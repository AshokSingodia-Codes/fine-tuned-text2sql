"""Unit test verifying that docs/EVALUATION.md matches results JSON files or explicitly marks them as To Be Measured."""

import json
from pathlib import Path


def test_docs_match_results() -> None:
    eval_doc = Path("docs/EVALUATION.md")
    eval_json = Path("results/eval_spider_latest.json")
    latency_json = Path("results/latency_latest.json")

    assert eval_doc.exists(), "docs/EVALUATION.md must exist"

    doc_text = eval_doc.read_text(encoding="utf-8")

    if eval_json.exists() and latency_json.exists():
        with open(eval_json, "r", encoding="utf-8") as f:
            eval_data = json.load(f)

        with open(latency_json, "r", encoding="utf-8") as f:
            latency_data = json.load(f)

        for c_id, c_info in eval_data.get("configs", {}).items():
            ex_pct = f"{c_info.get('execution_accuracy', 0.0) * 100:.2f}%"
            assert ex_pct in doc_text, (
                f"Expected EX percentage {ex_pct} for Config {c_id} in docs/EVALUATION.md"
            )

        p50_raw = latency_data.get("metrics", {}).get("p50_latency_sec", 0.0)
        p50_raw_str = f"{p50_raw} s"
        p50_round_str = f"{p50_raw:.2f} s"
        assert (p50_raw_str in doc_text) or (p50_round_str in doc_text), (
            f"Expected p50 latency {p50_raw_str} or {p50_round_str} in docs/EVALUATION.md"
        )
    else:
        assert "To Be Measured" in doc_text, (
            "Docs must state 'To Be Measured' when real results JSON files are absent"
        )
