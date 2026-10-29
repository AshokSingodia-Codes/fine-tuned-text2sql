# ─── Text-to-SQL Assistant ── Makefile ───────────────────────────────────────
# Usage:
#   make setup                         Install all dependencies
#   make serve                         Run API server (mock backend, port 8000)
#   make serve DB_DIR=./my_databases   Run server pointing at your own .sqlite files
#   make react-dev                     Run React frontend dev server (port 3000)
#   make query DB=mydb.sqlite Q="..."  One-shot CLI query
#   make repl  DB=mydb.sqlite          Interactive REPL
#   make validate SQL="SELECT ..."     Validate SQL through guardrail (no model)
#   make test                          Run test suite
#   make lint                          Run ruff linter
# ─────────────────────────────────────────────────────────────────────────────

.PHONY: setup serve serve-local react-dev query repl validate test lint \
        data build-data baseline train eval eval-finetuned gguf benchmark redteam docker-up

# ── Configuration ─────────────────────────────────────────────────────────────
DB       ?= mydb.sqlite
DB_DIR   ?= data/raw/spider/database
DB_ID    ?=
Q        ?= How many rows are in the database?
SQL      ?= SELECT 1
BACKEND  ?= mock
MODEL    ?= models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf
PORT     ?= 8000

# ── Install ───────────────────────────────────────────────────────────────────
setup:
	python -m pip install --upgrade pip
	pip install -r requirements.txt
	pip install -r requirements-dev.txt
	pip install -e .
	@echo ""
	@echo "  ✓ Setup complete."
	@echo "  Run 'make serve' to start the API server."
	@echo "  Run 'make query DB=mydb.sqlite Q=\"Your question\"' to query a database."

# ── Serving ───────────────────────────────────────────────────────────────────
serve:
	@echo "  Starting API server (mock backend) on http://localhost:$(PORT)"
	@echo "  Docs: http://localhost:$(PORT)/docs"
	MODEL_BACKEND=mock DISABLE_AUTH=true \
	uvicorn src.t2s.serving.app:app --host 0.0.0.0 --port $(PORT) --reload

serve-local:
	@echo "  Starting API server pointing at: $(DB_DIR)"
	@echo "  Docs: http://localhost:$(PORT)/docs"
	MODEL_BACKEND=$(BACKEND) DISABLE_AUTH=true DB_DIR=$(DB_DIR) \
	uvicorn src.t2s.serving.app:app --host 0.0.0.0 --port $(PORT) --reload

serve-model:
	@echo "  Starting API server with GGUF model: $(MODEL)"
	MODEL_BACKEND=llama_cpp MODEL_PATH=$(MODEL) DISABLE_AUTH=true DB_DIR=$(DB_DIR) \
	uvicorn src.t2s.serving.app:app --host 0.0.0.0 --port $(PORT)

# ── Frontend ──────────────────────────────────────────────────────────────────
react-dev:
	cd frontend && npm run dev

react-build:
	cd frontend && npm run build

# ── CLI Query Tools ───────────────────────────────────────────────────────────
query:
	@echo "  Querying: $(DB)"
	@echo "  Question: $(Q)"
	@echo ""
	python scripts/query_cli.py --db "$(DB)" --question "$(Q)" --backend $(BACKEND) --model "$(MODEL)"

repl:
	python scripts/query_cli.py --db "$(DB)" --interactive --backend $(BACKEND) --model "$(MODEL)"

query-dir:
	python scripts/query_cli.py --db-dir "$(DB_DIR)" --db-id "$(DB_ID)" --question "$(Q)" --backend $(BACKEND)

validate:
	python scripts/query_cli.py --validate "$(SQL)"

list-dbs:
	python scripts/query_cli.py --db-dir "$(DB_DIR)"

# ── Research Pipeline ─────────────────────────────────────────────────────────
data:
	bash scripts/download_spider.sh

build-data:
	python -m src.t2s.data.build_dataset

baseline:
	python scripts/run_baseline.py

train:
	python -m src.t2s.train.train_qlora

eval:
	python scripts/evaluate.py

eval-finetuned:
	python scripts/evaluate_finetuned.py

gguf:
	bash scripts/to_gguf.sh

benchmark:
	python scripts/benchmark.py

redteam:
	python scripts/run_redteam.py

# ── Quality ───────────────────────────────────────────────────────────────────
test:
	pytest tests/ -q

test-safety:
	pytest tests/ -q -k "safety or validator or guardrail"

lint:
	ruff check .

format:
	ruff format .

# ── Docker ────────────────────────────────────────────────────────────────────
docker-up:
	docker-compose up --build
