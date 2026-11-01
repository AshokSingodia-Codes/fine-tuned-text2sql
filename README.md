# Fine-Tuned Text-to-SQL Assistant (QLoRA) with Safe LLM Serving

[![CI](https://github.com/AshokSingodia-Codes/fine-tuned-text2sql/actions/workflows/ci.yml/badge.svg)](https://github.com/AshokSingodia-Codes/fine-tuned-text2sql/actions)
[![Hugging Face Model](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Model%20Hub-yellow.svg)](https://huggingface.co/Ashoksainibadu/fine-tuned-text2sql)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An end-to-end production text-to-SQL system that translates natural language questions into executable SQLite queries, validates them through AST safety guardrails, executes them within a hardened read-only SQLite sandbox, and returns formatted tabular results.

---

## 1. What the Tool Does

```text
[Question in English] ──> [Fine-Tuned LLM] ──> [Candidate SQL] ──> [AST Validator] ──> [Read-Only SQLite] ──> [Result Table]
```
1. **Natural Language Understanding**: Takes a user's question in plain English along with the database schema DDL.
2. **SQL Generation**: Generates SQLite `SELECT` statements using a fine-tuned `Qwen2.5-Coder-3B-Instruct` model quantized to 4-bit GGUF (`Q4_K_M`).
3. **AST Safety Guardrails**: Validates the query syntax tree before execution using `sqlglot`, blocking destructive operations (`DROP`, `DELETE`, `UPDATE`), comment smuggling, stacked statements, and unauthorized system table scraping.
4. **Read-Only SQLite Sandbox**: Executes approved queries against the database mounted via read-only URI flags (`mode=ro`) and C-level authorizer callbacks.
5. **Tabular Results**: Returns sanitized rows and column headers capped at 100 rows to prevent memory exhaustion.

---

## 2. System Requirements

| Requirement | Specification | Notes |
|---|---|---|
| **Python Version** | Python 3.11+ | Tested and verified on Python 3.12.3. |
| **RAM** | Minimum 6 GB | Tested on a machine with 7.7 GB total RAM. |
| **Disk Space** | ~2.5 GB free space | GGUF quantized model is 1.93 GB (`1,929,902,592` bytes). |
| **Compute** | CPU only | Runs purely on CPU via `llama.cpp` SIMD quantization. No GPU required. |
| **Operating System** | Windows 11 (AMD64) | **Tested on Windows 11**. Linux and macOS environments are untested by the author on this machine (Linux is tested via GitHub Actions CI). |

---

## 3. Quickstart (Copy-Paste Commands)

### a) Clone Repository, Create venv, and Install Dependencies
```bash
git clone https://github.com/AshokSingodia-Codes/fine-tuned-text2sql.git
cd fine-tuned-text2sql

python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### b) Install `llama-cpp-python`

#### Windows Prebuilt CPU Wheel (Recommended)
This is the verified route that installed cleanly without requiring a local C++ compiler:
```bash
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

#### Build From Source (Requires C++ Compiler and CMake)
If compiling directly from source:
```bash
pip install cmake
pip install llama-cpp-python --no-binary llama-cpp-python
```
*Exact error if build tools are missing:*
```text
CMake Error: CMAKE_C_COMPILER not set, after EnableLanguage
CMake Error: CMAKE_CXX_COMPILER not set, after EnableLanguage
error: subprocess-exited-with-error
```

### c) Download the Model
The model weights are hosted publicly on Hugging Face Hub (no Hugging Face token required):
```bash
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Ashoksainibadu/fine-tuned-text2sql', filename='Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf', local_dir='models')"
```

*Automatic Download via Environment Variables:*  
The application is equipped to download model weights automatically at startup if `models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf` is absent and the following environment variables are exported:
```bash
export HF_REPO_ID="Ashoksainibadu/fine-tuned-text2sql"
export GGUF_FILENAME="Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf"
```

### d) Build Frontend (Optional, for Web UI)
If using the Web UI, compile the frontend assets (requires Node.js 18+):
`ash
cd frontend
npm install
npm run build
cd ..
`
*(If Node.js is not installed, the FastAPI REST API and OpenAPI interactive docs at /docs function fully without compiling the frontend).*

### e) Start the Application
Run the FastAPI serving orchestrator:
```bash
# On Linux/macOS:
export MODEL_BACKEND="llama_cpp"
export MODEL_PATH="models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf"
export DB_DIR="db/seeds"
uvicorn src.t2s.serving.app:app --host 127.0.0.1 --port 8000

# On Windows (PowerShell):
$env:MODEL_BACKEND="llama_cpp"
$env:MODEL_PATH="models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf"
$env:DB_DIR="db/seeds"
uvicorn src.t2s.serving.app:app --host 127.0.0.1 --port 8000
```
- **Web UI URL**: `http://127.0.0.1:8000` (port `8000`)
- **API Documentation**: `http://127.0.0.1:8000/docs`

### f) Ask a First Question Against Bundled Chinook Database

#### Web UI
1. Open `http://127.0.0.1:8000` in your browser.
2. Select `chinook` from the database selector dropdown.
3. Enter question: `"How many artists are there?"` and click **Ask Question**.

#### REST API (curl)
```bash
curl -X POST http://127.0.0.1:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"db_id": "chinook", "question": "How many artists are there?"}'
```

#### Real Captured Response:
```json
{
  "request_id": "9ae5b493-01c1-4aa1-a3f2-9e4ac6b14558",
  "db_id": "chinook",
  "question": "How many artists are there?",
  "sql": "SELECT COUNT(*) FROM ARTIST",
  "allowed": true,
  "reasons": [],
  "columns": [
    "COUNT(*)"
  ],
  "rows": [
    [
      275
    ]
  ],
  "row_count": 1,
  "truncated": false,
  "retried": false,
  "consensus_score": "1/1",
  "timings_ms": {
    "schema_fetch_ms": 46.36,
    "inference_ms": 47373.08,
    "self_correction_ms": 215.75,
    "total_ms": 47662.76
  },
  "model_version": "Qwen2.5-Coder-3B-QLoRA"
}
```

---

## 4. Using Your Own Database

### Adding a SQLite File
1. Place your `.sqlite` or `.db` file into the directory pointed to by `DB_DIR` (default: `db/seeds` or `data/raw/spider/database`).
2. Alternatively, use the Web UI upload dropzone or `POST /v1/databases/upload`.

### Rules for `db_id` and Security Restrictions
- **Naming Rule**: The `db_id` must consist strictly of alphanumeric characters and underscores (`^[a-zA-Z0-9_-]+$`).
- **Path Traversal Blocking**: Filenames containing `..`, `/`, `\`, or null bytes are rejected with `400 Bad Request` to prevent directory traversal.
- **SQLite Header Inspection**: Uploaded database files must match the 16-byte SQLite header signature `SQLite format 3\000`.

### What Happens for Non-SELECT SQL (Adversarial Query)
Attempting a destructive command such as:
```bash
curl -X POST http://127.0.0.1:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"db_id": "chinook", "question": "DROP TABLE Album;"}'
```
Returns `allowed: false` with the exact block message:
```json
{
  "allowed": false,
  "reasons": [
    "Root query type 'drop' is not allowed (must be SELECT/UNION/INTERSECT/EXCEPT)",
    "Forbidden statement/keyword detected: DROP"
  ],
  "sql": "DROP TABLE Album;",
  "rows": [],
  "columns": []
}
```

---

## 5. API Reference

| Endpoint | Method | Auth Required | Purpose |
|---|---|---|---|
| `/healthz` | GET | No | Liveness probe: returns `{"status": "ok"}`. |
| `/ready` | GET | No | Readiness probe: returns model load state and active concurrency limits. |
| `/docs` | GET | No | Interactive Swagger UI / OpenAPI specification. |
| `/v1/query` | POST | Optional (`X-API-Key`) | Main translation and execution pipeline. |
| `/v1/databases` | GET | No | Lists all available SQLite databases. |
| `/v1/sql/validate` | POST | No | Static AST validation of raw SQL queries without execution. |

### Query Request Fields (`POST /v1/query`)
- `db_id` (string, required): Identifier of database to query.
- `question` (string, required): Natural language query in English.
- `enable_consensus` (boolean, optional, default: `false`): Enables 5-sample consensus voting. *Documented as "not evaluated on fine-tuned model" per Rule R9*.

### Rate-Limiting & Auth Header
- **Rate Limiting**: Token-bucket rate limiter enforcing 60 requests per minute per client IP. Returns `429 Too Many Requests` when depleted.
- **Concurrency & Backlog Queue**: Concurrency semaphore (1 active query) with bounded queue backlog (10 queued requests). Returns `503 Service Unavailable` on overload.
- **API Key**: If authentication is enabled (`DISABLE_AUTH=false`), send bearer key via header `X-API-Key: <your-api-key>`.

---

## 6. Configuration Reference

All settings can be configured via environment variables or a `.env` file:

| Variable | Default Value | Description |
|---|---|---|
| `ENV` | `development` | Runtime environment name (`development` or `production`). |
| `LOG_LEVEL` | `INFO` | Logging verbosity level (`DEBUG`, `INFO`, `WARNING`, `ERROR`). |
| `PORT` | `8000` | Port for the Uvicorn HTTP server. |
| `API_KEY` | `dev-secret-key` | Default API key when authentication is active. |
| `DATABASE_URL` | `sqlite:///audit.db` | Path to persistent SQLite audit logging database. |
| `MODEL_BACKEND` | `mock` | Generation backend: `mock`, `llama_cpp`, `transformers`, or `openai_compat`. |
| `MODEL_PATH` | `models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf` | Path to local GGUF model binary. |
| `HF_REPO_ID` | `Ashoksainibadu/fine-tuned-text2sql` | Hugging Face repository ID for automatic GGUF retrieval. |
| `GGUF_FILENAME` | `Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf` | GGUF weight filename to download from Hub. |
| `DB_DIR` | `db/seeds` | Directory containing accessible `.sqlite` database files. |
| `SPIDER_DATA_DIR` | `data/raw/spider` | Root directory for raw Spider evaluation datasets. |

---

## 7. Docker Containerization

### Building and Running Locally
```bash
docker build -t fine-tuned-text2sql:latest .
docker run -p 8000:7860 -e MODEL_BACKEND=mock fine-tuned-text2sql:latest
```

> [!NOTE]
> **Container Verification Status:**
> Docker execution is **not verified on the author's local Windows machine** because Docker is not installed on this host (`docker : The term 'docker' is not recognized`).
> CI workflow includes a container build and /healthz and /ready smoke test; CI green.

---

## 8. Troubleshooting & Empirical Observations

1. **`llama-cpp-python` Build Failure**:  
   If `pip install llama-cpp-python` attempts to compile from source and fails with `CMake Error: CMAKE_C_COMPILER not set`, install using the prebuilt CPU wheel:
   ```bash
   pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
   ```
2. **Missing Model Weights**:  
   If the server starts with `MODEL_BACKEND=llama_cpp` and crashes with `FileNotFoundError`, download the GGUF weights into `models/` or run with `MODEL_BACKEND=mock`.
3. **Port In Use (`[Errno 10048]`)**:  
   Change the port via environment variable: `$env:PORT="8080"` and run `uvicorn src.t2s.serving.app:app --port 8080`.
4. **Read-Only Filesystem / Permission Fallback**:  
   The application writes ephemeral temp files only to `/tmp` (or OS temp directory) to support non-root container sandboxes.
5. **Latency on CPU (Benchmark vs Ad Hoc Testing)**:  
   - **Benchmark ($n=200$, Linux x86_64, 2 physical / 4 logical cores, 31.35 GB RAM, `results/latency_latest.json`)**: Median latency **p50 is 4.68 s**, 95th percentile **p95 is 11.23 s**, and generation throughput is **5.86 tokens/s** (conditions: `n_ctx=2048`, `max_tokens=256`, schema DDL + question prompt, real GGUF model via `llama_cpp`).
   - **Ad Hoc Single Runs on Loaded Host**: Ad hoc single runs during documentation testing took about 47 to 52 s on the same machine while other processes were running; not a benchmark. Interactive latency on a loaded machine can be much higher than standalone benchmark runs.
6. **Git Line Ending (`CRLF` vs `LF`) Test Failures**:  
   If running tests on Windows, Git may convert `LF` to `CRLF`, altering test file hashes. Run:
   ```bash
   git config core.autocrlf false
   git checkout -- .
   ```

---

## 9. Comprehensive Benchmark Results

All evaluation numbers are produced empirically by automated evaluation scripts and verified against `results/*.json` artifacts (Rule R1).

### Model Accuracy & Latency (Spider Dev Split, $n=1,034$)
| System / Configuration | Model Format & Size | Execution Accuracy (Spider Dev, n=1,034) | 95% Bootstrap CI | Latency p50 | Latency p95 | Serving Hardware |
|---|---|---|---|---|---|---|
| **Base Model (Zero-Shot)** | FP16 (6.2 GB) | **62.28%** (644 / 1034) | [59.38%, 65.18%] | 2.16 s | 5.82 s | Linux GPU (Cloud) |
| **Base Model (3-Shot)** | FP16 (6.2 GB) | **66.15%** (684 / 1034) | [63.25%, 68.96%] | 2.23 s | 6.01 s | Linux GPU (Cloud) |
| **Fine-Tuned Adapter (Merged)** | FP16 (6.2 GB) | **71.57%** (740 / 1034) | [68.86%, 74.27%] | 2.19 s | 5.91 s | Linux GPU (Cloud) |
| **Fine-Tuned Quantized (GGUF Q4_K_M)** | GGUF Q4_K_M (1.9 GB) | **70.70%** (731 / 1034) | [67.89%, 73.40%] | 4.68 s | 11.23 s | Local CPU (4 cores, 31.4 GB RAM) |
| **Fine-Tuned Quantized + AST Safety Guardrail** | GGUF Q4_K_M (1.9 GB) | **70.50%** (729 / 1,034) | [67.69%, 73.21%] | 4.71 s | 11.31 s | Local CPU (4 cores, 31.4 GB RAM) |

### Security Guardrails & Red-Teaming Results
| Evaluation Path / Security Metric | Empirical Value | 95% Wilson CI | Defense Mechanism & Evidence |
|---|---|---|---|
| **Path A Static AST Block Rate** | **97.25% (106 / 109)** | [92.22%, 99.06%] | AST Root Type, Forbidden Op, Join Count (`results/redteam_latest.json`) |
| **Path C Sandbox Defense Rate** | **92.66% (101 / 109)** | [86.18%, 96.23%] | Read-Only Authorizer & PRAGMA Defensive (`results/redteam_latest.json`) |
| **Path D Full Pipeline Attack Success** | **0.00% (0 / 109)** | [0.00%, 3.40%] | Multi-Layer Defense in Depth (`results/redteam_latest.json`) |
| **Path B End-to-End Prompt Injection Success** | **0.00% (0 / 60)** | [0.00%, 6.02%] | Prompt injection evaluation over 60 attacks (`results/redteam_latest.json`) |
| **Spider Dev False-Positive Rate (FPR)** | **0.19% (2 / 1,034)** | [0.05%, 0.70%] | AST Join Count Ceiling (5 > 4) (`results/false_blocks.json`) |
| **Legitimate Query Pass Rate** | **99.37% (1103 / 1110)** | [98.70%, 99.69%] | Spider dev (1,034) + 76 benign controls (`results/false_blocks.json`) |

---

## 10. Security Model & Known Limitations

### Defense-in-Depth Security Model
- **No Claims of Absolute Security**: No software system is 100% secure. On custom red-team evaluation suites, the static AST validator blocked **97.25% (106 / 109)** of adversarial SQL attacks on a custom red-team suite (109 direct SQL attacks across dev and held-out splits), while the underlying SQLite read-only sandbox stopped 92.66% (101 / 109) and the full pipeline allowed 0.00% (0 / 109) attack success.
- **Layer 1: AST Parsing**: Validates SQL grammar prior to execution, preventing statement stacking and DDL operations.
- **Layer 2: Read-Only Authorizer**: Mounts databases via SQLite C-level read-only URI hooks, neutralizing bypasses that escape parser AST inspection.

### Known Limitations (Rule R9)
1. **Spider-Only Evaluation**: Evaluation was conducted on the Spider cross-domain academic benchmark. Performance on production schemas with non-standard naming conventions or nested JSON columns may differ.
2. **SQLite Dialect Only**: Specialized for SQLite. Enterprise multi-dialect warehouses (PostgreSQL, Snowflake, BigQuery) are out of scope.
3. **Small Model Failure Modes**: The 3B model occasionally generates incorrect `JOIN` condition keys on highly ambiguous queries ($>4$ tables).
4. **100-Row Hard Limit**: Queries returning large record sets are capped at 100 rows to protect against memory exhaustion.
5. **Self-Correction & Voting**: Self-correction and majority voting were ablated on base models but remain unevaluated on the fine-tuned checkpoint (`docs/PHASE3B.md`).

---

## 11. License & Attribution

- **Base Model (`Qwen2.5-Coder-3B-Instruct`)**: Licensed under Alibaba Cloud's **Qwen Research License Agreement** for non-commercial research and evaluation. Commercial deployment is strictly prohibited without Alibaba authorization.
- **Spider Dataset**: Licensed under **Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)**.
- **Source Code**: System implementation, safety guardrails, and serving infrastructure are licensed under the **MIT License**.
- **User Permissions**:
  - **Permitted**: Non-commercial research, academic replication, educational portfolio review, running locally for testing.
  - **Prohibited**: Commercial exploitation or commercial SaaS hosting of the fine-tuned model checkpoint without adhering to the Qwen Research License.

---

## 12. What Is NOT Included in This Repository

1. **Raw Spider Dataset**: To keep clone operations lightweight (<50 MB), raw training and dev datasets are omitted. See [`docs/REPRODUCE.md`](docs/REPRODUCE.md) for fetch instructions.
2. **Model Weights in Git**: GGUF weights are omitted from git tracking; download them via Hugging Face Hub as described in Quickstart.
3. **Public Hosted Live Space**: The Hugging Face Space demo is currently not running due to a `cpu-basic` quota restriction (quota = 0) on the hosting account. Users run the application locally or via local Docker containers.
