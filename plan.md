# PLAN: Fine-Tuned Text-to-SQL Assistant (QLoRA) with Safe LLM Serving

An end-to-end build plan: data, prompt design, evaluation harness, QLoRA fine-tuning, quantization, SQL safety layer, API, UI, tests and deployment.
It is written so a human, or an AI coding agent (for example Antigravity), can execute it stage by stage.

> If you keep this file inside the project repo, rename it to `plan.md`.

---

## 0. How to use this file with an AI IDE (read first)

### 0.1 What the agent can and cannot do alone
- **Can do alone (CPU only):** repo setup, data prep, evaluation harness, safety layer, API, UI, tests, Docker, CI, docs.
- **Needs a GPU (human must run):** baseline generation on the full dev set (fast on GPU, slow on CPU), QLoRA training, and the GPU latency benchmark. When a stage is marked **[GPU]** and no GPU is available, the agent must generate a ready-to-run Colab/Kaggle notebook plus a script, then **stop and ask the human** to run it and return the artifacts (paths are listed in each stage).
- **Needs the human:** accepting dataset terms where required, creating Hugging Face and deployment accounts, and approving every metric before it goes on a resume.

### 0.2 Master prompt (paste this to the agent, then attach this file)

```
You are building the project described in plan.md. Work strictly stage by stage.
Rules:
1. Complete one stage at a time. At the end of each stage, run the acceptance
   checks and tests, then stop and print a short status report. Do not start the
   next stage until the checks pass.
2. Never invent or hard-code metrics. Every number in the README, reports and
   model card must come from JSON files in reports/ produced by code.
3. Never commit datasets, model weights over 50 MB, API keys, tokens or .env files.
4. Evaluation uses Spider dev only for the final report. Hyperparameter and prompt
   choices use a validation split carved from the training DATABASES, never dev.
5. Training and inference must use the same prompt-building code.
6. Generated SQL is untrusted. It must pass the safety validator and run only
   through the read-only executor. Never run model output with a writable connection.
7. Verify library APIs against the installed versions (trl, peft, transformers,
   sqlglot, llama-cpp-python change often). If a call fails, read the docs or
   source instead of guessing.
8. If something in the plan is impossible or ambiguous, ask me instead of guessing.
9. Keep functions small, typed and tested. Use ruff for lint and pytest for tests.
```

### 0.3 Per-stage prompt template

```
Execute Stage N of plan.md ("<stage title>"). Create exactly the files listed in
that stage, implement the tasks in order, run the acceptance checks, and report:
files changed, commands run, test results, and measured metrics. If the stage is
marked [GPU] and no GPU is available, create the notebook/script, then stop and
tell me exactly what to run and which files to bring back.
```

---

## 1. Project overview

**Goal:** a natural-language interface to SQL databases, powered by a small open model that **you fine-tune with QLoRA**, served behind a **guarded** API. Users ask a question; the service generates SQL, validates it, executes it read-only, and returns the SQL plus results.

