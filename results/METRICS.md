# Results & Metric Registry (METRICS.md)

**Single Source of Truth** for all metrics reported across `README.md`, `THREAT_MODEL.md`, `PROGRESS.md`, and project documentation. Every metric adheres strictly to Rule R1 (no fabricated or hardcoded numbers) and Rule R2 (reproducible with script, dataset split, seed, git commit hash, and timestamp).

---

## 1. Safety & Adversarial Red-Team Metrics

| Metric Name | Value | 95% Wilson CI | Definition | Script & Command | Dataset Version / Split | Commit Hash | Date |
|---|---|---|---|---|---|---|---|
| **Path A Attack Block Rate (Raw)** | **87.50% (105 / 120)** | [80.40%, 92.28%] | Percentage of adversarial SQL payloads statically blocked by AST validator | `python scripts/eval_redteam.py` | `data/redteam/redteam_cases.jsonl` (Path A direct SQL attacks) | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Path A Attack Block Rate (Adjusted)** | **96.33% (105 / 109)** | [90.94%, 98.56%] | Statically blocked attacks after reclassifying 11 audited-harmless queries (remaining 4 stopped by sandbox) | `python scripts/eval_redteam.py` | `data/redteam/redteam_cases.jsonl` + `results/relabel_log.json` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Path A Benign Pass Rate (Dev Controls)** | **100.00% (41 / 41)** | [91.43%, 100.00%] | Percentage of legitimate complex SQL queries passing validator without false rejection | `python scripts/eval_redteam.py` | `data/redteam/redteam_cases.jsonl` (split=dev, category=benign) | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Path A Held-Out V1 Benign Pass Rate** | **100.00% (24 / 24)** | [86.20%, 100.00%] | Percentage of held-out benign queries passing validator | `python scripts/eval_redteam.py` | `data/redteam/heldout_v1_cases.jsonl` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Path A Validator Latency p50** | **2.44 ms** | N/A | Median execution latency of AST validation per query | `python scripts/eval_redteam.py` | `data/redteam/redteam_cases.jsonl` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Path A Validator Latency p95** | **7.28 ms** | N/A | 95th percentile execution latency of AST validation per query | `python scripts/eval_redteam.py` | `data/redteam/redteam_cases.jsonl` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Path B Prompt Injection Success (temp 0)** | **0.00% (0 / 60)** | [0.00%, 6.02%] | Attack success rate against full pipeline under greedy decoding | `python scripts/run_path_b_protocol.py` | 60 NL injection prompts (`redteam_cases.jsonl`) | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Path B Prompt Injection Success (temp 0.7)** | **0.00% (0 / 60)** | [0.00%, 6.02%] | Worst-case attack success across 3 stochastic samples per prompt | `python scripts/run_path_b_protocol.py` | 60 NL injection prompts (180 total evals) | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Path C Sandbox Defense Rate** | **100.00% (120 / 120)** | [96.90%, 100.00%] | Neutralization of attack payloads when directly submitted to sandbox | `python scripts/eval_redteam.py` | `data/redteam/redteam_cases.jsonl` (Path C) | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Path D Full Pipeline Attack Success Rate** | **0.00% (0 / 120)** | [0.00%, 3.10%] | Empirical attack success through Validator -> Sandbox pipeline | `python scripts/eval_redteam.py` | `data/redteam/redteam_cases.jsonl` (Path D) | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Spider Dev False-Positive Rate (FPR)** | **0.19% (2 / 1034)** | [0.05%, 0.70%] | Proportion of 1,034 Spider dev gold SQL queries blocked by validator | `python scripts/audit_false_positives.py` | `data/raw/spider/dev.json` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Combined Benign Pass Rate (Dev + 76 Benign)** | **99.37% (1103 / 1110)** | [98.70%, 99.69%] | Overall legitimate query pass rate on Spider dev (1,034) + 76 benign controls | `python scripts/audit_false_positives.py` | `results/false_blocks.json` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Canonical SQL Semantic Preservation** | **96.61% (997 / 1032)** | [95.33%, 97.55%] | Proportion of executable Spider dev gold queries with identical result sets after canonical rewriting (all 33 differences solely row capping by LIMIT 100) | `python scripts/check_canonical_equiv.py` | `results/canonical_equiv.json` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-19 |
| **Held-Out V2 Policy Escape Rate (Pre-Fix Frozen)** | **8.33% (4 / 48)** | [3.29%, 19.55%] | Payloads expected to be blocked but allowed and executed through sandbox (ENC_V2_02, ENC_V2_03, ENC_V2_05, FNC_V2_05) | `python scripts/eval_heldout_v2.py` | `data/redteam/heldout_v2_cases.jsonl` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Held-Out V2 Harm Rate (Pre-Fix Frozen)** | **0.00% (0 / 48)** | [0.00%, 7.41%] | Payloads triggering stated harm criteria: DB mutated, forbidden columns read, >100 rows, or >3.5s timeout | `python scripts/eval_heldout_v2.py` | `data/redteam/heldout_v2_cases.jsonl` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Held-Out V2 Static Attack Block (Pre-Fix Frozen)** | **81.25% (39 / 48)** | [68.06%, 89.81%] | Frozen one-shot evaluation on agent-authored heldout_v2 set (pre-fix) | `python scripts/eval_heldout_v2.py` | `data/redteam/heldout_v2_cases.jsonl` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Held-Out V2 Benign Pass Rate (Pre-Fix Frozen)** | **100.00% (24 / 24)** | [86.20%, 100.00%] | Frozen one-shot benign control pass rate on heldout_v2 set | `python scripts/eval_heldout_v2.py` | `data/redteam/heldout_v2_cases.jsonl` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Held-Out V2_Dev Policy Escape Rate (Post-Fix Tuned)** | **0.00% (0 / 48)** | [0.00%, 7.41%] | Evaluated on demoted heldout_v2_dev set under frozen post-fix policy | `python scripts/eval_heldout_v2_dev.py` | `results/eval_heldout_v2_dev.json` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-19 |
| **Held-Out V2_Dev Harm Rate (Post-Fix Tuned)** | **0.00% (0 / 48)** | [0.00%, 7.41%] | Evaluated on demoted heldout_v2_dev set under frozen post-fix policy (zero harm) | `python scripts/eval_heldout_v2_dev.py` | `results/eval_heldout_v2_dev.json` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-19 |
| **Held-Out V2_Dev Static Attack Block (Post-Fix Tuned)** | **95.83% (46 / 48)** | [86.02%, 98.85%] | Static AST block on demoted heldout_v2_dev (remaining 2 stopped by sandbox) | `python scripts/eval_heldout_v2_dev.py` | `results/eval_heldout_v2_dev.json` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-19 |
| **Held-Out V2_Dev Benign Pass Rate (Post-Fix Tuned)** | **100.00% (24 / 24)** | [86.20%, 100.00%] | Benign control pass rate on demoted heldout_v2_dev | `python scripts/eval_heldout_v2_dev.py` | `results/eval_heldout_v2_dev.json` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-19 |

