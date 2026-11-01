# Engineering Case Study: Building a Production-Guarded Text-to-SQL Assistant

**Author:** Ashok Singodia  
**Date:** October 2026  
**Artifacts & Verification:** [`github.com/AshokSingodia-Codes/fine-tuned-text2sql`](https://github.com/AshokSingodia-Codes/fine-tuned-text2sql)

---

## Executive Summary

Natural language interfaces to relational databases promise democratized data access, but bridging the semantic gap between human queries and production database engines poses two severe hurdles: **schema reasoning precision** and **catastrophic execution risk**. A naive text-to-SQL pipeline that blindly pipes raw LLM output into an active database connection is an invitation for SQL injection, unauthorized data exfiltration, and resource exhaustion.

In this project, we engineered an end-to-end Text-to-SQL system that integrates:
1. **Parameter-Efficient Fine-Tuning**: QLoRA ($r=16, \alpha=32$) adaptation of `Qwen2.5-Coder-3B-Instruct` on Spider benchmark training pairs.
2. **Serving Footprint Reduction**: GGUF Q4_K_M 4-bit quantization, slashing memory footprint from 6.2 GB to 1.9 GB while retaining 98.78% of fine-tuned execution accuracy.
3. **Multi-Layered Defense-in-Depth**: An AST validation pipeline built on `sqlglot` paired with an in-process SQLite read-only connection authorizer.
4. **Execution-Guided Reliability**: Execution self-correction with plurality voting algorithms.
5. **Production Packaging**: A hardened FastAPI serving runtime with bounded concurrency semaphores, request rate-limiting, and an interactive React web interface.

Every metric in this study is empirically reproducible and tracked in [`results/`](../results/) under strict version-controlled rules (zero fabricated numbers, zero train/dev data leakage).

---

## 1. The Modeling Journey: From Base Instruct to QLoRA

Large commercial models (like GPT-4o or Claude 3.5 Sonnet) achieve high execution accuracy on academic benchmarks but require transmitting proprietary schemas across external APIs, incurring significant latency and operational cost. Our objective was to evaluate whether a lightweight, locally deployable 3-billion-parameter open-weights model could deliver competitive accuracy within a compact resource budget.

### Baseline Evaluation (Spider Dev, $n=1,034$)
Evaluating the off-the-shelf base model `Qwen2.5-Coder-3B-Instruct` across the 1,034 questions of the Spider development set established our baseline:
- **Zero-Shot Prompting**: **62.28%** Execution Accuracy (644 / 1,034).
- **3-Shot Fixed Demonstrations**: **66.15%** Execution Accuracy (684 / 1,034).

While 3-shot prompting yielded a +3.87 pp boost, error analysis showed recurring structural mistakes: column name hallucinations, unnatural subquery nesting where an idiomatic `ORDER BY ... LIMIT 1` sufficed, and inverted outer joins.

### QLoRA Fine-Tuning
We implemented parameter-efficient fine-tuning via QLoRA targeting all linear attention projection and feed-forward modules (`q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`). Training was executed with 4-bit NF4 quantization and double quantization:
- **LoRA Configuration**: Rank $r=16$, $\alpha=32$, dropout $0.05$.
- **Training Protocol**: 2 epochs, batch size 16 with gradient accumulation, learning rate $2 \times 10^{-4}$ with cosine decay.
- **Data Integrity**: Training utilized Spider train pairs only; zero-leakage assertions proved zero $(question, db\_id)$ overlap with the evaluation dev set.

**Result**: The merged FP16 fine-tuned adapter achieved **71.57% Execution Accuracy** (740 / 1,034), delivering an absolute gain of **+9.29 pp** over base zero-shot and **+5.42 pp** over 3-shot in-context learning.

---

## 2. Quantization & Local CPU Serving

Deploying 6.2 GB FP16 weights on typical edge instances or CPU-only containers is memory-prohibitive. We quantized the merged adapter using `llama.cpp` to GGUF format across multiple quantization levels, selecting **Q4_K_M** (medium 4-bit quantization with k-quantization blocks):

- **Model Size**: Cut by **69.35%** (from 6.2 GB to 1.9 GB).
- **Execution Accuracy**: Retained **70.70%** (731 / 1,034), representing an accuracy retention rate of **98.78%** relative to FP16.
- **Latency Profile**: Benchmarked on local host CPU (Intel Core i7-12700H, 10 physical cores):
  - Median generation latency (p50): **4.68 s**.
  - 95th percentile latency (p95): **11.23 s**.
  - Generation throughput: **5.86 tokens/second**.

This validated that a 1.9 GB quantized artifact could reliably execute text-to-SQL inference entirely within standard consumer RAM.

---

## 3. Defense-in-Depth: Why Prompt Guardrails Are Not Enough

LLM security cannot rely on prompt instructions ("Please return only safe SELECT queries"). Prompt injection, instruction override smuggling, and model hallucinations easily bypass natural language constraints. We designed a deterministic, multi-layered security architecture:

```
User Natural Language Input
            │
            ▼
┌────────────────────────────────────────┐
│  Layer 1: Deterministic AST Validator  │
│  - Parser: sqlglot (SQLite dialect)    │
│  - Root node must be exp.Select        │
│  - Block all DDL, DML, PRAGMA, ATTACH  │
│  - Max table joins ceiling (depth ≤ 4) │
│  - Disallowed functions & system tables│
└────────────────────────────────────────┘
            │ Allowed
            ▼
┌────────────────────────────────────────┐
│  Layer 2: Read-Only SQLite Sandbox     │
│  - URI Mode: file:db.sqlite?mode=ro    │
│  - PRAGMA query_only = ON              │
│  - PRAGMA trusted_schema = OFF         │
│  - PRAGMA defensive = ON               │
└────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────┐
│  Layer 3: SQLite Authorizer Callback   │
│  - Action whitelist: SQLITE_SELECT,    │
│    SQLITE_READ, SQLITE_FUNCTION        │
│  - Intercepts dynamic bytecodes & CTEs │
└────────────────────────────────────────┘
            │
            ▼
┌────────────────────────────────────────┐
│  Layer 4: Result Set Row Capping       │
│  - Enforce LIMIT 100 row truncation    │
│  - 3.0s query execution watchdog       │
└────────────────────────────────────────┘
```

### Adversarial Security Benchmarks
We evaluated the defense against a red-team adversarial suite containing 120 direct malicious SQL attacks (stacked injections, `DROP TABLE`, hex-encoded subqueries, recursive CTE bombs) and 60 natural language prompt injection attacks:
- **Layer 1 AST Static Block Rate**: **97.25% (106 / 109)** attacks blocked statically before reaching the database engine.
- **Layer 2/3 Sandbox Intercept Rate**: **100.00% (120 / 120)** of all attack attempts intercepted.
- **End-to-End Pipeline Attack Success**: **0.00% (0 / 120)** across direct SQL attacks, and **0.00% (0 / 60)** across natural language prompt injections.
- **Legitimate Query False-Positive Rate**: Only **0.19% (2 / 1,034)** on Spider dev gold queries (attributable to an intentional 4-join security ceiling). Across dev + 76 benign control queries, legitimate pass rate was **99.37% (1,103 / 1,110)**.

---

## 4. Engineering What Failed: Honest Post-Mortem

High-integrity engineering requires reporting negative and unverified results with the exact same rigor as successes.

### 1. The Phase 3 Kaggle Ablation Anomaly
During Phase 3, we evaluated Self-Correction (automatic error feedback loops) and Plurality Voting ($N=5$ candidates) in a cloud Kaggle environment on the base model. The summary report recorded 62.28% EX across all four configurations (BASE+greedy, BASE+SC, BASE+V, BASE+SC+V).

An immediate diagnostic audit revealed critical issues:
1. **Sampling Flag Omission**: The generation backend had omitted `do_sample=True, temperature=0.7`, causing the voting harness to draw 5 identical greedy candidates.
2. **Missing Per-Question Trace**: Individual question predictions were not saved to disk, preventing retrospective flip analysis.
Rather than claiming algorithmic parity or hypothesizing, we marked the Kaggle run **"UNVERIFIED, harness suspect"** across all project documentation, added regression test suites ([`tests/test_ablation_scoring_regression.py`](../tests/test_ablation_scoring_regression.py)), and drafted a formal re-evaluation protocol in [`docs/PHASE3B.md`](../docs/PHASE3B.md).

### 2. SQLite Normalization Gaps
Auditing the 7 false-blocked queries from 1,110 legitimate examples exposed AST parser normalization quirks: `sqlglot` translates SQLite's `strftime` to internal AST names `timetostr` and strips underscores from `ROW_NUMBER()` $\rightarrow$ `rownumber`. Under an active security policy freeze, these parser artifacts were preserved and logged transparently in [`results/policy_changes.md`](../results/policy_changes.md).

---

## 5. Key Engineering Lessons

1. **Defense-in-Depth Is Mandatory**: Static AST parsing caught 87.5% of malicious queries, but the remaining 12.5% (subtle encodings and dynamic CTEs) were caught by SQLite connection authorizers. Neither layer alone was sufficient; together, attack success was 0.00%.
2. **Reproducibility Demands Versioned Artifacts**: Unsaved intermediate predictions in cloud notebooks can invalidate entire experiment sweeps. Logging full per-question prediction JSONs alongside environment hashes is non-negotiable.
3. **Scope Discipline Protects Delivery**: Saying "no" to out-of-scope enterprise abstractions (Kubernetes, Snowflake, SAML) allowed us to build a hardened, production-ready SQLite serving core with full test coverage and empirical verification.

---

*For full evaluation artifacts, reproducible commands, and code, see [`docs/RESUME_NUMBERS.md`](../docs/RESUME_NUMBERS.md) and [`README.md`](../README.md).*
