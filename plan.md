# Fine-Tuned Text-to-SQL Assistant: Master Plan (Current State → Production → Resume-Ready)

Owner: Ashok Singodia | Goal: AI Engineer role (~20 LPA) | Estimated duration: 5–6 weeks part-time

---

## 0. HOW TO USE THIS FILE WITH AN AI CODING AGENT (Antigravity)

1. Put this file in the repo root as `PLAN.md`. Also create `AGENTS.md` containing section 1 (Global Rules) below.
2. Give the agent **ONE phase at a time**. Prompt template:
   > Read PLAN.md and AGENTS.md. Execute Phase N only. Do every task in order. When done, run every acceptance check, paste the real command output, and update `results/PROGRESS.md`. Do not start Phase N+1. If a criterion fails, fix it; do not weaken the criterion.
3. After each phase, **you** review the diff and the numbers before starting the next phase.
4. A phase is DONE only when every acceptance box is checked with evidence (command output or file produced).

## 1. GLOBAL RULES (paste into AGENTS.md)

- **R1 No fabricated numbers.** Every metric in README, docs, or resume text must come from a JSON file under `results/` produced by a script in `scripts/`. Never hardcode a metric. Never estimate.
- **R2 Reproducibility.** Every result script takes `--seed` (default 42), writes `results/<name>_<timestamp>.json` plus a stable copy `results/<name>_latest.json`, and records: git commit hash, model name, dataset split, date.
- **R3 No data leakage.** Training uses Spider **train** only. Evaluation uses Spider **dev** only. A script `scripts/check_leakage.py` must assert zero overlap of (question, db_id) between train data and dev data.
- **R4 Audit before assuming.** Do not assume file paths. Start with `tree -L 3` and read `src/t2s/` before editing. Known file: `src/t2s/safety/validator.py`.
- **R5 Don't break green.** All existing 40 tests must keep passing. New code needs tests. Run `pytest -q` before declaring done.
- **R6 Scope discipline.** Do NOT implement: Kubernetes, SSO/SAML/Okta, Snowflake, BigQuery, Redshift, Databricks, Oracle, SQL Server. They are out of scope and must not appear in the resume.
- **R7 Security.** No secrets in git. Use `.env` + `.env.example`. Add `gitleaks` or `detect-secrets` check in CI.
- **R8 Type and lint.** `ruff check .` and `ruff format --check .` pass. Public functions have type hints and docstrings.
- **R9 Honest wording.** If a result is weaker than expected, report it as is. Negative results go in `docs/LIMITATIONS.md`.

## 2. TARGET REPO STRUCTURE (end state)

```
fine-tuned-text2sql/
├── AGENTS.md, PLAN.md, README.md, LICENSE, .env.example
├── pyproject.toml / requirements.txt, Dockerfile, docker-compose.yml
├── .github/workflows/ci.yml
├── src/t2s/
│   ├── api/            # FastAPI routes, auth, rate limit
│   ├── service/        # orchestrator, self-correction, voting
│   ├── model/          # llama.cpp / HF loader, prompt builder
│   ├── safety/         # validator.py (sqlglot), rls.py, pii.py
│   ├── db/             # connectors (sqlite, postgres), executor, schema reflection
│   ├── retrieval/      # schema indexer + retriever
│   └── observability/  # metrics, audit log
├── scripts/            # train, quantize, eval_*, bench_*, check_leakage
├── eval/               # redteam_cases.jsonl, golden_pairs.jsonl, configs
├── results/            # JSON outputs + PROGRESS.md + figures/
├── tests/              # unit, integration, e2e
├── web/                # React + Vite UI
├── docs/               # ARCHITECTURE.md, LIMITATIONS.md, MODEL_CARD.md, RESUME_NUMBERS.md
└── notebooks/          # train_qlora.ipynb (Colab reproducible)
```

---

# PHASE 0: Repo Audit and Baseline Freeze (Day 1)

**Goal:** Know exactly what exists; lock a baseline so improvements are measurable.

**Tasks**
1. Run `tree -L 3`, `pytest -q`, `ruff check .`; save outputs to `results/baseline/`.
2. Write `docs/CURRENT_STATE.md`: list every module, its purpose, its test coverage, known gaps.
3. Tag the commit: `git tag v0.1-poc`.
4. Create `results/PROGRESS.md` with a table: Phase | Status | Date | Key numbers | Evidence files.
5. Add `scripts/check_leakage.py` (Rule R3). Run it.
6. Locate the fine-tuned adapter, merged model, and GGUF file; record sizes and SHA256 in `docs/ARTIFACTS.md`.