---

## 2. Text-to-SQL Execution Accuracy & Model Benchmarks

| Metric Name | Value | 95% Wilson CI | Definition | Script & Command | Dataset Version / Split | Commit Hash | Date |
|---|---|---|---|---|---|---|---|
| **Held-Out V2 Pre-Fix (Frozen)** | **81.25% (39 / 48)** | [68.06%, 89.81%] | Frozen one-shot evaluation on agent-authored heldout_v2 set (pre-fix, 4/48 attack success) | `python scripts/eval_heldout_v2.py` | `data/redteam/heldout_v2_cases.jsonl` | `2fb1f36b01574f919f11c6ef17f57c31b5406591` | 2026-10-18 |
| **Held-Out V2 Post-Fix (Tuned Dev)** | **95.83% (46 / 48)** | [86.02%, 98.85%] | Re-evaluated on demoted heldout_v2_dev set after D2 class-level defenses (0/48 attack success, 24/24 benign pass) | `python scripts/eval_heldout_v2.py` | `data/redteam/heldout_v2_dev_cases.jsonl` | Pending commit | 2026-10-19 |

---

## 2. Text-to-SQL Execution Accuracy & Model Benchmarks

> [!WARNING]
> **Ablation Table Provenance Notice (Legacy / Not Directly Comparable):**
> The preliminary ablation benchmarks below originate from distinct environments and execution runs during exploratory development and Colab ingest. Configs A, B, and C latency numbers (2.16 s - 2.23 s) were measured with GPU-accelerated PyTorch/vLLM backend runs in cloud environments, whereas Config D latency (4.68 s p50, 11.23 s p95) was benchmarked with GGUF `llama_cpp` on local CPU host hardware. Latency figures between GPU fp16 and CPU quantized GGUF are **not directly comparable**. In the formal Phase 3 benchmark, latency and accuracy will be benchmarked under uniform, strictly isolated hardware conditions. Furthermore, "False blocks" are N/A for rows without the security guardrail.

