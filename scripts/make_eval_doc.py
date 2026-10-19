"""Generate docs/EVALUATION.md and docs/PHASE1_SUMMARY.md from evaluation JSON files.

Strictly reads results/eval_spider_latest.json and results/latency_latest.json
to populate documentation tables without hardcoding numbers.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def make_eval_doc() -> None:
    eval_json_path = PROJECT_ROOT / "results" / "eval_spider_latest.json"
    latency_json_path = PROJECT_ROOT / "results" / "latency_latest.json"

    eval_data = {}
    if eval_json_path.exists():
        with open(eval_json_path, "r", encoding="utf-8") as f:
            eval_data = json.load(f)

    latency_data = {}
    if latency_json_path.exists():
        with open(latency_json_path, "r", encoding="utf-8") as f:
            latency_data = json.load(f)

    configs = eval_data.get("configs", {})
    backend_used = eval_data.get("metadata", {}).get("backend_used", "unknown")

    # Format table rows for EVALUATION.md
    def format_cfg(cfg_id: str, default_name: str, size: str) -> str:
        cfg = configs.get(cfg_id, {})
        if cfg and backend_used != "mock":
            ex = f"{cfg.get('execution_accuracy', 0.0) * 100:.2f}%"
            val_sql = f"{cfg.get('valid_sql_rate', 0.0) * 100:.2f}%"
            status = f"Measured ({backend_used})"
        else:
            ex = "*To Be Measured*"
            val_sql = "*To Be Measured*"
            status = "Pending Real Run" if backend_used != "mock" else "Mock Run (Excluded)"
        return f"| **Config {cfg_id}** | {default_name} | {size} | {ex} | {val_sql} | {status} |"

    row_a = format_cfg("A", "Base Zero-Shot", "6.2 GB")
    row_b = format_cfg("B", "Base 3-Shot", "6.2 GB")
    row_c = format_cfg("C", "Fine-Tuned FP16", "6.2 GB")
    row_d = format_cfg("D", "Quantized GGUF Q4_K_M", "1.9 GB")

    lat_metrics = latency_data.get("metrics", {})
    hw_info = latency_data.get("hardware", {})
    hw_desc = hw_info.get("description")
    if not hw_desc and hw_info:
        cpu = hw_info.get("cpu_name", "x86_64")
        cores = hw_info.get("cpu_physical_cores", 2)
        ram = hw_info.get("total_ram_gb", 31.35)
        os_name = hw_info.get("os", "Linux")
        cuda = ", CUDA" if hw_info.get("cuda_available") else ""
        hw_desc = f"{os_name} ({cpu}, {cores} cores, {ram} GB RAM{cuda})"
    if not hw_desc:
        hw_desc = "Not measured"

    p50 = f"{lat_metrics.get('p50_latency_sec', 0.0)} s" if lat_metrics else "*To Be Measured*"
    p95 = f"{lat_metrics.get('p95_latency_sec', 0.0)} s" if lat_metrics else "*To Be Measured*"
    p99 = f"{lat_metrics.get('p99_latency_sec', 0.0)} s" if lat_metrics else "*To Be Measured*"
    tok_sec_val = lat_metrics.get("tokens_per_sec") or lat_metrics.get("tokens_per_second", 0.0)
    tok_sec = f"{tok_sec_val:.2f}" if lat_metrics else "*To Be Measured*"

    eval_doc_content = f"""# Evaluation Methodology & Benchmark Specifications

This document defines the evaluation methodology, common prompt template, hardware specifications, evaluation metrics, and execution instructions for the **Text-to-SQL Assistant**.

> **Note on Metric Provenance**: To prevent data fabrication, mock backend runs are stored under `results/smoke/` and excluded from official evaluation docs. All FP16 and GGUF metrics below are derived directly from `results/eval_spider_latest.json` and `results/latency_latest.json`.

---

## 1. Common Prompt Template

To ensure strict parity across all model configurations (A, B, C, D), all evaluations use the exact same prompt template:

```text
System: "You are a text-to-SQL assistant. Return only one SQLite SELECT query. No explanations."

User:
### SQLite Schema:
CREATE TABLE department (
  Department_ID INTEGER,
  Name TEXT,
  PRIMARY KEY (Department_ID)
);

### Question:
How many departments are there?
```