**Acceptance criteria**
- [ ] `git tag v0.1-poc` exists
- [ ] `pytest -q` shows 40 passed (saved output in `results/baseline/pytest.txt`)
- [ ] `check_leakage.py` exits 0 and prints overlap count = 0
- [ ] `docs/CURRENT_STATE.md` and `docs/ARTIFACTS.md` exist and list real paths

---

# PHASE 1: Real Evaluation (Execution Accuracy) (Days 2–4) ★ HIGHEST VALUE

**Goal:** Replace the weak "100% valid syntax" claim with true accuracy numbers.

**Tasks**
1. Implement `scripts/eval_spider.py`:
   - Load Spider **dev** (1,034 questions) and the Spider databases.
   - For each model config, generate SQL, execute predicted SQL and gold SQL on the same DB (read-only, 3 s timeout), compare result sets (order-insensitive unless gold has ORDER BY; normalize types/None).
   - Metrics: **Execution Accuracy (EX)**, valid-SQL rate, execution-error rate, timeout rate, blocked-by-guardrail rate; breakdown by Spider difficulty (easy/medium/hard/extra) when available.
2. Run 4 configs through the **same script and same prompt template**:
   - A) Base zero-shot, B) Base 3-shot, C) Fine-tuned (merged FP16/BF16), D) Fine-tuned GGUF Q4_K_M.
3. Implement `scripts/bench_latency.py` for config D on the actual serving path: 200 questions, report p50/p95/p99 end-to-end latency, tokens/sec, peak RSS memory, on the stated hardware (record CPU model, cores, RAM, GPU or none).
4. Generate `results/figures/ex_comparison.png` (bar chart by config and difficulty) via `scripts/make_figures.py`.
5. Write `docs/EVALUATION.md`: method, prompt template, metric definitions, hardware, table of results, honest notes (e.g. Spider is a benchmark, not an enterprise schema).

**Acceptance criteria**
- [ ] `results/eval_spider_latest.json` contains EX for all 4 configs on all 1,034 dev items
- [ ] Fine-tuned EX ≥ Base zero-shot EX (if not: record in LIMITATIONS.md and stop; investigate prompt/training before moving on)
- [ ] GGUF EX within 3 points of fine-tuned FP16 EX (if worse, try Q5_K_M or Q8_0 and report both)
- [ ] `results/latency_latest.json` has p50, p95, p99, tokens/sec, RSS MB, hardware description
- [ ] `docs/EVALUATION.md` table values equal the JSON values (add a test `tests/test_docs_match_results.py` that checks this)
- [ ] Figure file exists

**Resume output:** "Raised execution accuracy from X% → Y% on Spider dev (n=1,034); Q4_K_M GGUF retains Z% EX at 1.9 GB, p95 latency N s on CPU."

---

# PHASE 2: Hardened and Honest Security Evaluation (Days 5–6)

**Goal:** Make the "security" claim defensible.

**Tasks**
1. Expand `eval/redteam_cases.jsonl` from 60 to **≥150 cases**, each with fields: `id, category, prompt, expected_behavior`. Categories (min 15 each): DDL/DML injection, instruction override, data exfiltration, comment smuggling, stacked statements, system-table access, sensitive-column access, Cartesian/resource abuse, encoding tricks (unicode, case, whitespace), function abuse (`load_extension`, `pragma`, `attach`).
2. Split cases: **dev set** (used while building rules) and **held-out set** (never used to tune rules; ≥50 cases written fresh). Report both.
3. Test **two paths**: (a) adversarial SQL fed directly to the validator (unit-level), (b) adversarial natural-language prompts through the full pipeline with the model.
4. Add a **fuzz test** (`hypothesis`) generating random mutations of SELECT queries and DDL; assert validator never crashes and never passes a non-SELECT.
5. Re-measure false-block rate on the 1,034 gold queries; list every blocked gold query in `results/false_blocks.json` with the reason.
6. Write `docs/THREAT_MODEL.md`: assets, attackers, mitigations (AST validator, sandbox, read-only connection, timeout, row limit), and **known gaps** (e.g. semantically wrong but safe SQL, expensive-but-legal queries, side channels).

**Acceptance criteria**
- [ ] ≥150 cases, held-out ≥50, categories documented
- [ ] `results/redteam_latest.json` reports block rate separately for dev, held-out, and end-to-end
- [ ] Any bypass found is fixed AND added as a regression test (list them in THREAT_MODEL.md)
- [ ] Fuzz test passes ≥1,000 examples
- [ ] False-block rate recomputed and each blocked query explained
- [ ] README wording says "blocked X/Y on a custom red-team suite", never "100% secure"

