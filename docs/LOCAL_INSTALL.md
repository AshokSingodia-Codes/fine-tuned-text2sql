# Local Installation & Usage Guide

This guide covers everything needed to run the **Text-to-SQL Assistant** on your own machine, query your own SQLite databases, and call the API programmatically.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | 3.12 also works |
| Node.js | 18+ | Only needed for the web UI |
| Git | Any | To clone the repo |
| RAM | ≥ 4 GB | 8 GB recommended for the real model |
| Disk | ≥ 500 MB | + 2 GB if you download the GGUF model |

---

## 1. Installation (One-Time Setup)

```bash
# Clone the repository
git clone https://github.com/AshokSingodia-Codes/fine-tuned-text2sql.git
cd fine-tuned-text2sql

# Create a virtual environment
python -m venv .venv

# Activate it
# On Linux/Mac:
source .venv/bin/activate
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# Install all dependencies
make setup
# (or without make: pip install -r requirements.txt && pip install -e .)
```

---

## 2. Quick Start — Query Your Own Database

You **do not need** the real AI model for this. The `mock` backend returns structured placeholder responses instantly, which is useful for testing the pipeline.

### Option A — CLI (fastest, no server needed)

```bash
# Query any .sqlite file in plain English
python scripts/query_cli.py \
    --db /path/to/your/database.sqlite \
    --question "How many customers signed up last month?"

# Interactive REPL (ask multiple questions)
python scripts/query_cli.py --db mydb.sqlite --interactive

# Validate a raw SQL query through the safety guardrail
python scripts/query_cli.py --validate "DROP TABLE users;"
# → Output: ✗  BLOCKED BY GUARDRAIL  • Forbidden root statement: DROP

# Point at a whole directory of .sqlite files
python scripts/query_cli.py \
    --db-dir /path/to/databases/ \
    --db-id my_database \
    --question "Show top 10 records"

# List all databases in a directory
python scripts/query_cli.py --db-dir /path/to/databases/

# JSON output (for piping to other tools)
python scripts/query_cli.py --db mydb.sqlite --question "Count rows" --json
```

### Option B — Web UI + API Server

```bash
# Terminal 1: Start the API server (mock, no model required)
make serve

# Terminal 2: Start the React frontend
make react-dev
```

Open **http://localhost:3000** in your browser.

- Upload your `.sqlite` file using the drag-and-drop zone in the UI, **or**
- Point the server at your database directory (see below)

---

## 3. Using Your Own Databases

### Method 1 — Upload via Web UI (easiest)
1. Start `make serve` + `make react-dev`
2. Open http://localhost:3000
3. Drag & drop your `.sqlite` file into the **"Upload Your Own SQLite Database"** zone
4. Select your database from the grid → ask questions

### Method 2 — Point the server at a directory

```bash
# Start the server with your database directory
make serve DB_DIR=/path/to/your/databases/
# or:
DB_DIR=/path/to/databases MODEL_BACKEND=mock DISABLE_AUTH=true \
    uvicorn src.t2s.serving.app:app --host 0.0.0.0 --port 8000
```

Your databases will appear automatically in the web UI and API.

### Method 3 — CLI pointing at a directory

```bash
make query DB_DIR=/path/to/databases/ DB_ID=my_database Q="Show all orders"
# or:
python scripts/query_cli.py \
    --db-dir /path/to/databases/ \
    --db-id my_database \
    --question "Show all orders"
```

### What databases work?

| Format | Supported | Notes |
|---|---|---|
| `.sqlite` files | ✅ | Standard SQLite format |
| `.db` files | ✅ | Same format, different extension |
| PostgreSQL / MySQL | ❌ | Not supported (SQLite only in MVP) |
| In-memory SQLite | ❌ | Must be a file on disk |

> **Constraint:** All queries run in a **read-only sandbox**. `INSERT`, `UPDATE`, `DELETE`, `DROP` are always blocked regardless of what the model generates. This is enforced at both the AST validation layer and the SQLite connection authorizer.

---

## 4. Using the Real AI Model (Optional)

By default the system uses a `mock` backend. For real natural language → SQL conversion, download the GGUF model:

```bash
# [NOT PUBLISHED / TODO: When published to Hugging Face Hub]
# pip install huggingface_hub
# python -c "
# from huggingface_hub import hf_hub_download
# hf_hub_download(
#     repo_id='<HF_USERNAME>/fine-tuned-text2sql-adapter',
#     filename='Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf',
#     local_dir='models/'
# )
# print('Model downloaded to models/')
# "

# Then run with the real model
python scripts/query_cli.py \
    --db mydb.sqlite \
    --question "Show top 5 customers by revenue" \
    --backend llama_cpp \
    --model models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf

# Or start the full server with the real model
make serve-model MODEL=models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf \
                 DB_DIR=/path/to/your/databases/
```

---

## 5. REST API Reference

Once the server is running (`make serve`), you have a full REST API.

**Interactive docs:** http://localhost:8000/docs

### Health & Status

```bash
# Check if the server is running
curl http://localhost:8000/health
# → {"status": "ok"}

# Check if the model is loaded and ready
curl http://localhost:8000/ready
# → {"status": "ready", "backend": "mock", "model_loaded": true}
```

### List Available Databases

```bash
curl http://localhost:8000/v1/databases
```

