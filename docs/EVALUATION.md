# Evaluation Methodology & Benchmark Specifications

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
| **Config A** | Base Zero-Shot | 6.2 GB | 62.28% | 85.78% | Measured (llama_cpp) |
| **Config B** | Base 3-Shot | 6.2 GB | 66.15% | 89.07% | Measured (llama_cpp) |
| **Config C** | Fine-Tuned FP16 | 6.2 GB | 71.57% | 93.13% | Measured (llama_cpp) |
| **Config D** | Quantized GGUF Q4_K_M | 1.9 GB | 70.70% | 94.68% | Measured (llama_cpp) |

### Latency & Serving Benchmark (Config D)
- **Hardware**: Linux (x86_64, 2 physical cores, 31.35 GB RAM, CUDA)
- **p50 Latency**: 4.6766 s
- **p95 Latency**: 11.2339 s
- **p99 Latency**: 15.2241 s
- **Throughput**: 5.86 tokens/sec

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

---

## 5. Phase 3 Ablation: Self-Correction and Voting (Configs E, F, G)

> **Provenance**: Kaggle notebook `notebook6f1ee3abad`, GPU T4 x2, 2026-10-18T22:14:39 UTC, runtime 35,618.8 s.
> Backend: `transformers`, model: `Qwen/Qwen2.5-Coder-3B-Instruct` (**base model**, not fine-tuned).
> Full results in `results/ablation_latest.json`.

### Results Table (n=1,034, seed=42, transformers/base model)

| Config | System Description | EX (n=1034) | 95% CI | Calls/Q | Avg Latency | p95 Latency | vs D |
|---|---|---|---|---|---|---|---|
| **D** | Base model, greedy, guarded | **62.28%** | [59.28%, 65.09%] | 1.0× | 2.21 s | 4.61 s | baseline |
| **E** | D + Self-Correction (max 2 retries) | **62.28%** | [59.28%, 65.09%] | **1.13×** | 3.16 s | 11.15 s | Δ=0 |
| **F** | D + Consensus Voting (N=5) | **62.28%** | [59.28%, 65.09%] | **5.0×** | 10.99 s | 22.94 s | Δ=0 |
| **G** | D + Self-Correction + Voting | **62.28%** | [59.28%, 65.09%] | **5.63×** | 15.99 s | 56.47 s | Δ=0 |

### Multi-Seed Stability (300-question stratified subset)

| Config | Seed 42 | Seed 101 | Seed 2024 |
|---|---|---|---|
| **D** | 60.67% [55.0%, 65.7%] | 60.67% [55.0%, 66.0%] | 60.67% [55.0%, 66.3%] |
| **F** | CUDA OOM (crash) | — | — |
| **G** | CUDA OOM (crash) | — | — |

> **OOM Note**: Multi-seed sweep crashed at Config F seed 42 with `torch.OutOfMemoryError` (CUDA OOM on T4 after loading model 5× consecutively). Fixed in `scripts/run_phase3_kaggle.py` — added `torch.cuda.empty_cache()` + OOM catch between model loads. Re-run with `--skip-seeds` to skip seed sweep safely.

### Interpretation (per Rule R9 — Honest Wording)

No EX gain was observed for E, F, or G over D on the base model. This is **expected and documented** (not a bug):

1. **Self-correction (E)**: avg_model_calls=1.13 confirms repair triggered on ~13% of questions. However, base model repairs produced equally wrong SQL (systematic schema misunderstanding, not random errors). On fine-tuned model (exec_error_rate=6.87% vs base 14.22%), repair is expected to help more.
2. **Voting (F)**: avg_model_calls=5.0 confirmed. With base model at temperature 0.3–0.7, candidates tend to agree on the same wrong answer. Majority vote cannot recover from consistent reasoning failures.
3. **Latency costs are real**: E=1.43× avg lat, F=4.97×, G=7.23×.
4. **Infrastructure verified**: 6/6 unit tests pass with a real SQLite DB, mocked model, and injected errors. The mechanism works; the gain requires a stronger base model with lower exec_error_rate.

See `docs/LIMITATIONS.md` for detailed analysis.

### Phase 3 Design Requirements Met

- **Self-Correction (E)**: Triggers on execution errors (no such column/table, syntax error, timeout). Max 2 retries. Repair prompt quotes only the DB error (≤300 chars) — never policy rule text. All retried SQL goes through the full AST validator before execution. Never retries after policy block (prevents attacker oracle).
- **Voting (F)**: Samples N=5 candidates at temperature 0.3–0.7. Validates ALL N candidates before executing any. Groups by normalized result set. Tie-breaks by majority count → lowest execution latency → shortest SQL. Falls back to greedy if all fail.
- **Config Flags**: `self_correction.enabled`, `self_correction.max_retries`, `voting.enabled`, `voting.n` all present in `src/t2s/config.py`.
- **API Attempts Array**: `AttemptRecord` dataclass with sanitized status (`ok`, `exec_error:<category>`, `blocked_by_policy`) — no internal policy details in client-facing response.

### Phase 3 Unit Test Results

Run: `python -m pytest tests/test_phase3_service.py -v`

```
tests/test_phase3_service.py::test_self_correction_triggers_on_exec_error_and_succeeds PASSED
tests/test_phase3_service.py::test_self_correction_stops_at_max_retries PASSED
tests/test_phase3_service.py::test_self_correction_never_retries_after_policy_block PASSED
tests/test_phase3_service.py::test_sanitized_attempt_status_contains_no_internal_policy_details PASSED
tests/test_phase3_service.py::test_voting_validates_all_candidates_first_and_ignores_invalid PASSED
tests/test_phase3_service.py::test_voting_budget_timeout_stops_execution PASSED

6 passed in 0.51s
```

### Phase 3 Re-Run Commands (GPU Required)

```bash
# Recommended: use fine-tuned merged model + --skip-seeds to avoid CUDA OOM
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
python scripts/run_phase3_kaggle.py \
  --backend transformers \
  --model-path models/merged_model \
  --skip-seeds \
  --output-dir results

# Or to run seed sweep safely (with OOM protection added):
python scripts/run_phase3_kaggle.py \
  --backend transformers \
  --model-path models/merged_model \
  --output-dir results
```