---

## 2. Evaluation Metric Definitions

- **Execution Accuracy (EX)**: Percentage of predicted SQL queries that return the exact same multiset result table as the gold SQL query when executed on the target SQLite database.
- **Valid SQL Rate**: Percentage of generated SQL queries that execute without SQLite syntax or runtime errors.
- **Execution Error Rate**: Percentage of queries resulting in a database execution error.
- **Timeout Rate**: Percentage of queries exceeding the 3.0-second execution time limit.
- **Guardrail Block Rate**: Percentage of generated queries blocked by the AST SQL validator.

---

## 3. Target Benchmark Matrix

| Config ID | System Description | Model Size | Execution Accuracy (Dev) | Valid SQL Rate | Status |
|---|---|---|---|---|---|
{row_a}
{row_b}
{row_c}
{row_d}

### Latency & Serving Benchmark (Config D)
- **Hardware**: {hw_desc}
- **p50 Latency**: {p50}
- **p95 Latency**: {p95}
- **p99 Latency**: {p99}
- **Throughput**: {tok_sec} tokens/sec

---

## 4. Execution Commands for Real Model Evaluation

### A. Google Colab GPU Commands (for Configs A, B, C FP16 Evaluation)
Run the following bash script in a GPU-enabled Colab environment (T4 / A100):

```bash
# 1. Mount Drive & unzip project bundle
unzip phase1_bundle.zip -d /content/proj
cd /content/proj

# 2. Run FP16 GPU Evaluation across all 1,034 Spider dev questions
python scripts/eval_spider.py --backend transformers --model-path Qwen/Qwen2.5-Coder-3B-Instruct --config A
python scripts/eval_spider.py --backend transformers --model-path Qwen/Qwen2.5-Coder-3B-Instruct --config B
python scripts/eval_spider.py --backend transformers --model-path models/merged_model --config C
```

### B. GGUF Evaluation & Latency Benchmark (Config D)
```bash
python scripts/eval_spider.py --backend openai_compat --model-path models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf --config D
python scripts/bench_latency.py --backend openai_compat --model-path models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf --limit 200
```
"""

    eval_doc_path = PROJECT_ROOT / "docs" / "EVALUATION.md"
    with open(eval_doc_path, "w", encoding="utf-8") as f:
        f.write(eval_doc_content)
    print(f"Updated {eval_doc_path.name}")

    # Generate docs/PHASE1_SUMMARY.md
    summary_rows = []
    for cfg_id in ["A", "B", "C", "D"]:
        c_info = configs.get(cfg_id, {})
        ex_val = (
            f"{c_info.get('execution_accuracy', 0.0) * 100:.2f}%"
            if c_info and backend_used != "mock"
            else "Pending"
        )
        summary_rows.append(
            f"| Config {cfg_id} EX | {ex_val} | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config {cfg_id}` |"
        )

    if lat_metrics:
        summary_rows.append(
            f"| Latency p50 | {lat_metrics.get('p50_latency_sec', 0.0):.2f} s | `results/latency_latest.json` | `python scripts/bench_latency.py` |"
        )
        summary_rows.append(
            f"| Latency p95 | {lat_metrics.get('p95_latency_sec', 0.0):.2f} s | `results/latency_latest.json` | `python scripts/bench_latency.py` |"
        )
        summary_rows.append(
            f"| Latency p99 | {lat_metrics.get('p99_latency_sec', 0.0):.2f} s | `results/latency_latest.json` | `python scripts/bench_latency.py` |"
        )

    summary_table_rows = "\n".join(summary_rows)
    summary_content = f"""# Phase 1 Summary: Real Metric Provenance

This file records all official Phase 1 benchmark metrics, their source files, and reproduction commands.

| Metric Name | Value | Source File | Reproduction Command |
|---|---|---|---|
{summary_table_rows}
"""

    summary_doc_path = PROJECT_ROOT / "docs" / "PHASE1_SUMMARY.md"
    with open(summary_doc_path, "w", encoding="utf-8") as f:
        f.write(summary_content)
    print(f"Updated {summary_doc_path.name}")


if __name__ == "__main__":
    make_eval_doc()