---

# PHASE 3: Execution-Guided Self-Correction and Voting (Days 7–10)

**Goal:** Measurable accuracy gain beyond a single greedy pass.

**Tasks**
1. `src/t2s/service/self_correct.py`: if validator rejects or executor raises an error (syntax, no such column/table, timeout), build a repair prompt `{schema, question, previous_sql, error_message}` and regenerate. Max 2 retries. Log each attempt.
2. `src/t2s/service/voting.py`: sample N candidates (N=5, temperature 0.3–0.7), validate, execute in sandbox, group by normalized result set, choose the majority group; tie-break by lowest-latency / shortest SQL; fall back to greedy if all fail.
3. Config flags in `config.yaml`: `self_correction.enabled`, `max_retries`, `voting.enabled`, `voting.n`.
4. Extend `scripts/eval_spider.py` with configs E) +self-correction, F) +voting, G) +both. Same dev set.
5. Ablation table: EX, avg attempts per question, avg latency, p95 latency.
6. Add an `attempts` array to the API response (SQL, status, error) for transparency.

**Acceptance criteria**
- [x] Unit tests with mocked model: repair is triggered on error, stops at max retries, never executes non-validated SQL
- [x] `results/ablation_latest.json` has EX and latency for configs D, E, F, G
- [ ] At least one of E/F/G improves EX over D (NOT MET: base model ablation showed parity at 62.28%; flagged as UNVERIFIED, harness suspect in docs/LIMITATIONS.md; re-run required on fine-tuned model per docs/PHASE3B.md)
- [x] Latency cost is reported next to each EX gain
- [x] All repaired SQL still passes through the AST validator before execution (test asserts this)

**Resume output:** "Execution-guided self-correction + majority voting lifted EX from Y% → Z% at N× latency."

---

# PHASE 4: Multi-Database Layer (SQLite + PostgreSQL) (Days 11–15)

**Goal:** Prove it works beyond SQLite. Scope limited to **SQLite and PostgreSQL** (MySQL optional only if time remains).

**Tasks**
1. `src/t2s/db/base.py`: abstract `Connector` (`reflect_schema()`, `execute_readonly(sql, timeout, max_rows)`, `dialect`).
2. `sqlite.py` (wrap existing logic) and `postgres.py` (SQLAlchemy + psycopg): connect with a **read-only role** (`GRANT SELECT` only), `SET default_transaction_read_only = on`, `SET statement_timeout`, and `LIMIT` enforcement.
3. Dialect-aware validator: pass `dialect=` into sqlglot; add tests for Postgres-specific syntax (`ILIKE`, `::` casts, `generate_series`, `pg_sleep`, `pg_read_file`, `COPY`, `DO $$`). Block dangerous functions via an explicit denylist AND an allowlist for common functions.
4. Schema reflection from `information_schema` / SQLAlchemy inspector: tables, columns, types, PK/FK, comments.
5. `docker-compose.yml`: add a `postgres` service seeded with a demo database (use **Chinook** or **Northwind**; include the seed SQL in `db/seeds/`).
6. Add dialect hint to the prompt (`-- dialect: postgresql`). Re-run a small PG evaluation (see Phase 7 for the golden set).
7. Integration tests with `testcontainers` or the compose Postgres.

**Acceptance criteria**
- [ ] `docker compose up` brings up API + Postgres; `curl /v1/query` works against both SQLite and Postgres via a `db_id`/connection parameter
- [ ] Attempted `DROP TABLE`, `COPY ... PROGRAM`, `pg_sleep(100)`, `SELECT pg_read_file(...)` are all blocked or timed out (integration test proves it, and the DB role itself lacks permission)
- [ ] Validator unit tests for both dialects pass
- [ ] Schema reflection output for Postgres includes FKs (test)
- [ ] Documented in `docs/ARCHITECTURE.md` with updated diagram

---

# PHASE 5: Schema RAG for Large Databases (Days 16–20)

**Goal:** Handle hundreds of tables by retrieving only relevant schema, with measured benefit.

