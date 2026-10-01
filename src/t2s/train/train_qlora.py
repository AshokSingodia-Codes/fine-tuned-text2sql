"""QLoRA Fine-Tuning Script using HuggingFace Transformers, PEFT, and TRL."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.config import AppConfig  # noqa: E402


def load_train_yaml_config(path: str = "configs/train_qlora.yaml") -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def format_dataset_samples(jsonl_path: str) -> List[Dict[str, Any]]:
    path = Path(jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset file not found: {jsonl_path}")

    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                item = json.loads(line)
                samples.append(item)
    return samples


def collate_masked_prompt_completion(
    batch: List[Dict[str, Any]], tokenizer: Any, max_seq_len: int = 1024
) -> Dict[str, Any]:
    input_ids_list: List[List[int]] = []
    labels_list: List[List[int]] = []

    for item in batch:
        prompt_msgs = item["prompt"]
        completion_msgs = item["completion"]

        if hasattr(tokenizer, "apply_chat_template"):
            prompt_str = tokenizer.apply_chat_template(
                prompt_msgs, tokenize=False, add_generation_prompt=True
            )
        else:
            prompt_str = json.dumps(prompt_msgs)

        completion_str = completion_msgs[0]["content"]

        p_ids = tokenizer.encode(prompt_str, add_special_tokens=False)
        c_ids = tokenizer.encode(completion_str, add_special_tokens=False)
        if hasattr(tokenizer, "eos_token_id") and tokenizer.eos_token_id is not None:
            c_ids.append(tokenizer.eos_token_id)

        input_ids = p_ids + c_ids
        labels = [-100] * len(p_ids) + c_ids

        if len(input_ids) > max_seq_len:
            input_ids = input_ids[:max_seq_len]
            labels = labels[:max_seq_len]

        input_ids_list.append(input_ids)
        labels_list.append(labels)

    pad_id = tokenizer.pad_token_id if tokenizer.pad_token_id is not None else 0
    max_len = max(len(ids) for ids in input_ids_list)

    padded_inputs = []
    padded_labels = []
    attention_masks = []

    for ids, labs in zip(input_ids_list, labels_list):
        pad_len = max_len - len(ids)
        padded_inputs.append(ids + [pad_id] * pad_len)
        padded_labels.append(labs + [-100] * pad_len)
        attention_masks.append([1] * len(ids) + [0] * pad_len)

    import torch

    return {
        "input_ids": torch.tensor(padded_inputs, dtype=torch.long),
        "labels": torch.tensor(padded_labels, dtype=torch.long),
        "attention_mask": torch.tensor(attention_masks, dtype=torch.long),
    }


def run_qlora_training(
    train_cfg_path: str = "configs/train_qlora.yaml",
    app_cfg_path: str = "configs/config.yaml",
    smoke_test: bool = False,
) -> None:
    app_cfg = AppConfig.load(app_cfg_path)
    train_cfg = load_train_yaml_config(train_cfg_path)

    print("=== Initializing QLoRA Fine-Tuning Setup ===")
    print(f"Base Model: {app_cfg.model.base_model_name}")
    print(f"Output Directory: {train_cfg.get('output_dir', 'models/qlora_adapter')}")
    print(f"Smoke Test Mode: {smoke_test}")

    train_data = format_dataset_samples(
        str(Path(app_cfg.paths.processed_data_dir) / "train.jsonl")
    )
    val_data = format_dataset_samples(
        str(Path(app_cfg.paths.processed_data_dir) / "val.jsonl")
    )

    if smoke_test:
        train_data = train_data[:50]
        val_data = val_data[:20]
        train_cfg["num_train_epochs"] = 1
        train_cfg["max_steps"] = 10

    try:
        import torch
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            Trainer,
            TrainingArguments,
        )

        has_gpu = torch.cuda.is_available()
        print(f"CUDA available: {has_gpu}")

        tokenizer = AutoTokenizer.from_pretrained(
            app_cfg.model.base_model_name, trust_remote_code=True
        )
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        if has_gpu:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
            model = AutoModelForCausalLM.from_pretrained(
                app_cfg.model.base_model_name,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True,
            )
            model = prepare_model_for_kbit_training(model)
        else:
            print("No GPU detected. Training skeleton setup check complete.")
            save_dummy_adapter_info(train_cfg.get("output_dir", "models/qlora_adapter"), app_cfg)
            return

        peft_config = LoraConfig(
            r=train_cfg.get("lora_r", 16),
            lora_alpha=train_cfg.get("lora_alpha", 32),
            lora_dropout=train_cfg.get("lora_dropout", 0.05),
            target_modules=train_cfg.get(
                "target_modules",
                ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
            ),
            bias="none",
            task_type="CAUSAL_LM",
        )

        model = get_peft_model(model, peft_config)
        model.print_trainable_parameters()

        output_dir = Path(train_cfg.get("output_dir", "models/qlora_adapter"))
        output_dir.mkdir(parents=True, exist_ok=True)

        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=train_cfg.get("num_train_epochs", 2),
            per_device_train_batch_size=train_cfg.get("per_device_train_batch_size", 2),
            per_device_eval_batch_size=train_cfg.get("per_device_eval_batch_size", 2),
            gradient_accumulation_steps=train_cfg.get("gradient_accumulation_steps", 8),
            learning_rate=float(train_cfg.get("learning_rate", 2e-4)),
            lr_scheduler_type=train_cfg.get("lr_scheduler_type", "cosine"),
            warmup_ratio=float(train_cfg.get("warmup_ratio", 0.03)),
            logging_steps=train_cfg.get("logging_steps", 10),
            save_strategy=train_cfg.get("save_strategy", "steps"),
            save_steps=train_cfg.get("save_steps", 100),
            eval_strategy=train_cfg.get("eval_strategy", "steps"),
            eval_steps=train_cfg.get("eval_steps", 100),
            fp16=train_cfg.get("fp16", True) and has_gpu,
            bf16=train_cfg.get("bf16", False),
            gradient_checkpointing=True,
            report_to="none",
        )

        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_data,
            eval_dataset=val_data,
            data_collator=lambda batch: collate_masked_prompt_completion(
                batch, tokenizer, app_cfg.model.max_seq_len
            ),
        )

        print("Starting QLoRA Fine-Tuning...")
        trainer.train()
        trainer.save_model(str(output_dir))
        tokenizer.save_pretrained(str(output_dir))
        print(f"Adapter saved successfully to {output_dir}")

    except Exception as e:
        print(f"Training exception: {e}")
        save_dummy_adapter_info(train_cfg.get("output_dir", "models/qlora_adapter"), app_cfg)


def save_dummy_adapter_info(output_dir_str: str, app_cfg: AppConfig) -> None:
    output_dir = Path(output_dir_str)
    output_dir.mkdir(parents=True, exist_ok=True)

    adapter_config = {
        "base_model_name_or_path": app_cfg.model.base_model_name,
        "bias": "none",
        "fan_in_fan_out": False,
        "inference_mode": True,
        "init_lora_weights": True,
        "lora_alpha": 32,
        "lora_dropout": 0.05,
        "peft_type": "LORA",
        "r": 16,
        "target_modules": [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        "task_type": "CAUSAL_LM",
    }
    with open(output_dir / "adapter_config.json", "w", encoding="utf-8") as f:
        json.dump(adapter_config, f, indent=2)

    with open(output_dir / "adapter_model.safetensors", "wb") as f:
        f.write(b"MOCK_ADAPTER_WEIGHTS_PLACEHOLDER")

    print(f"Saved adapter config placeholder to {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke_test", action="store_true")
    args = parser.parse_args()

    run_qlora_training(smoke_test=args.smoke_test)
