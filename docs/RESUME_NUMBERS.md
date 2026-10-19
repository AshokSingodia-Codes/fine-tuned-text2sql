# docs/RESUME_NUMBERS.md - Single Source of Truth for Resume & Portfolio Metrics

**Integrity Policy (Rule R1, R2, R6, R9):**
Every metric claimed on a resume, technical report, portfolio document, or blog post MUST originate from this registry and trace to an empirical JSON file in `results/`. No estimates. No fabricated numbers. No out-of-scope technologies (Kubernetes, Snowflake, BigQuery, etc.).

---

## 1. Core Model Performance Metrics (Spider Dev Split, $n=1,034$, Seed 42)

| Metric Description | Exact Value | Confidence Interval | Evidence File | Exact Reproduction Command |
|---|---|---|---|---|
| Base Model Zero-Shot Execution Accuracy | **62.28%** (644 / 1,034) | 95% Bootstrap: [59.38%, 65.18%] | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config A` |
| Base Model 3-Shot Execution Accuracy | **66.15%** (684 / 1,034) | 95% Bootstrap: [63.25%, 68.96%] | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config B` |
| Fine-Tuned FP16 Merged Execution Accuracy | **71.57%** (740 / 1,034) | 95% Bootstrap: [68.86%, 74.27%] | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config C` |
| Fine-Tuned GGUF Q4_K_M Execution Accuracy | **70.70%** (731 / 1,034) | 95% Bootstrap: [67.89%, 73.40%] | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config D` |
| Fine-Tuned GGUF Q4_K_M + AST Guardrail EX | **70.50%** (729 / 1,034) | 95% Bootstrap: [67.69%, 73.21%] | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config D --guarded` |
| Guarded Accuracy Excluding 33 Capped (>100 row) Queries | **72.83%** (729 / 1,001) | - | `results/canonical_equiv.json` | `python scripts/check_canonical_equiv.py` |
| Execution Accuracy Delta (Base Zero-Shot $\rightarrow$ Fine-Tuned Q4_K_M) | **+8.42 pp** (62.28% $\rightarrow$ 70.70%) | - | `results/eval_spider_latest.json` | Computed from Config A vs Config D |
| Accuracy Retention after 4-bit Quantization (FP16 $\rightarrow$ Q4_K_M) | **98.78%** relative (71.57% $\rightarrow$ 70.70%) | - | `results/eval_spider_latest.json` | Computed from Config C vs Config D |
| Memory Footprint Reduction (FP16 $\rightarrow$ GGUF Q4_K_M) | **69.35%** cut (6.2 GB $\rightarrow$ 1.9 GB) | - | `docs/ARTIFACTS.md` | Measured artifact file sizes on disk |
| CPU Generation Latency p50 (GGUF Q4_K_M on CPU) | **4.68 s** | - | `results/latency_latest.json` | `python scripts/bench_latency.py` |
| CPU Generation Latency p95 (GGUF Q4_K_M on CPU) | **11.23 s** | - | `results/latency_latest.json` | `python scripts/bench_latency.py` |
| Generation Throughput (CPU tokens/sec) | **5.86 tokens/s** | - | `results/latency_latest.json` | `python scripts/bench_latency.py` |

---

## 2. Safety, Red-Teaming & AST Guardrail Metrics

| Metric Description | Exact Value | Confidence Interval | Evidence File | Exact Reproduction Command |
|---|---|---|---|---|
| Path A Static AST Attack Block Rate (Raw) | **87.50%** (105 / 120) | 95% Wilson: [80.40%, 92.28%] | `results/redteam_latest.json` | `python scripts/eval_redteam.py` |
| Path A Static AST Attack Block Rate (Adjusted) | **96.33%** (105 / 109) | 95% Wilson: [90.94%, 98.56%] | `results/redteam_latest.json` | `python scripts/eval_redteam.py` |
| Path C SQLite Read-Only Sandbox Defense Rate | **100.00%** (120 / 120) | 95% Wilson: [96.90%, 100.00%] | `results/redteam_latest.json` | `python scripts/eval_redteam.py` |
| Path D Full Pipeline Attack Success Rate | **0.00%** (0 / 120) | 95% Wilson: [0.00%, 3.10%] | `results/redteam_latest.json` | `python scripts/eval_redteam.py` |
| Path B End-to-End Prompt Injection Attack Success | **0.00%** (0 / 60) | 95% Wilson: [0.00%, 6.02%] | `results/path_b_protocol_results.json` | `python scripts/run_path_b_protocol.py` |
| False Positive Rate on Spider Dev Gold Queries | **0.19%** (2 / 1,034) | 95% Wilson: [0.05%, 0.70%] | `results/false_blocks.json` | `python scripts/audit_false_positives.py` |
| Legitimate Query Pass Rate (Spider Dev + 76 Benign Controls) | **99.37%** (1,103 / 1,110) | 95% Wilson: [98.70%, 99.69%] | `results/false_blocks.json` | `python scripts/audit_false_positives.py` |
| Static AST Validator Median Overhead Latency (p50) | **2.44 ms** | - | `results/redteam_latest.json` | `python scripts/eval_redteam.py` |
| Static AST Validator 95th Percentile Latency (p95) | **7.28 ms** | - | `results/redteam_latest.json` | `python scripts/eval_redteam.py` |
| AST Grammar Fuzz Invariant Test Pass Rate | **100.00%** (1,000 / 1,000) | - | `tests/test_fuzz_ast.py` | `pytest tests/test_fuzz_ast.py` |
| Held-Out V2 Policy Escape Rate (Pre-Fix Frozen) | **8.33%** (4 / 48) | 95% Wilson: [3.29%, 19.55%] | `results/eval_heldout_v2.json` | `python scripts/eval_heldout_v2.py` |
| Held-Out V2 Harm Rate (Pre-Fix Frozen) | **0.00%** (0 / 48) | 95% Wilson: [0.00%, 7.41%] | `results/eval_heldout_v2.json` | `python scripts/eval_heldout_v2.py` |
| Held-Out V2_Dev Policy Escape Rate (Post-Fix Tuned) | **0.00%** (0 / 48) | 95% Wilson: [0.00%, 7.41%] | `results/eval_heldout_v2_dev.json` | `python scripts/eval_heldout_v2_dev.py` |
| Held-Out V2_Dev Harm Rate (Post-Fix Tuned) | **0.00%** (0 / 48) | 95% Wilson: [0.00%, 7.41%] | `results/eval_heldout_v2_dev.json` | `python scripts/eval_heldout_v2_dev.py` |

---

## 3. Serving, Concurrency & Load Test Metrics

| Metric Description | Exact Value | Evidence File | Exact Reproduction Command |
|---|---|---|---|
| Bounded Concurrency Semaphore Capacity | **1 active query** | `configs/config.yaml` | Inspect serving configuration |
| Maximum Queue Backlog Depth | **10 queued requests** | `configs/config.yaml` | Inspect serving configuration |
| Overload Rejection Status Code | **503 Service Unavailable** | `tests/test_serving_limits.py` | `pytest tests/test_serving_limits.py` |
| Max Request Payload Limit | **65,536 bytes (64 KB)** | `configs/config.yaml` | `pytest tests/test_serving_limits.py` |
| Fast-path Auth Latency Overhead | **< 1 ms** | `results/loadtest_latest.json` | `python scripts/loadtest.py --backend stub` |
| Serving Stack Overhead p50 (Stub Backend, Concurrency 1) | **3.89 ms** | `results/loadtest_latest.json` | `python scripts/loadtest.py --backend stub` |
| Serving Stack Overhead p95 (Stub Backend, Concurrency 4) | **6.75 ms** | `results/loadtest_latest.json` | `python scripts/loadtest.py --backend stub` |
| Interactive Demo Preset Accounting | **13 attempted, 10 passed, 3 blocked** | `results/demo_examples.json` | Inspect `results/demo_examples.json` |

---

## 4. Engineering & Code Quality Metrics

| Metric Description | Exact Value | Evidence File / Command |
|---|---|---|
| Automated Test Suite Status | **80 passed in 112s** | `pytest -q` |
| Code Formatting & Linting Status | **0 errors, 127 files checked** | `ruff check .` && `ruff format --check .` |
| Frozen Security Policy SHA-256 | `fb2ecba1d761ae4ba9e1e072b03136ce56237f2e3b2343c36dd1e48772cde801` | `sha256sum config/security_policy.yaml` |
| Data Leakage Test | **0 overlap between train and dev** | `python scripts/check_leakage.py` |

---

## 5. Unverified Preliminary Ablations (Documented per Rule R9)

| Configuration | Model & Setup | EX Reported | Status & Provenance Note |
|---|---|---|---|
| BASE+greedy | Base Qwen-3B, Kaggle T4 GPU | 62.28% (644 / 1,034) | **UNVERIFIED, harness suspect**: Predictions not saved to disk; greedy generator lacked sampling flags. |
| BASE+SC (Self-Correction) | Base Qwen-3B, Kaggle T4 GPU | 62.28% (644 / 1,034) | **UNVERIFIED, harness suspect**: Re-evaluation on fine-tuned GGUF pending per `docs/PHASE3B.md`. |
| BASE+V (Voting N=5) | Base Qwen-3B, Kaggle T4 GPU | 62.28% (644 / 1,034) | **UNVERIFIED, harness suspect**: Identical candidate outputs produced due to missing temperature flags. |
| BASE+SC+V (Both) | Base Qwen-3B, Kaggle T4 GPU | 62.28% (644 / 1,034) | **UNVERIFIED, harness suspect**: Scored query mechanism patched and regression tested in `tests/`. |
