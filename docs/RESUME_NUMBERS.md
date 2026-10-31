# docs/RESUME_NUMBERS.md - Single Source of Truth for Resume & Portfolio Metrics

**Integrity Policy (Rule R1, R2, R6, R9):**
Every metric claimed on a resume, technical report, portfolio document, or blog post MUST originate from this registry and trace to an empirical JSON file in `results/`. No estimates. No fabricated numbers. No out-of-scope technologies (Kubernetes, Snowflake, BigQuery, etc.).

---

## 1. Core Model Performance Metrics (Spider Dev Split, $n=1,034$, Seed 42)

| Metric Description | Exact Value | Status | Evidence File | Exact Reproduction Command | Reason / Provenance Caveat |
|---|---|---|---|---|---|
| Base Model Zero-Shot Execution Accuracy | **62.28%** (644 / 1,034) | **CAVEAT** | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config A` | Zero-shot baseline evaluated on cloud Linux GPU ingest; hardware not identical to local CPU. |
| Base Model 3-Shot Execution Accuracy | **66.15%** (684 / 1,034) | **CAVEAT** | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config B` | 3-shot in-context baseline evaluated on cloud Linux GPU ingest. |
| Fine-Tuned FP16 Merged Execution Accuracy | **71.57%** (740 / 1,034) | **CAVEAT** | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config C` | Evaluated on cloud Linux GPU ingest. |
| Fine-Tuned GGUF Q4_K_M Execution Accuracy | **70.70%** (731 / 1,034) | **CLAIMABLE** | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config D` | Real local GGUF model binary on Spider dev split (1,034 queries). |
| Fine-Tuned GGUF Q4_K_M + AST Guardrail EX | **70.50%** (729 / 1,034) | **CLAIMABLE** | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config D --guarded` | Production guarded serving pipeline. |
| Guarded Accuracy Excluding 33 Capped (>100 row) Queries | **72.83%** (729 / 1,001) | **CLAIMABLE** | `results/canonical_equiv.json` | `python scripts/check_canonical_equiv.py` | Evaluated over 1,001 uncapped queries under production LIMIT 100 guardrail. |
| Execution Accuracy Delta (Base Zero-Shot $\rightarrow$ Fine-Tuned Q4_K_M) | **+8.42 pp** (62.28% $\rightarrow$ 70.70%) | **CAVEAT** | `results/eval_spider_latest.json` | Computed from Config A vs Config D | Base and fine-tuned were evaluated on different hardware environments. |
| Accuracy Retention after 4-bit Quantization (FP16 $\rightarrow$ Q4_K_M) | **98.78%** relative (71.57% $\rightarrow$ 70.70%) | **CLAIMABLE** | `results/eval_spider_latest.json` | Computed from Config C vs Config D | Standard quantization retention metric. |
| Memory Footprint Reduction (FP16 $\rightarrow$ GGUF Q4_K_M) | **69.35%** cut (6.2 GB $\rightarrow$ 1.9 GB) | **CLAIMABLE** | `docs/ARTIFACTS.md` | Measured artifact file sizes on disk | Real artifact files verified via SHA256. |
| CPU Generation Latency p50 (GGUF Q4_K_M on CPU) | **4.68 s** | **CLAIMABLE** | `results/latency_latest.json` | `python scripts/bench_latency.py` | Local CPU benchmark over 200 questions. |
| CPU Generation Latency p95 (GGUF Q4_K_M on CPU) | **11.23 s** | **CLAIMABLE** | `results/latency_latest.json` | `python scripts/bench_latency.py` | Local CPU benchmark over 200 questions. |
| Generation Throughput (CPU tokens/sec) | **5.86 tokens/s** | **CLAIMABLE** | `results/latency_latest.json` | `python scripts/bench_latency.py` | Measured token generation rate on CPU. |

---

## 2. Safety, Red-Teaming & AST Guardrail Metrics

| Metric Description | Exact Value | Status | Evidence File | Exact Reproduction Command | Reason / Provenance Caveat |
|---|---|---|---|---|---|
| Path A Static AST Attack Block Rate (Raw) | **87.50%** (105 / 120) | **CLAIMABLE** | `results/redteam_latest.json` | `python scripts/eval_redteam.py` | Direct red-team evaluation across 120 attack vectors. |
| Path A Static AST Attack Block Rate (Adjusted) | **96.33%** (105 / 109) | **CLAIMABLE** | `results/redteam_latest.json` | `python scripts/eval_redteam.py` | Adjusted for out-of-scope dialect exploits. |
| Path C SQLite Read-Only Sandbox Defense Rate | **100.00%** (120 / 120) | **CLAIMABLE** | `results/redteam_latest.json` | `python scripts/eval_redteam.py` | Read-only SQLite URI and authorizer hooks. |
| Path D Full Pipeline Attack Success Rate | **0.00%** (0 / 120) | **CLAIMABLE** | `results/redteam_latest.json` | `python scripts/eval_redteam.py` | End-to-end layered defense neutralizing all attacks. |
| Path B End-to-End Prompt Injection Attack Success | **0.00%** (0 / 60) | **CLAIMABLE** | `results/path_b_protocol_results.json` | `python scripts/run_path_b_protocol.py` | Model-in-the-loop prompt injection evaluations. |
| False Positive Rate on Spider Dev Gold Queries | **0.19%** (2 / 1,034) | **CLAIMABLE** | `results/false_blocks.json` | `python scripts/audit_false_positives.py` | Benign queries incorrectly blocked. |
| Legitimate Query Pass Rate (Spider Dev + 76 Benign Controls) | **99.37%** (1,103 / 1,110) | **CLAIMABLE** | `results/false_blocks.json` | `python scripts/audit_false_positives.py` | Benign query pass rate across gold dev and controls. |
| Static AST Validator Median Overhead Latency (p50) | **2.44 ms** | **CLAIMABLE** | `results/redteam_latest.json` | `python scripts/eval_redteam.py` | Static parsing overhead. |
| Static AST Validator 95th Percentile Latency (p95) | **7.28 ms** | **CLAIMABLE** | `results/redteam_latest.json` | `python scripts/eval_redteam.py` | 95th percentile parsing overhead. |
| AST Grammar Fuzz Invariant Test Pass Rate | **100.00%** (1,000 / 1,000) | **CLAIMABLE** | `tests/test_fuzz_validator.py` | `pytest tests/test_fuzz_validator.py` | Hypothesis fuzzing suite with 1,000 iterations. |
| Held-Out V2 Policy Escape Rate (Pre-Fix Frozen) | **8.33%** (4 / 48) | **CLAIMABLE** | `results/eval_heldout_v2.json` | `python scripts/eval_heldout_v2.py` | Pre-fix frozen baseline held-out suite. |
| Held-Out V2 Harm Rate (Pre-Fix Frozen) | **0.00%** (0 / 48) | **CLAIMABLE** | `results/eval_heldout_v2.json` | `python scripts/eval_heldout_v2.py` | Read-only authorizer blocked all escaped queries. |
| Held-Out V2_Dev Policy Escape Rate (Post-Fix Tuned) | **0.00%** (0 / 48) | **CLAIMABLE** | `results/eval_heldout_v2_dev.json` | `python scripts/eval_heldout_v2_dev.py` | Post-fix tuned held-out evaluation. |
| Held-Out V2_Dev Harm Rate (Post-Fix Tuned) | **0.00%** (0 / 48) | **CLAIMABLE** | `results/eval_heldout_v2_dev.json` | `python scripts/eval_heldout_v2_dev.py` | Zero harm executed. |

---

## 3. Serving, Concurrency & Load Test Metrics

| Metric Description | Exact Value | Status | Evidence File | Exact Reproduction Command | Reason / Provenance Caveat |
|---|---|---|---|---|---|
| Bounded Concurrency Semaphore Capacity | **1 active query** | **CLAIMABLE** | `configs/config.yaml` | Inspect serving configuration | Single active generation thread for CPU safety. |
| Maximum Queue Backlog Depth | **10 queued requests** | **CLAIMABLE** | `configs/config.yaml` | Inspect serving configuration | Bounded FIFO waiting queue. |
| Overload Rejection Status Code | **503 Service Unavailable** | **CLAIMABLE** | `tests/test_serving_limits.py` | `pytest tests/test_serving_limits.py` | Clean rejection on queue saturation. |
| Max Request Payload Limit | **65,536 bytes (64 KB)** | **CLAIMABLE** | `configs/config.yaml` | `pytest tests/test_serving_limits.py` | Clamped request body size. |
| Fast-path Auth Latency Overhead | **< 1 ms** | **CLAIMABLE** | `results/loadtest_latest.json` | `python scripts/loadtest.py --backend stub` | Constant-time bearer validation overhead. |
| Serving Stack Overhead p50 (Stub Backend, Concurrency 1) | **3.89 ms** | **CLAIMABLE** | `results/loadtest_latest.json` | `python scripts/loadtest.py --backend stub` | Serving framework latency with stub generation. |
| Serving Stack Overhead p95 (Stub Backend, Concurrency 4) | **6.75 ms** | **CLAIMABLE** | `results/loadtest_latest.json` | `python scripts/loadtest.py --backend stub` | Queueing and dispatch latency under concurrent load. |
| Interactive Demo Preset Accounting | **13 attempted, 10 passed, 3 blocked** | **CLAIMABLE** | `results/demo_examples.json` | Inspect `results/demo_examples.json` | Preset queries in interactive demo. |

---

## 4. Engineering & Code Quality Metrics

| Metric Description | Exact Value | Status | Evidence File | Exact Reproduction Command | Reason / Provenance Caveat |
|---|---|---|---|---|---|
| Automated Test Suite Status | **83 passed** | **CLAIMABLE** | `pytest -q` | `pytest -q` | Full test suite across serving, safety, and evaluation. |
| Code Formatting & Linting Status | **0 errors** | **CLAIMABLE** | `ruff check .` | `ruff check .` | Clean lint checks across repository. |
| Frozen Security Policy SHA-256 | `682e3439354213f37b7645592a57b439a94f3d5073794fa86a349ca5761a8daa` | **CLAIMABLE** | `config/security_policy.yaml` | `python scripts/check_phase2.py` | Cryptographically frozen AST and executor policy. |
| Data Leakage Test | **0 overlap between train and dev** | **CLAIMABLE** | `scripts/check_leakage.py` | `python scripts/check_leakage.py` | Zero overlap of (question, db_id) pairs. |

---

## 5. Self-Correction, Voting & Phase 3b Status (Documented per Rule R9)

| Metric Description | Exact Value | Status | Evidence File | Exact Reproduction Command | Reason / Provenance Caveat |
|---|---|---|---|---|---|
| Self-Correction Accuracy Uplift (Fine-Tuned Model) | **Not Evaluated** | **NOT YET** | `docs/PHASE3B.md` | `python scripts/eval_phase3_self_correction.py --model-path <path_or_repo> --eval-split dev --seed 42` | not evaluated on fine-tuned model, pending Phase 3b |
| Majority Voting Accuracy Uplift (Fine-Tuned Model) | **Not Evaluated** | **NOT YET** | `docs/PHASE3B.md` | `python scripts/eval_phase3_self_correction.py --model-path <path_or_repo> --eval-split dev --seed 42` | not evaluated on fine-tuned model, pending Phase 3b |
| Combined Self-Correction + Voting Uplift | **Not Evaluated** | **NOT YET** | `docs/PHASE3B.md` | `python scripts/eval_phase3_self_correction.py --model-path <path_or_repo> --eval-split dev --seed 42` | not evaluated on fine-tuned model, pending Phase 3b |
| Base Model Preliminary Self-Correction Trial | **62.28%** (644 / 1,034) | **NOT YET** | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config A` | not evaluated on fine-tuned model, pending Phase 3b (preliminary base trial unverified, greedy generator omitted sampling flags) |
| Base Model Preliminary Voting Trial | **62.28%** (644 / 1,034) | **NOT YET** | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config A` | not evaluated on fine-tuned model, pending Phase 3b (preliminary base trial unverified, sampling temperature omitted) |
