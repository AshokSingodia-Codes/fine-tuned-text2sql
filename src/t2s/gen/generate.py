"""SQL Generation runner."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from src.t2s.gen.backends import BaseBackend, get_backend


def clean_generated_sql(text: str) -> str:
    if not text:
        return ""

    # Remove code fences
    cleaned = re.sub(r"```(?:sql)?\s*(.*?)\s*```", r"\1", text, flags=re.DOTALL | re.IGNORECASE)

    # Trim leading/trailing whitespace
    cleaned = cleaned.strip()

    # Keep only the first SQL statement if multiple statements exist
    if ";" in cleaned:
        parts = cleaned.split(";")
        cleaned = parts[0].strip() + ";"
    elif not cleaned.endswith(";"):
        cleaned = cleaned + ";"

    # Take first line if explanation follows
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if lines:
        cleaned = " ".join(lines)

    return cleaned


def run_generation(
    dataset_jsonl_path: str,
    output_predictions_path: str,
    backend: BaseBackend,
    batch_size: int = 1,
) -> List[Dict[str, Any]]:
    path = Path(dataset_jsonl_path)
    if not path.exists():
        raise FileNotFoundError(f"Input jsonl not found: {dataset_jsonl_path}")

    entries: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    predictions: List[Dict[str, Any]] = []

    for i in range(0, len(entries), batch_size):
        batch_entries = entries[i : i + batch_size]
        prompts = [entry["prompt"] for entry in batch_entries]

        gen_outputs = backend.generate(prompts)

        for entry, gen_out in zip(batch_entries, gen_outputs):
            raw_text = gen_out["text"]
            cleaned_sql = clean_generated_sql(raw_text)

            pred_record = {
                "db_id": entry.get("db_id", ""),
                "question": entry.get("question", ""),
                "gold": entry.get("gold_sql", entry.get("completion", [{}])[0].get("content", "")),
                "pred": cleaned_sql,
                "raw_pred": raw_text,
                "latency_ms": gen_out["latency_ms"],
                "tokens": gen_out["tokens"],
            }
            predictions.append(pred_record)

    out_path = Path(output_predictions_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for pred in predictions:
            f.write(json.dumps(pred) + "\n")

    return predictions


if __name__ == "__main__":
    mock_be = get_backend("mock")
    preds = run_generation(
        "data/processed/dev.jsonl", "data/processed/mock_predictions.jsonl", mock_be
    )
    print(f"Generated {len(preds)} mock predictions.")