**Tasks**
1. Build a **large-schema benchmark**: merge all Spider dev databases' tables into one catalog (namespaced `db_id__table`), giving a few hundred tables with many distractors. For each dev question, the gold tables are known (parse from gold SQL via sqlglot).
2. `src/t2s/retrieval/indexer.py`: build documents per table (name, columns, types, FKs, comments, optional business glossary text); embed with `BAAI/bge-small-en-v1.5` or `all-MiniLM-L6-v2`; store in ChromaDB or pgvector (pick one; keep a persistent index on disk).
3. `retriever.py`: top-k tables (k configurable, default 5), expand with FK-neighbors (1 hop) to keep join paths; optional hybrid with BM25 (`rank_bm25`).
4. `scripts/eval_retrieval.py`: **Table Recall@k** (k=3,5,8,10) and MRR vs. gold tables; compare dense vs. hybrid vs. FK-expanded.
5. End-to-end: `scripts/eval_spider.py --schema-mode rag-large` measuring EX when the model sees only retrieved tables vs. the full catalog (where the full catalog may exceed context: record how many fail due to context overflow).
6. Business glossary support: `glossary.yaml` mapping terms to SQL expressions injected into the prompt when matched.

**Acceptance criteria**
- [ ] Large catalog contains ≥200 tables (printed by the script)
- [ ] `results/retrieval_latest.json` has Recall@3/5/8/10 and MRR for each retriever variant
- [ ] `results/eval_rag_large_latest.json` compares full-schema vs RAG on EX and prompt token counts
- [ ] Index build time and query-time retrieval latency reported
- [ ] Unit tests: retriever returns FK-connected tables; glossary injection works
- [ ] API accepts `schema_mode: auto|full|rag`; `auto` switches to RAG above a configurable table-count/token threshold

**Resume output:** "Schema retriever achieves Recall@5 = X% over a 200+ table catalog and keeps EX at Y% (full-schema prompt overflows context)."

---

# PHASE 6: Governance: PII Masking, RLS, Auth (Days 21–24)

**Goal:** Real enterprise controls, each with tests.

**Tasks**
1. `src/t2s/safety/pii.py`: column policy file `policies/columns.yaml` (`deny` / `mask` per table.column). Denied columns are **removed from the schema shown to the LLM** AND rejected by the AST validator if referenced. Pattern-based auto-detection (`ssn`, `password*`, `card*`, `email`, `phone`) as defaults.
2. `src/t2s/safety/rls.py`: AST rewriter that injects `WHERE <tenant_col> = :tenant_id` (AND-ed with any existing WHERE, including inside subqueries, CTEs, UNION branches, and joins). Bind parameters, never string-format user values.
3. Auth: API keys or JWT with roles (`viewer`, `analyst`, `admin`); per-role table/column policy; per-user rate limit (existing token bucket).
4. Audit log: user, role, question, final SQL, validator verdict, attempts, rows returned, duration, error. Redact result values. Export as JSON lines; add `/v1/audit` for admins.
5. Secrets: `.env`-based config; document how to plug in a secret manager (documentation only).
6. Tests: RLS bypass attempts (subquery, UNION, CTE, alias tricks, `OR 1=1` appended by model), PII column access via `SELECT *`, via alias, via subquery.

**Acceptance criteria**
- [ ] `SELECT *` on a table with denied columns never returns those columns (test)
- [ ] RLS: ≥15 bypass-attempt tests pass; two different tenants provably see different rows in an integration test
- [ ] Viewer role cannot access an analyst-only table (test returns 403)
- [ ] Audit log entry produced for every request, including blocked ones (test)
- [ ] `docs/THREAT_MODEL.md` updated with these controls and remaining gaps

---

# PHASE 7: Domain Adaptation Experiment (Days 25–28)

**Goal:** Validate the "200–500 golden pairs adapt the model to a company" claim with real evidence.

**Tasks**
1. Choose the Postgres demo DB from Phase 4 (Chinook/Northwind) as the "enterprise" database.
2. Create `eval/golden_pairs.jsonl`: **300 hand-verified** NL→SQL pairs with custom business terms (e.g. "revenue = unit_price * quantity - discount", "active customer = purchased in last 90 days"). Split 200 train / 100 test; the test set is never used for training. Use the LLM to draft, then **execute and manually verify every gold query**.
3. Evaluate on the 100-pair test set: fine-tuned base (Phase 1 model) with and without glossary (RAG).
4. QLoRA stage-2 fine-tune on the 200 train pairs (continue from stage-1 adapter or new adapter; record which). Use `notebooks/train_qlora.ipynb` on Colab T4. Save training config + loss curve.
5. Re-evaluate on the 100 test pairs. Report EX before/after, per question category.
6. Re-check Spider dev EX to measure **catastrophic forgetting**.

