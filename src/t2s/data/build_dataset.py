"""Build prompt-completion dataset for training, validation and dev."""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.t2s.config import AppConfig
from src.t2s.data.prompts import build_prompt_completion_entry
from src.t2s.data.schema import get_sqlite_schema_ddl
from src.t2s.data.spider_loader import SpiderExample, load_spider_examples
from src.t2s.data.split import split_train_val_by_db


def get_tokenizer(model_name: str) -> Any:
    try:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        return tokenizer
    except Exception as e:
        print(f"Warning: Could not load AutoTokenizer for {model_name}: {e}")
        return None


def count_tokens(tokenizer: Any, entry: Dict[str, Any]) -> Tuple[int, int, int]:
    if tokenizer is not None:
        try:
            # Render full prompt text using chat template if available
            if hasattr(tokenizer, "apply_chat_template"):
                prompt_text = tokenizer.apply_chat_template(
                    entry["prompt"], tokenize=False, add_generation_prompt=True
                )
            else:
                prompt_text = str(entry["prompt"])

            comp_text = entry["completion"][0]["content"]
            prompt_tokens = len(tokenizer.encode(prompt_text))
            comp_tokens = len(tokenizer.encode(comp_text))
            return prompt_tokens, comp_tokens, prompt_tokens + comp_tokens
        except Exception:
            pass

    # Heuristic fallback if tokenizer fails
    prompt_str = json.dumps(entry["prompt"])
    comp_str = json.dumps(entry["completion"])
    prompt_tokens = len(prompt_str.split())
    comp_tokens = len(comp_str.split())
    return prompt_tokens, comp_tokens, prompt_tokens + comp_tokens


def process_split(
    examples: List[SpiderExample],
    data_dir: Path,
    tokenizer: Any,
    max_seq_len: int,
    include_sample_rows: bool,
    schema_cache: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    entries: List[Dict[str, Any]] = []
    dropped_count = 0
    token_lengths: List[int] = []

    db_dir = data_dir / "database"

    for ex in examples:
        if ex.db_id not in schema_cache:
            db_path = db_dir / ex.db_id / f"{ex.db_id}.sqlite"
            schema_ddl = get_sqlite_schema_ddl(
                str(db_path), include_sample_rows=include_sample_rows
            )
            schema_cache[ex.db_id] = schema_ddl
        else:
            schema_ddl = schema_cache[ex.db_id]

        entry = build_prompt_completion_entry(
            schema_ddl=schema_ddl,
            question=ex.question,
            gold_sql=ex.query,
            db_id=ex.db_id,
        )

        p_tok, c_tok, total_tok = count_tokens(tokenizer, entry)
        entry["token_counts"] = {
            "prompt": p_tok,
            "completion": c_tok,
            "total": total_tok,
        }

        if total_tok > max_seq_len:
            dropped_count += 1
        else:
            entries.append(entry)
            token_lengths.append(total_tok)

    stats = {
        "total_input_examples": len(examples),
        "kept_examples": len(entries),
        "dropped_examples": dropped_count,
        "max_token_len": max(token_lengths) if token_lengths else 0,
        "min_token_len": min(token_lengths) if token_lengths else 0,
        "avg_token_len": sum(token_lengths) / len(token_lengths) if token_lengths else 0.0,
    }

    return entries, stats


def build_all_datasets(config_path: str = "configs/config.yaml") -> Dict[str, Any]:
    config = AppConfig.load(config_path)

    raw_dir = Path(config.paths.raw_data_dir)
    proc_dir = Path(config.paths.processed_data_dir)
    rep_dir = Path(config.paths.reports_dir)

    proc_dir.mkdir(parents=True, exist_ok=True)
    rep_dir.mkdir(parents=True, exist_ok=True)

    # 1. Load train and dev examples
    spider_train = load_spider_examples(str(raw_dir / "train_spider.json"))
    others_train = (
        load_spider_examples(str(raw_dir / "train_others.json"))
        if (raw_dir / "train_others.json").exists()
        else []
    )
    full_train = spider_train + others_train
    dev_exs = load_spider_examples(str(raw_dir / "dev.json"))

    # 2. Split train into train and val by database
    train_exs, val_exs, train_dbs, val_dbs = split_train_val_by_db(
        full_train, val_ratio=config.split.val_db_ratio, seed=config.seed
    )

    # 3. Load tokenizer
    tokenizer = get_tokenizer(config.model.base_model_name)

    # 4. Process datasets
    schema_cache: Dict[str, str] = {}
    train_entries, train_stats = process_split(
        train_exs,
        raw_dir,
        tokenizer,
        config.model.max_seq_len,
        config.generation.include_sample_rows,
        schema_cache,
    )
    val_entries, val_stats = process_split(
        val_exs,
        raw_dir,
        tokenizer,
        config.model.max_seq_len,
        config.generation.include_sample_rows,
        schema_cache,
    )
    dev_entries, dev_stats = process_split(
        dev_exs,
        raw_dir,
        tokenizer,
        config.model.max_seq_len,
        config.generation.include_sample_rows,
        schema_cache,
    )

    # 5. Save jsonl files
    def save_jsonl(entries: List[Dict[str, Any]], file_path: Path) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

    save_jsonl(train_entries, proc_dir / "train.jsonl")
    save_jsonl(val_entries, proc_dir / "val.jsonl")
    save_jsonl(dev_entries, proc_dir / "dev.jsonl")

    # 6. Save prompt stats report
    dev_dbs = {ex.db_id for ex in dev_exs}
    prompt_stats = {
        "max_seq_len_config": config.model.max_seq_len,
        "include_sample_rows": config.generation.include_sample_rows,
        "train_databases_count": len(train_dbs),
        "val_databases_count": len(val_dbs),
        "dev_databases_count": len(dev_dbs),
        "train_val_db_overlap": len(train_dbs.intersection(val_dbs)),
        "train_dev_db_overlap": len(train_dbs.intersection(dev_dbs)),
        "val_dev_db_overlap": len(val_dbs.intersection(dev_dbs)),
        "split_stats": {
            "train": train_stats,
            "val": val_stats,
            "dev": dev_stats,
        },
    }

    with open(rep_dir / "prompt_stats.json", "w", encoding="utf-8") as f:
        json.dump(prompt_stats, f, indent=2)

    return prompt_stats


if __name__ == "__main__":
    stats = build_all_datasets()
    print("Dataset Building Stats:")
    print(json.dumps(stats, indent=2))