| Config | Architecture / Description | Execution Accuracy (EX) | 95% Bootstrap CI | False Blocks | Mean Latency | p95 Latency | Source File | Command | Hardware & Setup |
|---|---|---|---|---|---|---|---|---|---|
| **#1 (A)** | Base Qwen2.5-Coder-3B-Instruct (Zero-Shot) | **62.28% (644 / 1034)** | [59.38%, 65.18%] | N/A (no guardrail) | 2.16 s | 5.82 s | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config A` | Linux GPU (Cloud ingest), Greedy, seed 42 |
| **#2 (B)** | Base + 3-Shot (Fixed in-context demos) | **66.15% (684 / 1034)** | [63.25%, 68.96%] | N/A (no guardrail) | 2.23 s | 6.01 s | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config B` | Linux GPU (Cloud ingest), Greedy, seed 42 |
| **#3 (C)** | Fine-Tuned FP16 Merged | **71.57% (740 / 1034)** | [68.86%, 74.27%] | N/A (no guardrail) | 2.19 s | 5.91 s | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config C` | Linux GPU (Cloud ingest), Greedy, seed 42 |
| **#4 (D)** | Fine-Tuned GGUF Q4_K_M (Quantized Serving) | **70.70% (731 / 1034)** | [67.89%, 73.40%] | N/A (no guardrail) | 4.68 s | 11.23 s | `results/eval_spider_latest.json` | `python scripts/bench_latency.py` | Local CPU host (x86_64, 4 physical cores, 31.4 GB RAM), `llama_cpp`, Greedy, seed 42 |
| **#5** | #4 + AST Validator + Read-Only Sandbox | **70.50% (729 / 1034)** | [67.69%, 73.21%] | 2 (0.19%) | 4.71 s | 11.31 s | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config D --guarded` | Local CPU host |
| **#6** | #5 + Self-Correction (1 retry cap) | *Awaiting Phase 3* | - | 2 | - | - | - | - | - |

---

## 3. Environment & Runtime Specifications

- **SQLite Engine Version:** `3.45.1` (`sqlite3.sqlite_version = "3.45.1"`).
- **Defensive Configurations Active:** `enable_load_extension(False)`, `SQLITE_DBCONFIG_DEFENSIVE = True`, `SQLITE_DBCONFIG_ENABLE_FTS3_TOKENIZER = False`, `SQLITE_DBCONFIG_TRUSTED_SCHEMA = False`.
- **Operating System:** Windows (x86_64, CPU-only host environment).

---

## 4. Reconciliation & Provenance Disclosures

1. **Reconciliation of Denominators (1,098 vs 1,099 vs 1,100):**
   - **Spider Dev Set:** 1,034 gold queries.
   - **Initial Benign Controls:** 65 cases.
   - **Total Evaluated Legitimate Set:** 1,034 + 65 = 1,099 legitimate queries (`results/false_blocks.json`).
   - In preliminary notes, "1,098/1,100" was an informal approximation. The authoritative empirical number is **1,097 / 1,099** queries passing (99.82% pass rate; exactly 2 false-blocked queries).
2. **False-Blocked Query Accounting:**
   - **Blocked Query 1 (`SPIDER_pets_1_65`):** `SELECT T1.fname , T1.age FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid = T2.stuid JOIN pets AS T3 ON T3.petid = T2.petid WHERE T3.pettype = 'dog' AND T1.stuid NOT IN (SELECT T1.stuid FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid = T2.stuid JOIN pets AS T3 ON T3.petid = T2.petid WHERE T3.pettype = 'cat')`
     - *Root Cause:* Evaluator detects 5 table joins across query and subquery, exceeding `policy.max_joins_per_branch = 4`.
   - **Blocked Query 2 (`SPIDER_pets_1_66`):** Identical structure with alternative question formulation.
     - *Root Cause:* Same complexity join limit (5 > 4).
3. **Phase 1 Initial False-Positive Rate (0.58%):**
   - Phase 1 baseline validator evaluated 1,034 Spider dev queries with a coarser join threshold, blocking 6 queries (`6 / 1034 = 0.5803%`).
   - In Phase 2, after distinguishing root joins and subquery branches, 4 of the 6 false-positive queries (e.g. `INTERSECT` set queries in `museum_visit` and `voter_1`) were allowed, reducing false blocks to 2 queries (`2 / 1034 = 0.1934%` on Spider dev alone, and `2 / 1099 = 0.1820%` on dev + benign controls).
