# Text-to-SQL Assistant: Comprehensive Project Audit & Step-by-Step Completion Guide

**Date:** October 18, 2026  
**Project:** Fine-Tuned Text-to-SQL Assistant (QLoRA) with Safe LLM Serving  
**Repository:** `AshokSingodia-Codes/fine-tuned-text2sql`  
**Current Status:** Nearly Complete (65% Production-Ready, 44/44 Green Tests)

---

## Part 1: Architecture & Current State Summary

### System Overview
This project provides a robust, safe Text-to-SQL system translating natural language questions into executable SQLite queries against relational databases (Spider 1.0 benchmark). It incorporates:
1. **Model Fine-Tuning**: `Qwen2.5-Coder-3B-Instruct` fine-tuned via 4-bit NF4 QLoRA for 2 epochs (974 steps), with prompt-completion loss masking (`-100`). The adapter is saved in `models/qlora_adapter/adapter_model.safetensors` (119.8 MB).
2. **SQL Safety Guardrails**: Multi-layered defense featuring:
   - AST validation via `sqlglot` (blocking DDL/DML, multi-statements, comment smuggling, excessive joins, and injecting `LIMIT 100`).
   - Read-only execution sandbox using SQLite URI `mode=ro`, `PRAGMA query_only = ON`, SQLite C-level authorizer callbacks, and 3.0s query timeout interrupts.
3. **Consensus Decoding & Self-Correction**: Samples $N=5$ candidate queries, repairs execution runtime failures via conversational prompt retries, and groups results by normalized multiset output for majority voting.
4. **FastAPI Serving & React UI**: Full REST API with rate-limiting, audit logging, Prometheus metrics, and a modern React 19 + Vite + Tailwind CSS interface.

---

## Part 2: Key Findings & Bug Inventory

Before proceeding to advanced phases, the following issues in the existing codebase must be resolved:

| ID | Issue | Location | Impact | Fix |
|---|---|---|---|---|
| **BUG-01** | Database Discovery Glob Bug | `src/t2s/serving/dbs.py:19` | `self.db_base_dir.glob("*.sqlite")` fails because Spider databases are stored in subdirectories (`<db_id>/<db_id>.sqlite`). `/v1/databases` returns `[]`. | Change glob to search subdirectories `*/*.sqlite` or iterate directory folders. |
| **BUG-02** | Hardcoded Mock Backend in FastAPI | `src/t2s/serving/app.py:37` | `service = Text2SQLService(backend_name="mock")` ignores `os.getenv("MODEL_BACKEND")` and `configs/serve.yaml`. | Read `os.getenv("MODEL_BACKEND", "mock")` and pass to `Text2SQLService`. |
| **BUG-03** | Stale Rewritten SQL in Retries | `src/t2s/serving/service.py:222` | Self-correction retries use `verdict.rewritten_sql` (initial failed query) instead of `retry_verdict.rewritten_sql`. | Update candidate record to use `retry_verdict.rewritten_sql`. |
| **BUG-04** | Missing Docker Nginx Reverse Proxy | `frontend/Dockerfile:8-12` | Nginx serves static HTML on port 80 with no proxy for `/v1/`, breaking `docker compose up`. | Add `nginx.conf` with `proxy_pass http://api:8000;` for `/v1/`, `/health`, and `/ready`. |
| **BUG-05** | Backend Kwarg Mismatch | `src/t2s/serving/service.py:31` vs `src/t2s/gen/backends.py:169` | `service.py` passes `model_name=model_path`, while `llama_cpp` expects `model_path`. | Standardize parameter passing in `get_backend`. |
| **BUG-06** | Prometheus Metrics Never Incremented | `src/t2s/serving/metrics.py:5-26` | Prometheus counters and histograms are defined but never called in `app.py` or `service.py`. | Add instrumentation hooks inside `process_query` and API endpoints. |
| **SEC-01** | `SELECT *` Column Denylist Bypass | `src/t2s/safety/validator.py:106-110` | `SELECT *` generates an `exp.Star` node, bypassing column denylists and returning sensitive columns (e.g. `password`). | Inspect schema tables when `*` is present and block if denied columns exist. |
| **OPS-01** | Heavy Archive Files in Workspace | `.gitignore` | `kaggle_bundle.zip` (318MB), `phase1_bundle.zip` (205MB), and `t2s_outputs-*.zip` (1.98GB) are not ignored. | Add `*.zip` to `.gitignore`. |

---

## Part 3: Step-by-Step Completion Roadmap

Follow these 4 sequential milestones to complete the system from its current 65% mark to 100% production-ready.

