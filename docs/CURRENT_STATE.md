# Project Current State Audit & System Inventory
**Date:** October 2, 2026  
**Commit / Tag:** `v0.1-poc`  
**Test Suite Status:** 40 / 40 Passing Cleanly (`pytest -q`)  
**train_examples_used:** `7784` (Exact lines in `data/processed/train.jsonl` used for QLoRA fine-tuning)  

---

## 1. Module Inventory & Functionality

### A. Data & Prompt Engineering (`src/t2s/data/`)
- `spider_loader.py`: Typed loaders for Spider dataset (`train_spider.json`, `dev.json`, `tables.json`).
- `schema.py`: Schema DDL extractor reading SQLite files to generate `CREATE TABLE` DDL statements with primary/foreign keys and optional sample rows.
- `prompts.py`: Deterministic chat-format prompt builder using Qwen2.5 chat template.
- `split.py`: Database-level validation splitting holding out 10% of training databases (`db_id`) to prevent data leakage.
- `build_dataset.py`: Dataset builder creating JSONL files in prompt-completion format.

### B. SQL Safety & Execution Guardrails (`src/t2s/safety/`)
- `validator.py`: `sqlglot` AST parser for SQLite dialect. Validates root statement (`SELECT`/`UNION`), checks forbidden keywords, walked table/column denylists, max joins limit, and injects `LIMIT`.
- `policy.py`: YAML-driven safety policy settings manager.
- `executor.py`: Safe SQLite read-only executor using `file:db?mode=ro`, `PRAGMA query_only = ON`, SQLite C-level authorizer callbacks (`SQLITE_SELECT` only), and 3.0s progress handler timeouts.
- `redteam_cases.py`: 60 adversarial red-team test cases across 6 threat categories.

### C. Serving Backend & API Microservice (`src/t2s/serving/`)
- `app.py`: FastAPI endpoints (`/v1/query`, `/v1/validate`, `/v1/feedback`, `/health`, `/ready`, `/metrics`).
- `service.py`: Service orchestrator integrating prompt builder, model inference backends, AST validator, safe executor, self-correction retries, and consensus voting.
- `dbs.py`: Demo SQLite database registry.
- `schemas.py`: Pydantic v2 validation models for request/response bodies.
- `auth.py`: Token API key header verification.
- `ratelimit.py`: Token bucket rate limiter.
- `audit.py`: SQLite audit logging for request metadata and verdicts.
- `metrics.py`: Prometheus metrics counters and latency histograms.

### D. Model Training & Quantization (`src/t2s/train/`)
- `train_qlora.py`: 4-bit NF4 QLoRA fine-tuning script with label masking using `trl.SFTTrainer` and `peft`.
- `merge.py`: Merges LoRA adapter weights with base FP16 model.

### E. Evaluation & Benchmarking (`src/t2s/eval/` & `src/t2s/gen/`)
- `exec_eval.py`: Fast internal multiset query execution evaluator.
- `official_eval.py`: Wrapper for official `test-suite-sql-eval`.
- `error_analysis.py`: Error categorization (syntax error, wrong aggregation, missing group by, value mismatch, wrong join), generalization slicing, and system diffs.
- `stats.py`: McNemar paired statistical test & bootstrap 95% confidence intervals.
- `backends.py`: Unified inference backend abstraction (`transformers`, `vllm`, `llamacpp`, `mock`).

---

## 2. Test Coverage & Verification

| Test Module | Component Covered | Status |
|---|---|---|
| `test_config.py` | Configuration loader | ✅ Passed |
| `test_schema.py` | Schema DDL extraction | ✅ Passed |
| `test_prompts.py` | Prompt construction | ✅ Passed |
| `test_split.py` | Database-level splitting | ✅ Passed |
| `test_masking.py` | SFT label token masking | ✅ Passed |
| `test_spider_loader.py` | Spider data parsing | ✅ Passed |
| `test_exec_eval.py` | Execution accuracy evaluator | ✅ Passed |
| `test_stats.py` | McNemar & Bootstrap CIs | ✅ Passed |
| `test_error_analysis.py` | Error categorization & slicing | ✅ Passed |
| `test_validator.py` | AST validator rules | ✅ Passed |
| `test_executor.py` | Read-only connection sandbox | ✅ Passed |
| `test_redteam.py` | Adversarial red-team suite | ✅ Passed |
| `test_api.py` | FastAPI endpoint integration | ✅ Passed |

**Total passing unit tests:** 40 / 40.

---

## 3. Known Gaps & Limitations

1. **Benchmark Scope**: Evaluated on Spider 1.0 SQLite databases; true multi-database engine connectors (PostgreSQL/SQLAlchemy) not yet abstracted.
2. **Schema Scale**: Full DDL injected in prompts; large schemas with 50+ tables require vector-based retrieval (Schema RAG).
3. **Data Governance**: PII masking policies and Row-Level Security (RLS) AST rewrites need explicit dedicated modules.
4. **Adversarial Hardening**: Red-team suite consists of 60 cases; expanding to 150+ held-out test cases required in Phase 2.
