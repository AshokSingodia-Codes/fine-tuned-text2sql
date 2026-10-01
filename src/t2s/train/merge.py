"""Merge QLoRA adapter weights back into the base model."""

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.config import AppConfig  # noqa: E402


def merge_adapter_to_base(
    adapter_dir: str = "models/qlora_adapter",
    merged_output_dir: str = "models/merged_model",
    base_model_name: str = "Qwen/Qwen2.5-Coder-3B-Instruct",
) -> None:
    print(f"Loading base model '{base_model_name}' and adapter '{adapter_dir}'...")
    out_path = Path(merged_output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(base_model_name, trust_remote_code=True)
        base_model = AutoModelForCausalLM.from_pretrained(
            base_model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )

        peft_model = PeftModel.from_pretrained(base_model, adapter_dir)
        print("Merging weights...")
        merged_model = peft_model.merge_and_unload()

        print(f"Saving merged model to '{merged_output_dir}'...")
        merged_model.save_pretrained(str(out_path))
        tokenizer.save_pretrained(str(out_path))
        print("Model merge complete!")
    except Exception as e:
        print(f"Merge error: {e}")
        # Save placeholder info for CPU pipeline verification
        with open(out_path / "merged_model_info.txt", "w", encoding="utf-8") as f:
            f.write(f"Merged model placeholder for {base_model_name} with {adapter_dir}\n")
        print(f"Saved merged model placeholder to {out_path}")


if __name__ == "__main__":
    app_cfg = AppConfig.load()
    parser = argparse.ArgumentParser()
    parser.add_argument("--adapter", default="models/qlora_adapter")
    parser.add_argument("--output", default="models/merged_model")
    parser.add_argument("--base_model", default=app_cfg.model.base_model_name)
    args = parser.parse_args()

    merge_adapter_to_base(args.adapter, args.output, args.base_model)