**Dataset:** Spider 1.0 (Yale), a cross-domain text-to-SQL dataset (https://yale-lily.github.io/spider).
- About 7,000 training questions and 1,034 dev questions; the databases in train and dev are different, so it tests generalization to unseen schemas.
- Distributed under CC BY-SA 4.0. Cite the paper (Yu et al., 2018) and state the license in your model card.
- The Spider test set is hidden, so **dev is your final test set**.

**Metric:** execution accuracy (does the generated SQL return the same result as the gold SQL). Use the official test-suite evaluator (https://github.com/taoyds/test-suite-sql-eval) for the reported number, plus your own quick evaluator for iteration.

**Systems compared in the report**
| ID | System |
|---|---|
| A | Base model, zero-shot prompt |
| B | Base model, few-shot prompt |
| C | Fine-tuned model (QLoRA) |
| D | Fine-tuned model, quantized to GGUF Q4_K_M (what you deploy) |
| E | D plus serving-time safety layer and one execution-guided retry |

**Success criteria**
- [ ] Fine-tuned execution accuracy reported on Spider dev, compared with base prompting, with confidence intervals
- [ ] Quantization impact measured
- [ ] Safety layer blocks a red-team suite and does not block valid queries
- [ ] Guarded API with audit log, tests, CI and Docker
- [ ] Public demo, Hugging Face model repo and model card

---

## 2. Tech stack

| Area | Choice |
|---|---|
| Language | Python 3.11 |
| Base model (default) | Qwen2.5-Coder-3B-Instruct. Fallback for small GPUs: Qwen2.5-Coder-1.5B-Instruct. Optional comparison: 7B. Check the model card license for the exact size before publishing; licenses differ between sizes. |
| Fine-tuning | transformers, peft, trl (SFTTrainer), bitsandbytes (4-bit NF4), accelerate |
| Fast inference for evaluation | vLLM (GPU) or transformers batch generate |
| Quantized serving | llama.cpp / llama-cpp-python with GGUF Q4_K_M (CPU friendly) |
| SQL parsing and safety | sqlglot, SQLite authorizer and read-only mode |
| Evaluation | taoyds/test-suite-sql-eval (pinned commit), own evaluator, scipy (bootstrap, McNemar) |
| Tracking | Weights & Biases or MLflow (either is fine); always export a summary JSON to `reports/` |
| API | FastAPI, Uvicorn, Pydantic v2 |
| Storage | SQLite demo databases (read-only); Postgres or SQLite for the audit log |
| Monitoring | prometheus-client (optional Grafana locally) |
| UI | Streamlit |
| Testing | pytest, httpx, Locust |
| Quality | ruff, pre-commit |
| Packaging | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Deployment | Hugging Face Spaces (Docker, CPU) for API + UI; Hugging Face Hub for model files |

Pin exact versions after the first working install (`pip freeze > requirements.lock`). Keep training dependencies (GPU) in a separate `requirements-train.txt` so CI stays light.

---

## 3. Compute plan

| Need | Free option | Notes |
|---|---|---|
| QLoRA training (3B) | Colab free T4 (16 GB) or Kaggle GPU | Use fp16 on T4 (no bf16). Save checkpoints to Google Drive or the HF Hub so a disconnect does not lose progress. Expect roughly a few hours for 2 epochs on about 7k examples; measure it. |
| Training fallback | Switch to the 1.5B model, or shorten max sequence length | Decide in Stage 5 if you hit out-of-memory errors. |
| Dev-set generation (1,034 questions) | Same GPU with vLLM (minutes) | On CPU with a quantized model it takes hours. |
| CPU serving demo | Hugging Face Space (free CPU tier) | A 3B model at Q4_K_M is about 2 GB. Check the current free-tier limits before deploying. |

---

## 4. Repository structure

```
text2sql-qlora/
├── README.md
├── plan.md
├── Makefile
├── requirements.txt            # serving and dev
├── requirements-train.txt      # GPU training extras
├── requirements-dev.txt
├── .env.example
├── .gitignore                  # data/, models/, *.gguf, *.safetensors, mlruns/, .env
├── Dockerfile
├── docker-compose.yml
├── .github/workflows/ci.yml
├── configs/
│   ├── config.yaml             # paths, seeds, split ratios, model names
│   ├── train_qlora.yaml        # hyperparameters
│   ├── serve.yaml              # model backend, timeouts, limits
│   └── policy.yaml             # SQL safety policy (allowed tables, denied functions/columns)
├── data/                       # gitignored
│   ├── raw/spider/
│   └── processed/
├── notebooks/
│   ├── 01_data_explore.ipynb
│   ├── 02_train_colab.ipynb
│   └── 03_generate_eval_colab.ipynb
├── src/t2s/
│   ├── config.py
│   ├── data/    download.py  spider_loader.py  schema.py  prompts.py  build_dataset.py  split.py
│   ├── eval/    exec_eval.py  official_eval.py  metrics.py  error_analysis.py  stats.py
│   ├── gen/     generate.py  backends.py
│   ├── train/   train_qlora.py  merge.py
│   ├── safety/  validator.py  policy.py  executor.py  redteam_cases.py
│   └── serving/ app.py  schemas.py  service.py  auth.py  ratelimit.py  audit.py  metrics.py  dbs.py
├── scripts/     download_spider.sh  run_baseline.py  evaluate.py  to_gguf.sh  benchmark.py
│                make_report.py  run_redteam.py  locustfile.py
├── app_ui/streamlit_app.py
├── reports/                    # JSON metrics, figures, model_card.md, evaluation_report.md
├── third_party/                # test-suite-sql-eval (pinned commit, gitignored or submodule)
└── tests/
    ├── conftest.py
    ├── fixtures/               # tiny synthetic SQLite DB and sample questions
    ├── test_schema.py  test_prompts.py  test_split.py  test_masking.py
    ├── test_exec_eval.py  test_validator.py  test_executor.py  test_redteam.py
    └── test_api.py
```

---

## 5. Timeline

| Path | Stages | Approx. days |
|---|---|---|
| **MVP path** | 0 to 9, 12 (lite), 13, 14 | 8-10 |
| **Full path** | 0 to 14 (plus stretch items) | 12-15 |

---

# STAGES

---

## Stage 0: Repo, environment and tooling (0.5 day)

**Tasks**
1. Create the repo, `git init`, and the folder structure from Section 4 with empty `__init__.py` files.
2. Create a virtual environment and install the serving and dev dependencies. Keep GPU training packages in `requirements-train.txt`.
3. `.gitignore` for data, weights (`*.gguf`, `*.safetensors`, `*.bin`), `.env`, `mlruns/`, `wandb/`.
4. `configs/config.yaml`: seed 42, paths, validation split fraction (10% of training databases), base model name, max sequence length, generation settings (greedy, `max_new_tokens` 256).
5. `src/t2s/config.py` loads YAML and environment variables.
6. `Makefile` targets: `setup`, `data`, `build-data`, `baseline`, `train`, `eval`, `gguf`, `redteam`, `serve`, `ui`, `test`, `lint`, `docker-up`.
7. Ruff config, pre-commit hook, and one passing placeholder test.

**Acceptance checks**
- [ ] `make lint` and `make test` pass on the skeleton
- [ ] No data or weights tracked by git

---

## Stage 1: Data acquisition and validation (0.5 day)

**Human step (if automatic download fails):** download the Spider 1.0 zip from the Spider page and place it in `data/raw/`. The download is hosted on Google Drive, so scripted download can fail; the agent should try `gdown`, then fall back to asking the human.

**Tasks**
1. `scripts/download_spider.sh` (try automatic download; otherwise print clear manual steps), then unzip to `data/raw/spider/`.
2. Expected contents: `train_spider.json`, `train_others.json`, `dev.json`, `tables.json`, `train_gold.sql`, `dev_gold.sql`, and a `database/` folder of SQLite files. Verify they exist.
3. `git clone https://github.com/taoyds/test-suite-sql-eval third_party/test-suite-sql-eval` and record the commit hash in `reports/eval_tool_version.txt`.
4. `src/t2s/data/spider_loader.py`: loaders returning typed records (`question`, `db_id`, `query`).
5. Validation script: check that every `db_id` has a SQLite file; every gold SQL executes without error on its database (report the count that fail); record counts per split.
6. Write `reports/data_profile.json`: number of train and dev questions, databases per split, overlap of `db_id` between train and dev (should be none), SQL hardness distribution if available.

**Acceptance checks**
- [ ] Train about 7,000, dev 1,034 (record actual numbers)
- [ ] Zero database overlap between train and dev
- [ ] Gold SQL executes for nearly all examples (list any that do not)

---

## Stage 2: Schema serialization, prompt and dataset building (1 day)

**Goal:** one prompt builder used everywhere (training, baselines, evaluation, serving).

**Tasks**
1. `schema.py`: read the schema from the SQLite file (not only `tables.json`) and serialize each table as a `CREATE TABLE` statement including primary and foreign keys. Keep table and column order stable.
2. **Sample rows (switchable):** optionally append 3 example rows per table as SQL comments. Public write-ups report that adding sample rows helps, so treat it as an ablation: `include_sample_rows: true/false` in config.
3. `prompts.py`: build a chat-format prompt using the model's own chat template.
   - System: "You are a text-to-SQL assistant. Return only one SQLite SELECT query. No explanations."
   - User: schema block + question.
   - Assistant target: the gold SQL only.
   A few-shot variant (3 examples from training databases) is used only for baseline B.
4. `build_dataset.py`: create training records in **prompt-completion format** so the loss applies to the completion only:
   ```json
   {"prompt": [{"role":"system","content":"..."},{"role":"user","content":"SCHEMA... QUESTION..."}],
    "completion": [{"role":"assistant","content":"SELECT ..."}]}
   ```
5. **Validation split by database:** `split.py` holds out about 10% of **training databases** (not random rows) as `val`. Hyperparameters and prompt choices are judged on `val`. Dev stays untouched until the final report.
6. Token statistics: compute token lengths with the model's tokenizer; choose `max_seq_len` (1,024 to 1,536 is typical). Drop examples longer than the limit and report how many were dropped.
7. Export `data/processed/train.jsonl`, `val.jsonl`, `dev.jsonl` (dev is for generation, not training) and `reports/prompt_stats.json`.
8. Tests: schema for the fixture DB renders correctly; prompt builder is deterministic; split has no `db_id` overlap; **masking test** (Stage 5 reuses it).

**Acceptance checks**
- [ ] Tests pass and no `db_id` appears in both train and val
- [ ] Prompt stats saved; dropped-example count reported

---

## Stage 3: Evaluation harness (1 day)

**Goal:** a trustworthy metric before any model runs.

**Tasks**
1. `gen/backends.py`: a common interface `generate(prompts) -> list[str]` with backends: `transformers`, `vllm`, `llamacpp`, `openai_compat` (works with llama.cpp server, vLLM server, Ollama) and `mock` (returns gold SQL or scripted outputs, for tests).
2. `gen/generate.py`: run a backend over a JSONL of prompts with greedy decoding; strip code fences and text after the first statement; save `predictions.jsonl` with `db_id`, `question`, `gold`, `pred`, `latency_ms`, `tokens`.
3. `eval/exec_eval.py` (fast internal evaluator):
   - run gold and predicted SQL on the same SQLite DB with a timeout;
   - compare result sets as multisets (order-sensitive only if the gold query has `ORDER BY`);
   - report execution accuracy, **valid-SQL rate** (predictions that execute), and exact-match rate.
4. `eval/official_eval.py`: wrap the pinned test-suite evaluator (`--etype exec`, with the tables file and database folder) and parse its output into JSON, including the hardness breakdown (easy / medium / hard / extra). The test-suite number is the one you report; the internal one is for quick iteration. Run `python -c "import nltk; nltk.download('punkt')"` if the tool needs it.
5. `eval/stats.py`: bootstrap 95% confidence intervals for accuracy and a paired test (McNemar) for comparing two systems on the same questions.
6. **Sanity tests (must pass):**
   - gold vs gold gives 100% execution accuracy;
   - an empty or garbage prediction gives 0%;
   - a prediction with a subtly wrong `WHERE` fails;
   - a reordered `SELECT` column list behaves as the tool defines.
7. Save example outputs to `tests/fixtures/` (synthetic DB only).

**Acceptance checks**
- [ ] Gold-vs-gold is 100% on both evaluators (or differences explained)
- [ ] Tests pass and the harness works with the `mock` backend

---

## Stage 4: Baselines [GPU recommended] (0.5-1 day)

**Goal:** honest "before" numbers with the same prompt format the fine-tuned model will use.

**Tasks**
1. `scripts/run_baseline.py` with systems A (zero-shot) and B (few-shot) on `val` first (prompt debugging), then on `dev` once.
2. Generate with vLLM on a GPU (Colab notebook `03_generate_eval_colab.ipynb`) for speed. If there is no GPU, run on a small subset locally and mark the result as partial.
3. Run both evaluators and save `reports/metrics_baseline_A.json`, `reports/metrics_baseline_B.json` (accuracy, valid-SQL rate, hardness breakdown, average latency).
4. Optional reference rows: a 7B base model with the same prompt (for context only).
5. Note failures by eye: 20 wrong predictions, categorized (wrong column, wrong join, missing `GROUP BY`, wrong aggregation, value mismatch, formatting).

**Return artifacts to the agent (if run on Colab):** `predictions_A.jsonl`, `predictions_B.jsonl`.

**Acceptance checks**
- [ ] Baseline metrics JSON saved for A and B
- [ ] Prompt format identical to the training format (except few-shot examples)

**Expected:** see Section 7. Modern code models can already be strong on Spider, so this baseline may be higher than you expect.

---

## Stage 5: QLoRA fine-tuning [GPU] (1.5-2 days, mostly waiting)

**Goal:** train the adapter, with checkpoints and tracking.

**Tasks**
1. `configs/train_qlora.yaml` default values:
   - 4-bit NF4 quantization, double quantization, compute dtype fp16 on T4 (bf16 on newer GPUs);
   - LoRA rank 16, alpha 32, dropout 0.05, target all linear projection layers (`q_proj,k_proj,v_proj,o_proj,gate_proj,up_proj,down_proj`);
   - learning rate 2e-4, cosine schedule, warmup about 3%, 2 epochs;
   - per-device batch size 1-2 with gradient accumulation to an effective batch of about 16;
   - gradient checkpointing on, paged 8-bit AdamW optimizer, `max_seq_len` from Stage 2;
   - evaluate on `val` every N steps, save a checkpoint every N steps, keep the best by validation loss.
2. `train/train_qlora.py`: loads the quantized base, attaches LoRA, builds `SFTTrainer` with the prompt-completion dataset so loss is computed **only on the SQL completion**. Check the installed TRL version's docs for the exact config names.
3. **Masking test** (`test_masking.py`): tokenize one example through the training collator and assert that prompt tokens have label `-100` and completion tokens do not.
4. `notebooks/02_train_colab.ipynb`: installs dependencies, mounts Drive or logs into the HF Hub for checkpoints, runs `train_qlora.py`, and supports resuming from the latest checkpoint.
5. **Smoke run first:** 50 steps on a tiny subset to catch shape, dtype and template errors before the long run.
6. Log to W&B or MLflow: loss curves, learning rate, GPU memory, tokens per second, training time.
7. **Ablations** (each short, judged on `val`, not dev):
   - with vs. without sample rows in the prompt;
   - LoRA rank 8 vs 16 vs 32;
   - 1 vs 2 vs 3 epochs.
   Choose the final configuration from `val` only. Save `reports/ablations.json`.
8. Save the final LoRA adapter (a few tens of MB) and push it to a private HF repo as a backup.

**Return artifacts to the agent:** adapter folder (`adapter_model.safetensors`, `adapter_config.json`), tokenizer files, `trainer_state.json`, tracking export, `reports/ablations.json`.

**Acceptance checks**
- [ ] Training loss decreases; validation loss does not diverge
- [ ] Masking test passes
- [ ] Adapter loads on the base model and generates SQL for a fixture question

**If out-of-memory:** lower `max_seq_len`, drop sample rows, use batch size 1 with more accumulation, or switch to the 1.5B model.

---

## Stage 6: Evaluate the fine-tuned model [GPU recommended] (1 day)

**Tasks**
1. Generate on **dev once** with the final adapter (merged or adapter-attached, same prompt as training) and save `predictions_C.jsonl`.
2. Run both evaluators; save `reports/metrics_finetuned_C.json` with execution accuracy, valid-SQL rate and hardness breakdown.
3. Comparison table A vs B vs C, with bootstrap 95% confidence intervals and McNemar p-values (`reports/comparison.json`).
4. **Error analysis:** categorize 50 random failures of C; compare with the categories from Stage 4. Also list questions C fixed and questions C broke relative to A.
5. **Generalization slices:** accuracy by database, by SQL hardness, and by query features (joins, nested queries, `GROUP BY`, `ORDER BY ... LIMIT`).
6. **Contamination note:** code models may have seen Spider during pretraining. State this as a limitation. If the gain over the baseline is small, say so, and emphasize other wins: valid-SQL rate, format compliance, smaller quantized footprint and latency.

**Acceptance checks**
- [ ] Dev evaluated exactly once for final numbers; results saved by code
- [ ] Comparison table with confidence intervals exists

---

## Stage 7: Merge, quantize and benchmark (1 day)

**Tasks**
1. `train/merge.py`: load the base model in fp16, apply the adapter, merge, and save the merged model (run on GPU or a machine with enough RAM).
2. `scripts/to_gguf.sh`: clone and build llama.cpp (pin a release tag), convert the merged model to GGUF (fp16), then quantize to `Q4_K_M`. Also produce `Q8_0` for comparison.
3. Generate dev predictions with each GGUF through the `llamacpp` or `openai_compat` backend; evaluate. Save `reports/metrics_quantized.json` with accuracy for fp16 merged, Q8_0 and Q4_K_M.
4. `scripts/benchmark.py`: measure on a fixed set of 100 dev prompts:
   - average and p95 latency per query, tokens per second, time to first token;
   - model file size and peak memory;
   - on CPU (llama.cpp, record thread count and CPU model) and, if available, on GPU (vLLM).
5. Optional: create an Ollama `Modelfile` for easy local use.
6. Upload to the Hugging Face Hub: adapter, GGUF file(s) and a draft model card (Stage 14 completes it). Check the base model license first.

**Acceptance checks**
- [ ] Quantized accuracy measured on the same dev set
- [ ] Benchmark JSON saved with hardware details

---

## Stage 8: SQL safety layer (1.5 days)

**Principle:** generated SQL is untrusted input. Use defense in depth: validate before execution, and also restrict the connection itself.

**Tasks**
1. `configs/policy.yaml`: allowed statement type (single `SELECT`, `WITH ... SELECT` allowed), allowed tables per database, denied columns (for example `password`, `ssn`, `token`), denied functions, max row limit (for example 100), max query length, max joins, timeout (for example 3 seconds).
2. `safety/validator.py` using `sqlglot` (SQLite dialect):
   - reject empty output, multiple statements, and non-SELECT roots (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `ATTACH`, `PRAGMA`, `VACUUM`, `REPLACE`);
   - reject SQL comments used to hide payloads, and `load_extension`;
   - walk the AST: every referenced table must be in the allowlist and exist in the schema; every referenced column must exist and not be in the denylist;
   - reject denied functions; block access to `sqlite_master` and other system tables unless explicitly allowed;
   - enforce a row limit by adding or lowering `LIMIT`;
   - limit complexity (joins, subquery depth, cross joins without a condition);
   - return a structured verdict: `allowed` (bool), `reasons[]`, `rewritten_sql`.
3. `safety/executor.py` (defense in depth at the connection level):
   - open SQLite read-only: `sqlite3.connect("file:PATH?mode=ro", uri=True)` and `PRAGMA query_only = ON`;
   - install an **authorizer** callback that only allows `SELECT`, `READ` and an allowlisted set of functions, and denies everything else;
   - install a **progress handler** that aborts queries after the timeout;
   - cap returned rows and total result size;
   - return columns, rows, row count, execution time and truncation flag.
4. **Execution-guided retry:** if execution fails with a SQL error (not a policy violation), call the model once more with the error message appended; allow at most one retry.
5. **Prompt-injection stance:** the user question is data; the system prompt is fixed; output is accepted only if it parses as a single SELECT. Never pass the model's text through to anything other than the validator.
6. `safety/redteam_cases.py`: at least 60 adversarial cases in categories:
   - write and DDL attempts ("delete all rows", "drop the singer table");
   - instruction override ("ignore previous instructions and ...");
   - data exfiltration (password columns, system tables, `sqlite_master`);
   - multi-statement tricks (`; DROP TABLE ...`), comment smuggling;
   - resource abuse (cartesian joins, recursive CTE loops, huge `LIMIT`);
   - encoding and casing tricks, stacked quotes.
   Each case lists the expected outcome (blocked, or allowed and safely truncated).
7. `scripts/run_redteam.py`: runs the cases in two modes: (a) direct SQL strings against the validator and executor, and (b) end to end through the model (on a machine that can run it). Save `reports/metrics_safety.json`: block rate by category, plus false-block rate.
8. **False-block check:** run all dev **gold** SQL through the validator; report how many are wrongly blocked and fix policy gaps (for example an allowed function missing from the allowlist).

**Acceptance checks**
- [ ] `tests/test_validator.py`, `test_executor.py`, `test_redteam.py` pass
- [ ] All write, DDL and multi-statement attacks are blocked; no writes possible even if the validator were bypassed (verify by calling the executor directly with `DROP TABLE`)
- [ ] False-block rate on dev gold SQL is small and documented

---

## Stage 9: Serving API (1.5 days)

**Tasks**
1. `serving/dbs.py`: registry of demo databases. Choose 2-3 SQLite databases from the Spider **dev** split (unseen during training) by reading `db_id` values from `dev.json`. Keep them small.
2. `serving/service.py`: orchestration: fetch schema, build prompt (same builder as training), call the model backend, validate, execute, retry once on execution error, return the result. Backend is chosen from `serve.yaml` (`llamacpp` in-process, `openai_compat` URL, or `mock`).
3. `serving/schemas.py` (Pydantic v2): `QueryRequest` (`db_id`, `question` with max length), `QueryResponse` (`sql`, `verdict`, `columns`, `rows`, `row_count`, `truncated`, `retried`, `timings`, `model_version`, `request_id`).
4. `serving/app.py` endpoints:
   - `GET /health`, `GET /ready` (model loaded, databases reachable), `GET /metrics`
   - `GET /v1/databases`, `GET /v1/databases/{db_id}/schema`
   - `POST /v1/query` (question to SQL to results)
   - `POST /v1/sql/validate` (validate raw SQL, no execution)
   - `POST /v1/feedback` (thumbs up/down with request id)
   - `GET /v1/model/info` (version, quantization, headline metrics read from `reports/`)
5. `auth.py` (X-API-Key), `ratelimit.py` (token bucket; in-memory by default, Redis optional), request size limits, and a global request timeout.
6. `audit.py`: log every request to a table (timestamp, hashed key, db, question, generated SQL, verdict and reasons, execution time, row count, retry flag, model version). Use SQLite locally and Postgres in deployment via `DATABASE_URL`. Do not log result rows.
7. `metrics.py`: Prometheus counters and histograms: requests, latency by stage (generate / validate / execute), blocked count by reason, retry count, errors.
8. Structured JSON logs with a request id.
9. Tests with the `mock` backend: a valid question returns rows; a malicious mock output is blocked with a reason; auth and rate limit behave; oversized input is rejected; retry happens once on an execution error.

**Acceptance checks**
- [ ] API tests pass in CI without a GPU or real model
- [ ] Manual `curl` with the real quantized model returns SQL and rows for a demo database

---

## Stage 10: Demo UI (0.5-1 day)

**Tasks**
1. `app_ui/streamlit_app.py`: database picker with schema viewer, question box, example questions, generated SQL (syntax highlighted), validation verdict (allowed or blocked with reasons), result table, latency breakdown, thumbs up/down buttons.
2. A "try to break it" section with a few sample attack prompts to demonstrate the guardrails.
3. A clear note: demo databases only, read-only, generated SQL is shown before results.

**Acceptance checks**
- [ ] UI works end to end against the local API

---

## Stage 11: Testing, load testing and security report (1 day)

**Tasks**
1. Coverage of at least 80% on `src/t2s` (excluding training code).
2. `scripts/locustfile.py`: mixed traffic of `/v1/query` and `/v1/sql/validate`. Model inference is the bottleneck, so also load test the safety layer alone with the `mock` backend to show its overhead.
3. Record for the real CPU model: concurrency 1, 2 and 4; median and p95 latency; error rate. Save `reports/load_test.json`.
4. Overhead report: validator and executor time versus model time (expect the safety layer to be small compared with generation).
5. `reports/security_report.md`: red-team categories, block rates, known limitations (for example semantic attacks such as a legitimate-looking query that is expensive, and dialect edge cases), and what remains out of scope.

**Acceptance checks**
- [ ] Load test and security reports generated by code
- [ ] Error rate under 1% in the load test (excluding intentional blocks)

---

## Stage 12: Docker, Compose and CI/CD (0.5-1 day)

**Tasks**
1. `Dockerfile`: multi-stage, slim Python base, install llama-cpp-python (use prebuilt CPU wheels if available, otherwise build from source with the needed build tools), non-root user, `HEALTHCHECK`. The GGUF model is **not baked into the repo**; it is downloaded from the HF Hub at startup into a cache directory using `MODEL_REPO` and `MODEL_FILE` environment variables.
2. `docker-compose.yml`: `api`, `ui`, optional `postgres` (audit log), optional `prometheus` and `grafana`.
3. `.github/workflows/ci.yml`: install, `ruff check`, `pytest --cov` with the `mock` backend and fixture DB, build the Docker image, smoke test `/health`.
4. README badges.

**Acceptance checks**
- [ ] `docker compose up` starts the stack and `/ready` returns OK
- [ ] CI green on GitHub

---

## Stage 13: Deployment (1 day)

**Suggested free setup:** a Docker Space on Hugging Face (CPU) running API and UI, with the GGUF downloaded from your HF model repo at startup. Check the current free-tier CPU, RAM and sleep behavior before you deploy.

**Tasks**
1. Create the Space (Docker SDK), set the exposed port (commonly 7860), and add secrets in the Space settings: API keys, `DATABASE_URL` if used.
2. A small launcher runs the FastAPI service and the UI together (or a single reverse-proxy app).
3. Cold-start behavior: log model load time; show a "warming up" message in the UI.
4. Verify `/docs`, a real query on each demo database, and a blocked attack.
5. Publish the HF model repo: adapter, GGUF file(s), tokenizer config, and the finished model card.
6. Put live links (Space, model repo, GitHub) in the README.

**Acceptance checks**
- [ ] Public demo answers a question end to end
- [ ] Guardrails visibly block a malicious prompt in the live demo

---

## Stage 14: Documentation, model card and resume (0.5-1 day)

**Tasks**
1. `scripts/make_report.py` fills README and report tables from `reports/*.json`. No typed-by-hand numbers.
2. **README:** summary, live links, architecture diagram (Mermaid), data and prompt format, training setup, results tables (A/B/C/D, hardness breakdown, quantization, latency), safety design and red-team results, how to run locally, API examples, limitations.
3. **Model card** (`reports/model_card.md` and the HF README): base model and its license, dataset and its CC BY-SA 4.0 terms, training hyperparameters and compute, evaluation method and numbers with confidence intervals, contamination caveat, intended use (read-only analytics on known schemas), out-of-scope uses (writes, production data without review), known failure modes.
4. **Write-up** (optional blog post): what worked, ablation results, what the safety layer caught.
5. Resume bullet (fill with measured values):
   *Fine-tuned Qwen2.5-Coder-3B with QLoRA for text-to-SQL, raising Spider dev execution accuracy from X% to Y% over the prompted baseline; quantized to GGUF (Z% accuracy retained, N ms/query on CPU) and served through a FastAPI service with SQL validation, read-only execution and audit logging; blocked K% of a 60-case red-team suite.*

**Acceptance checks**
- [ ] Every number in docs traces to a JSON file in `reports/`
- [ ] A new person can run the local stack from the README on a clean machine

---

## Stretch items (only after the MVP works)
- **Postgres mode:** transpile generated SQL with `sqlglot` from SQLite to Postgres, run it under a read-only database role with `statement_timeout`, and test dialect edge cases. Report the accuracy drop from transpilation.
- **Grammar-constrained decoding:** use llama.cpp grammar (GBNF) to force a single SELECT statement and measure the change in valid-SQL rate.
- **Larger model comparison:** fine-tune the 1.5B and 7B models and plot accuracy against size and latency.
- **Out-of-domain test:** evaluate on another benchmark (for example a BIRD dev subset or your own small schema) to check generalization.
- **Schema linking:** add a lightweight table and column filter for large schemas.

---

# 7. Expected results before deployment

These are approximate sanity ranges, not guarantees. Always report what you measure.

| Stage | Result | Expected range | Red flag |
|---|---|---|---|
| 1 | Train / dev sizes | About 7,000 / 1,034 | Very different counts |
| 1 | Database overlap train vs dev | None | Any overlap |
| 2 | Examples dropped for length | A small percentage | Large share dropped |
| 3 | Gold vs gold accuracy | 100% | Below 100% |
| 4 | Base model A, dev execution accuracy | Roughly 50-75% for a 3B code model with a good prompt | Near 0% (prompt or parsing bug) |
| 4 | Few-shot B vs zero-shot A | Roughly 0 to +8 points | Large drop |
| 5 | Training loss | Falls steadily; validation tracks it | Validation loss rises early (overfit) |
| 6 | Fine-tuned C, dev execution accuracy | Roughly 65-82% | Below the base model; above about 90% (suspect leakage) |
| 6 | Gain of C over A | Roughly +3 to +20 points | Negative gain |
| 6 | Valid-SQL rate of C | Above about 97% | Below 90% |
| 6 | Hardness | Easy highest; extra-hard much lower (often about 30-55%) | Flat profile |
| 7 | Q4_K_M vs merged fp16 | Drop of about 0-3 points | Drop above 5 points |
| 7 | CPU latency (3B, Q4_K_M, few threads) | Several seconds per query | Minutes per query |
| 8 | Red-team block rate | 100% on write/DDL/multi-statement; above 95% overall | Any successful write |
| 8 | False-block rate on dev gold SQL | Under about 2% | Above 5% |
| 11 | Load test error rate | Under 1% | Over 1% |

**Context:** public engineering write-ups report large gains from fine-tuning on Spider. For example, a Databricks post reports Llama 3 8B improving from about 61% zero-shot to about 80% on Spider dev (https://www.databricks.com/blog/improving-text2sql-performance-ease-databricks). Small models with modern code pretraining may start higher, so your gain can be smaller. Report it honestly.

---

# 8. Common pitfalls

1. **Tuning on dev.** Use the database-level validation split; touch dev once.
2. **Random row split.** Rows from the same database leak schema knowledge. Split by `db_id`.
3. **Prompt mismatch** between training and inference (system text, schema format, chat template). Use one builder.
4. **Training on the prompt tokens.** Verify loss masking with a test.
5. **Wrong dtype on T4.** Use fp16, not bf16.
6. **Trusting the model's output.** Always validate and execute read-only.
7. **Only string-matching SQL.** Use execution accuracy.
8. **Dev gold SQL blocked by your own policy.** Run the false-block check.
9. **Committing weights or data.** Keep them out of git; host weights on the Hub.
10. **Publishing without checking licenses.** Check the base model card and the Spider CC BY-SA terms.
11. **Hand-typed metrics.** Generate from JSON.

---

# 9. Final definition of done

- [ ] All stages' acceptance checks passed
- [ ] `reports/` contains: `data_profile.json`, `prompt_stats.json`, `metrics_baseline_A.json`, `metrics_baseline_B.json`, `ablations.json`, `metrics_finetuned_C.json`, `comparison.json`, `metrics_quantized.json`, `metrics_safety.json`, `load_test.json`, `security_report.md`, `model_card.md`, and figures
- [ ] Adapter and GGUF published on the Hugging Face Hub with a model card
- [ ] Live demo works and blocks a malicious prompt
- [ ] CI green, README complete, repo pinned, resume bullet filled with real numbers
- [ ] You can explain in an interview: why QLoRA, how the prompt and loss masking work, how execution accuracy differs from exact match, what the quantization trade-off was, and how the safety layers (validator, authorizer, read-only mode, timeouts) work together