```
+-----------------------------------------------------------------------+
| MILESTONE 1: Critical Bug Fixes & Wiring (Low Effort, Immediate)     |
| - Fix dbs.py database discovery                                       |
| - Wire MODEL_BACKEND environment variable in app.py                   |
| - Fix consensus retry rewritten_sql bug in service.py                 |
| - Add nginx.conf reverse proxy for frontend Docker container          |
| - Add *.zip to .gitignore                                             |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
| MILESTONE 2: Weight Merging & Real Model Serving                     |
| - Merge QLoRA adapter into base model (generate models/merged_model/) |
| - Quantize merged weights to GGUF Q4_K_M via llama.cpp                |
| - Verify local serving with llama-cpp-python or Transformers backend  |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
| MILESTONE 3: Empirical Spider Dev Benchmark (Phase 1 Execution)       |
| - Run scripts/eval_spider.py with real model across 1,034 questions   |
| - Produce real results/eval_spider_latest.json                        |
| - Run scripts/bench_latency.py for p50/p95/p99 serving latency        |
| - Generate comparative figures and update docs/EVALUATION.md          |
+-----------------------------------+-----------------------------------+
                                    |
                                    v
+-----------------------------------------------------------------------+
| MILESTONE 4: Security & Governance Hardening (Phases 2 & 6)           |
| - Close SELECT * sensitive column bypass in AST validator             |
| - Expand Red-Team suite from 60 to 150+ adversarial cases             |
| - Add asynchronous SQLite audit logging to avoid DB locking           |
| - Add secret scanning to GitHub Actions CI                            |
+-----------------------------------------------------------------------+
```

---

## Part 4: Detailed Implementation Guide

### Milestone 1: Critical Bug Fixes & Wiring

#### 1. Fix Database Discovery (`src/t2s/serving/dbs.py`)
In `DatabaseRegistry.list_databases`, search nested Spider directory layouts:
```python
# Check both nested Spider directories and flat sqlite files
for p in self.db_base_dir.glob("*/*.sqlite"):
    db_id = p.parent.name
    info = self.get_db_info(db_id)
    if info:
        dbs.append(info)
for p in self.db_base_dir.glob("*.sqlite"):
    db_id = p.stem
    if not any(d["db_id"] == db_id for d in dbs):
        info = self.get_db_info(db_id)
        if info:
            dbs.append(info)
```

#### 2. Wire Dynamic Backend in Serving App (`src/t2s/serving/app.py`)
Read environment variable `MODEL_BACKEND`:
```python
backend_type = os.getenv("MODEL_BACKEND", "mock")
model_path = os.getenv("MODEL_PATH", "models/qlora_adapter")
service = Text2SQLService(backend_name=backend_type, model_path=model_path)
```

#### 3. Fix Consensus Retry SQL (`src/t2s/serving/service.py`)
In `process_query_consensus`:
```python
"rewritten_sql": retry_verdict.rewritten_sql if retried else verdict.rewritten_sql,
```

#### 4. Add Nginx Reverse Proxy for Docker Deployment
Create `frontend/nginx.conf`:
```nginx
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }

    location ~ ^/(v1|health|ready|metrics) {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```
Update `frontend/Dockerfile` to copy `nginx.conf` into `/etc/nginx/conf.d/default.conf`.

---

### Milestone 2: Weight Merging & GGUF Quantization

#### 1. Merge QLoRA Weights to FP16
```bash
python scripts/merge_adapter.py \
  --adapter-dir models/qlora_adapter \
  --output-dir models/merged_model \
  --base-model Qwen/Qwen2.5-Coder-3B-Instruct
```
This produces `models/merged_model/model.safetensors` (~6.2 GB).

#### 2. Quantize to GGUF Q4_K_M
Using `llama.cpp`:
```bash
# Convert to FP16 GGUF
python third_party/llama.cpp/convert_hf_to_gguf.py models/merged_model --outfile models/merged_fp16.gguf

# Quantize to 4-bit Medium (Q4_K_M) ~1.9 GB
./third_party/llama.cpp/build/bin/llama-quantize models/merged_fp16.gguf models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf Q4_K_M
```

---

### Milestone 3: Real Evaluation (Execution Accuracy)

Run the automated evaluation across all 1,034 Spider dev queries:
```bash
# Run real evaluation for Config C (Fine-Tuned Adapter) on GPU
python scripts/eval_spider.py \
  --backend transformers \
  --model-path models/merged_model \
  --config C \
  --output-dir results

# Benchmark serving latency (p50/p95/p99) on 200 queries
python scripts/bench_latency.py \
  --backend transformers \
  --model-path models/merged_model \
  --limit 200 \
  --output-dir results
```
This automatically produces:
- `results/eval_spider_latest.json`
- `results/latency_latest.json`
- Updates `docs/EVALUATION.md` via `python scripts/make_eval_doc.py`
- Generates `results/figures/ex_comparison.png` via `python scripts/make_figures.py`

---

### Milestone 4: Security Hardening & Production Polish

1. **Cover `SELECT *` in Validator**:
   In `src/t2s/safety/validator.py`, when an `exp.Star` is parsed, fetch table schema columns and reject if the queried table contains restricted columns.
2. **Prometheus Metrics Instrumentation**:
   Increment `REQUEST_COUNT`, observe `LATENCY_HISTOGRAM`, and increment `BLOCKED_COUNT` inside `src/t2s/serving/app.py`.
3. **Async Audit Logging**:
   Refactor `AuditLogger` in `src/t2s/serving/audit.py` to use an asynchronous worker to prevent SQLite lock contention.
4. **GitHub Actions Security Check**:
   Add `gitleaks` step to `.github/workflows/ci.yml`.