**Acceptance criteria**
- [ ] 300 pairs, split documented, every gold query executes (script verifies)
- [ ] Before/after EX on the 100-pair held-out test saved in `results/domain_adapt_latest.json`
- [ ] Spider dev EX after stage 2 reported next to before
- [ ] Training config, seed, GPU, time, and loss curve saved under `results/training/`
- [ ] Honest conclusion written in EVALUATION.md (gain or no gain)

---

# PHASE 8: Production Packaging and Deployment (Days 29–32)

**Goal:** A public live demo that actually works, plus a reproducible build.

**Tasks**
1. Publish artifacts: push adapter and GGUF to Hugging Face Hub with `docs/MODEL_CARD.md` (intended use, training data, metrics from results/, limitations, license: Qwen2.5-Coder is Apache-2.0, Spider is CC BY-SA 4.0: check and state).
2. Serving: use `llama-cpp-python` server or `llama.cpp` server; config for threads, context size, and a request queue with concurrency limit; graceful 503 on overload; request timeout.
3. Dockerfile: multi-stage, non-root user, healthcheck; image size reported. Compose profiles: `dev`, `demo`.
4. Observability: Prometheus metrics (request count, latency histogram, validator rejects by reason, retries, tokens), plus a Grafana dashboard JSON in `deploy/grafana/`.
5. Deploy demo: backend on **Hugging Face Spaces (Docker, CPU)** or Render/Fly; frontend on Vercel. Demo uses a **read-only sample DB** (Chinook) and a global rate limit; show a banner "demo, sample data only".
6. Web UI polish: schema browser, example questions, validator badge, show attempts, copy SQL, CSV export, error states, loading skeletons, mobile layout. Add Playwright smoke test (ask a question, see a table).
7. CI (`.github/workflows/ci.yml`): ruff, pytest (unit + integration with Postgres service), coverage ≥ 80% on `src/t2s/safety` and `src/t2s/db`, secret scan, docker build, eval smoke test (20 questions) on PR.
8. Load test `scripts/loadtest.py` (locust or k6): 10 / 25 / 50 concurrent users; report throughput and p95.

**Acceptance criteria**
- [ ] Live demo URL responds to a real question in the browser (agent includes a screenshot or curl output)
- [ ] `docker compose --profile demo up` works from a clean clone following README only
- [ ] HF model page is public with model card
- [ ] CI green on main; badge in README
- [ ] `results/loadtest_latest.json` exists; overload returns 503/429, not a crash
- [ ] Grafana dashboard JSON committed; screenshot in `docs/img/`
- [ ] Coverage ≥ 80% on safety and db packages

---

# PHASE 9: Documentation and Portfolio Packaging (Days 33–35)

**Tasks**
1. `README.md` structure: one-line pitch → demo GIF (≤15 s) → live link → architecture diagram → **results table (generated from results/ by `scripts/make_readme_tables.py`)** → quickstart (3 commands) → security model → evaluation method → limitations → roadmap → citations (Spider, Qwen2.5-Coder, sqlglot, llama.cpp).
2. `docs/ARCHITECTURE.md` with Mermaid diagrams matching the real code (request flow, self-correction loop, RAG path, RLS rewrite).
3. `docs/LIMITATIONS.md`: Spider-only generalization caveat, 3B-model weaknesses, no multi-turn conversation, dialect coverage, cost of voting, known failure examples (include 5 real failures with SQL).
4. `docs/RESUME_NUMBERS.md`: **single source of truth** table: metric | value | file | command to reproduce. Resume may only use numbers from this file.
5. Write a blog post draft `docs/BLOG.md` (1,000–1,500 words): problem → approach → results → what failed → lessons.
6. Roadmap section: only what you did NOT build (Snowflake/BigQuery, SSO, k8s, multi-turn, column-level lineage).
7. Pin the repo on GitHub; set topics (`text-to-sql`, `qlora`, `llm`, `fastapi`, `sqlglot`, `gguf`); clean the commit history if messy (squash WIP commits only on a branch you control).

**Acceptance criteria**
- [ ] A stranger can run the demo from README in <10 minutes (test by following it in a fresh clone / fresh container)
- [ ] `RESUME_NUMBERS.md` has every number with a reproduce command
- [ ] README tables equal results JSON (the test from Phase 1 covers it)
- [ ] No broken links (`lychee` or manual check), no TODO/FIXME in docs

---

# PHASE 10: Resume and Interview Readiness (Days 36–38)

**Resume entry template** (fill `[ ]` ONLY from `RESUME_NUMBERS.md`; keep 4 bullets):