```json
{
  "total": 3,
  "databases": [
    {"db_id": "concert_singer", "table_count": 4, "tables": [...]},
    {"db_id": "pets_1", "table_count": 3, "tables": [...]}
  ]
}
```

### Get Schema DDL

```bash
curl http://localhost:8000/v1/databases/concert_singer/schema
```

### Query — Natural Language to SQL

```bash
curl -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "db_id": "concert_singer",
    "question": "How many singers are there?",
    "enable_consensus": false,
    "n_samples": 1
  }'
```

**Response:**
```json
{
  "request_id": "abc123",
  "db_id": "concert_singer",
  "question": "How many singers are there?",
  "sql": "SELECT COUNT(*) FROM singer",
  "allowed": true,
  "reasons": [],
  "columns": ["COUNT(*)"],
  "rows": [[30]],
  "row_count": 1,
  "truncated": false,
  "consensus_score": null,
  "retried": false,
  "timings_ms": {
    "inference_ms": 4710,
    "validation_ms": 2,
    "execution_ms": 1,
    "total_ms": 4713
  }
}
```

### Upload a Database via API

```bash
curl -X POST http://localhost:8000/v1/databases/upload \
  -F "file=@/path/to/mydb.sqlite"
```

```json
{
  "db_id": "mydb",
  "table_count": 5,
  "tables": ["users", "orders", "products", "categories", "reviews"],
  "size_bytes": 204800
}
```

After upload, use `"db_id": "mydb"` in `/v1/query` immediately.

### Validate a SQL Query (No Model)

```bash
curl -X POST http://localhost:8000/v1/sql/validate \
  -H "Content-Type: application/json" \
  -d '{"sql": "DROP TABLE users;"}'
```

```json
{
  "allowed": false,
  "reasons": ["Forbidden root statement type: DROP"],
  "rewritten_sql": null
}
```

### Python Client Example

```python
import requests

BASE = "http://localhost:8000"

# Upload your database
with open("mydb.sqlite", "rb") as f:
    r = requests.post(f"{BASE}/v1/databases/upload", files={"file": f})
    db_id = r.json()["db_id"]
    print(f"Uploaded: {db_id}")

# Query it
r = requests.post(
    f"{BASE}/v1/query",
    json={
        "db_id": db_id,
        "question": "Show the top 10 rows",
        "enable_consensus": False,
        "n_samples": 1,
    },
)
result = r.json()
if result["allowed"]:
    print("SQL:", result["sql"])
    print("Columns:", result["columns"])
    print("Rows:", result["rows"])
else:
    print("Blocked:", result["reasons"])
```

---

## 6. Environment Variables Reference

| Variable | Default | Description |
|---|---|---|
| `MODEL_BACKEND` | `mock` | `mock`, `llama_cpp`, or `openai_compat` |
| `MODEL_PATH` | `models/...gguf` | Path to GGUF model weights |
| `DB_DIR` | `data/raw/spider/database` | Directory of .sqlite files to serve |
| `DISABLE_AUTH` | _(unset)_ | Set to `true` to skip API key auth |
| `APP_PROFILE` | `dev` | `demo` disables /metrics and restricts DBs |
| `PORT` | `8000` | Port for uvicorn |
| `CORS_ALLOW_ORIGINS` | `*` | Comma-separated allowed origins |

---

## 7. Makefile Quick Reference

```bash
make setup                              # Install dependencies
make serve                              # API server, mock backend, port 8000
make serve DB_DIR=./mydata              # API server pointing at your .sqlite files
make serve-model MODEL=path/to.gguf    # API server with real GGUF model
make react-dev                          # React frontend at port 3000
make query DB=mydb.sqlite Q="..."      # One-shot CLI query
make repl  DB=mydb.sqlite              # Interactive REPL
make validate SQL="DROP TABLE x;"      # Validate SQL through guardrail
make list-dbs DB_DIR=./mydata          # List all .sqlite files in a directory
make test                               # Run full test suite (80 tests)
make lint                               # Run ruff linter
```

---

## 8. Security Model

The system enforces safety at **three independent layers**:

| Layer | What it blocks |
|---|---|
| **1. AST Validator** (sqlglot) | Non-SELECT statements, subquery injection, forbidden ops |
| **2. SQLite Read-Only Authorizer** | Any write operation at the SQLite C-level callback |
| **3. Row Limit** | Results capped at 100 rows to prevent data exfiltration |

Even if the model generates a malicious query, layers 2 and 3 prevent execution.

---

## 9. Troubleshooting

**`ModuleNotFoundError: No module named 'src.t2s'`**
→ Run `pip install -e .` or set `PYTHONPATH=.`

**`Model is warming up` in the UI**
→ The mock backend should be instant. If you see this with `llama_cpp`, the GGUF model is still loading (~30s).

**CLI query returns mock SQL like `SELECT 1`**
→ You're using `--backend mock` (default). Use `--backend llama_cpp --model path/to.gguf` for real inference.

**Upload fails: "Only .sqlite or .db files are accepted"**
→ Make sure your file extension is exactly `.sqlite` or `.db`. Rename if needed.

**`Database 'mydb' not found` on the server**
→ The server only serves databases in `DB_DIR`. Restart with `DB_DIR=/your/path make serve` or use the upload endpoint.