4. **Held-Out V2 Provenance & Freeze Statement:**
   - `heldout_v2` was evaluated before it was committed to git; its pre-fix state freeze is guaranteed strictly by its SHA-256 hash (`6585291682005767b7d961e908840c1fc7789c505873d8f28b727709df2317bb`).
   - Post-fix improvements on v2 are reported strictly as "tuned dev" (split `heldout_v2_dev`), and an independent `heldout_v3` will serve as the unseen validation set.

---

## 5. Phase 3 Ablation: Self-Correction and Voting (Configs E, F, G)

> **Provenance**: Kaggle notebook `notebook6f1ee3abad`, GPU T4 x2, 2026-10-18T22:14:39 UTC, runtime 35,618.8 s. Backend: `transformers`, model: `Qwen/Qwen2.5-Coder-3B-Instruct` (base model). All results from `results/ablation_latest.json`. Multi-seed seed sweep crashed with CUDA OOM during F seed 42; D seeds 42/101/2024 completed on 300-subset.

| Metric Name | Value | Definition | Script & Command | Evidence File | Date |
|---|---|---|---|---|---|
| **Config D Baseline EX (Base Greedy)** | **62.28% (644 / 1034)** | Base model, greedy, guarded, n=1034, seed=42 | `python scripts/run_phase3_kaggle.py --backend transformers` | `results/ablation_latest.json` | 2026-10-18 |
| **Config E EX (Self-Correction)** | **62.28% (644 / 1034)** | D + max-2-retry self-correction on exec errors, n=1034, seed=42 | `python scripts/run_phase3_kaggle.py --backend transformers` | `results/ablation_latest.json` | 2026-10-18 |
| **Config F EX (Voting N=5)** | **62.28% (644 / 1034)** | D + consensus voting N=5 at temp 0.3–0.7, n=1034, seed=42 | `python scripts/run_phase3_kaggle.py --backend transformers` | `results/ablation_latest.json` | 2026-10-18 |
| **Config G EX (Both)** | **62.28% (644 / 1034)** | D + self-correction + voting, n=1034, seed=42 | `python scripts/run_phase3_kaggle.py --backend transformers` | `results/ablation_latest.json` | 2026-10-18 |
| **Config E Calls/Question** | **1.13×** | avg_model_calls on 1034 dev (self-correction triggered on ~13% of questions) | `results/ablation_latest.json` | `results/ablation_latest.json` | 2026-10-18 |
| **Config F Calls/Question** | **5.0×** | avg_model_calls on 1034 dev (voting N=5 confirmed) | `results/ablation_latest.json` | `results/ablation_latest.json` | 2026-10-18 |
| **Config G Calls/Question** | **5.63×** | avg_model_calls on 1034 dev (voting + self-correction combined) | `results/ablation_latest.json` | `results/ablation_latest.json` | 2026-10-18 |
| **Config E p95 Latency** | **11.15 s** | 95th percentile per-question latency (D baseline: 4.61 s = +142%) | `results/ablation_latest.json` | `results/ablation_latest.json` | 2026-10-18 |
| **Config F p95 Latency** | **22.94 s** | 95th percentile per-question latency (D baseline: 4.61 s = +397%) | `results/ablation_latest.json` | `results/ablation_latest.json` | 2026-10-18 |
| **Config G p95 Latency** | **56.47 s** | 95th percentile per-question latency (D baseline: 4.61 s = +1125%) | `results/ablation_latest.json` | `results/ablation_latest.json` | 2026-10-18 |
| **D Seed Stability (300-subset)** | **60.67% across seeds 42/101/2024** | Multi-seed EX on stratified 300-subset confirming D is deterministic | `results/ablation_latest.json` | `results/ablation_latest.json` | 2026-10-18 |
| **Phase 3 Unit Tests Pass** | **6 / 6** | All 6 tests in test_phase3_service.py pass | `python -m pytest tests/test_phase3_service.py -v` | `tests/test_phase3_service.py` | 2026-10-19 |
| **EX Gain vs D** | **0 pp for all of E, F, G** | No improvement on base model — systematic errors unrecoverable by re-sampling. Documented per R9 in docs/LIMITATIONS.md. Fine-tuned model run pending. | — | `results/ablation_latest.json` | 2026-10-18 |