```
Fine-Tuned Text-to-SQL Assistant: QLoRA + Guarded Local LLM Serving (Live Demo | GitHub | HF Model)
• Fine-tuning: QLoRA (r=16) on Qwen2.5-Coder-3B with [N] Spider pairs; GGUF Q4_K_M cut size 6.2 GB → 1.9 GB;
  execution accuracy [X]% → [Y]% on Spider dev (n=1,034); CPU p95 latency [N] s.
• Reliability: execution-guided self-correction and [N]-way voting raised EX to [Z]%;
  schema RAG over a [N]-table catalog reached Recall@5 [R]%.
• Safety/Governance: sqlglot AST validator + read-only sandbox; blocked [a]/[b] adversarial prompts
  ([c]/[d] on held-out set), false-block [e]%; PII column masking and tenant-scoped RLS rewriting for PostgreSQL and SQLite.
• MLOps: FastAPI + React, Prometheus/Grafana, Docker Compose, CI ([cov]% coverage on safety/db); deployed on [HF Spaces/Vercel].
```

**Tasks**
1. Fill the template from real numbers; update the resume Summary ("four systems", "QLoRA fine-tuning, quantized local LLM serving, LLM guardrails") and Skills (QLoRA/PEFT, Hugging Face Transformers, TRL, GGUF/llama.cpp, sqlglot, pgvector/ChromaDB, Locust).
2. One-page resume check: order projects FinAdvisor-X → Text-to-SQL → Fraud; shrink the YBI internship to one line; remove skills with no evidence (C, R) unless you can defend them.
3. Create `docs/INTERVIEW_PREP.md` with 25 Q&A grounded in this repo. Must include: Why QLoRA over full fine-tuning? Why r=16 and which target modules? Why Q4_K_M and what accuracy did it cost? How is EX computed and what are its blind spots? How does the AST validator differ from prompt-based safety? What bypasses remain? How does voting choose? Why RAG for schema, how did you measure it? How does RLS rewriting handle subqueries/UNION? What failed? What would you do with 10× compute/data? How would you scale it (vLLM, batching)?
4. 90-second and 5-minute project walkthrough scripts.
5. LinkedIn: project post with demo GIF + 3 key numbers; update headline to "AI Engineer | LLM Fine-tuning, RAG, Guardrails".
6. Application kit: 10 target companies (AI product companies/startups hiring "AI/GenAI Engineer"), tailor the first resume bullet to each JD's keywords.

**Acceptance criteria**
- [ ] Every number on the resume traces to `RESUME_NUMBERS.md`
- [ ] Resume is exactly 1 page, exported to PDF, text selectable (ATS-safe: no tables/columns/icons)
- [ ] Links (demo, GitHub, HF) all open in an incognito window
- [ ] Mock interview done: can explain every bullet for 3 minutes without notes

---

## MASTER DEFINITION OF DONE

- [ ] Phases 0–10 all checked, each with evidence in `results/PROGRESS.md`
- [ ] Real EX numbers for base, fine-tuned, GGUF, +self-correction, +voting
- [ ] Red-team: dev + held-out + end-to-end reported; fuzz test passes
- [ ] PostgreSQL + SQLite both work end-to-end in CI
- [ ] Schema RAG measured on a 200+ table catalog
- [ ] PII masking + RLS + roles tested; audit log complete
- [ ] Domain-adaptation before/after on a held-out set; forgetting check done
- [ ] Public demo, HF model card, green CI, README generated from results
- [ ] Resume updated with verified numbers only

## MINIMUM VIABLE PATH (if time is short: 3 weeks)

Do Phase 0 → 1 → 2 → 3 → 8 (demo only) → 9 → 10. Skip Phases 4–7 and do not claim them. This alone gives: real accuracy, honest security eval, self-correction gains, live demo, and a clean resume story.

## RISKS AND FALLBACKS

| Risk | Fallback |
|---|---|
| Fine-tuned EX not better than base | Check prompt template parity, learning rate, epochs (try 3), data formatting; report honestly |
| GGUF Q4_K_M loses too much EX | Use Q5_K_M/Q8_0; report size vs accuracy trade-off table |
| CPU latency too high for demo | Reduce context, `n_threads` tuning, shorter schema prompts, cache; state hardware honestly |
| Colab T4 time limits | Save checkpoints each 100 steps to Drive; resume training |
| HF Space free tier too slow | Use Render/Fly with a small VM, or demo with a recorded GIF plus local run instructions |