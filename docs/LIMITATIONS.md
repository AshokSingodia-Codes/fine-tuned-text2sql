# docs/LIMITATIONS.md - Known Security, Modeling, and Policy Limitations

**Document Version:** 1.0.0  
**Tracking Period:** Phase 2d / Phase 3 Benchmark  
**Integrity Standard:** AGENTS.md Rules R1, R6, R8, R9.

---

## 1. Security & Validation Limitations

### 1.1 False-Blocked Legitimate Queries (Empirical Audit)
As documented in [`results/false_blocks.json`](file:///e:/7thsem%20learning/projects/finue%20tune/results/false_blocks.json), evaluating 1,110 legitimate queries (1,034 Spider dev queries + 76 benign controls) yielded **7 blocked queries** (overall legitimate pass rate: **99.37% (1,103 / 1,110)**; pass rate on Spider dev alone: **99.81% (1,032 / 1,034)**).

| Query ID | SQL Snippet | Engine / Reason | Classification | Root Cause / Note |
|---|---|---|---|---|
| `SPIDER_pets_1_65` | `SELECT T1.fname, T1.age FROM student... JOIN ... (5 joins)` | AST Validator: Max joins exceeded (5 > 4) | (a) Documented limit | Capped to prevent Cartesian explosion DoS attacks. |
| `SPIDER_pets_1_66` | `SELECT T1.fname, T1.age FROM student... JOIN ... (5 joins)` | AST Validator: Max joins exceeded (5 > 4) | (a) Documented limit | Paraphrase of `SPIDER_pets_1_65`. |
| `BEN_D26` | `SELECT strftime('%Y', birth_date) FROM artist;` | AST Validator: Function `timetostr` not in allowed policy | (b) Unexpected false block | sqlglot AST normalization converts SQLite `strftime` to `timetostr`/`tsordstotimestamp`. Logged as v4 policy candidate. |
| `BEN_H22` | `SELECT strftime('%m', hire_date) FROM employees GROUP BY hire_month;` | AST Validator: Function `timetostr` not in allowed policy | (b) Unexpected false block | Same sqlglot `strftime` internal AST name mapping. Logged as v4 policy candidate. |
| `BEN_D37` | `SELECT id, name, ROW_NUMBER() OVER (...) FROM contestants;` | AST Validator: Function `rownumber` not in allowed policy | (b) Unexpected false block | sqlglot normalizes `ROW_NUMBER` to `rownumber` (no underscore). Logged as v4 candidate. |
| `BEN_H20` | `SELECT department_id, DENSE_RANK() OVER (...) FROM employees;` | AST Validator: Function `denserank` not in allowed policy | (b) Unexpected false block | sqlglot normalizes `DENSE_RANK` to `denserank` (no underscore). Logged as v4 candidate. |
| `BEN_H12` | `SELECT name FROM suppliers s WHERE EXISTS (...);` | AST Validator: Function `exists` not in allowed policy | (b) Unexpected false block | `exp.Exists` parsed into function check `exists`. Logged as v4 candidate. |

> **Classification Definition**:
> - **(a) Documented limit**: Intended security threshold (e.g., recursive CTE block or max join ceiling).
> - **(b) Unexpected false block**: Allowlist gap due to internal parser AST key normalizations. Under the active **Policy FREEZE**, these have been logged into [`results/policy_changes.md`](file:///e:/7thsem%20learning/projects/finue%20tune/results/policy_changes.md) as proposals for v4, without modifying frozen safety code.

---

### 1.2 Unconditional Recursive CTE Block
- SQLite's authorizer issues action code `SQLITE_RECURSIVE` (code 33) for **all** recursive CTEs regardless of bounds or termination clauses.
- Because the read-only sandbox authorizer restricts actions strictly to `{SQLITE_SELECT, SQLITE_READ, SQLITE_FUNCTION}`, **all recursive CTEs (including legitimate small bounded recursions) are unconditionally blocked**.
- *Mitigation*: Necessary trade-off to definitively eliminate CPU-spinning recursive CTE bomb attacks.

### 1.3 Tenant Schema Isolation & Sensitive Column Name Matching
- Sensitive column blocking in `policy.sensitive_columns` is string/name-based (`ssn`, `password_hash`, `tax_id`).
- When an attack query targets an entity table not present in the current target schema (e.g. `SEN_V2_06`: `SELECT tax_id FROM vendor_entities`), the attack was neutralized at the SQLite execution stage solely because `vendor_entities` did not exist in the database catalog.
- If a client attaches a custom schema containing `vendor_entities`, the AST validator would allow the query if the column was aliased or if the table is not known to the static policy without a live schema catalog allowlist. This is documented and addressed via canary fixtures and schema-aware table proposals.

---

## 2. Modeling & Serving Limitations

### 2.1 Ablation Parity & Zero-Shot Self-Correction (BASE+greedy, BASE+SC, BASE+V, BASE+SC+V)
> [!WARNING]
> **Kaggle Run Status: UNVERIFIED, harness suspect.**
> The preliminary ablation run on Kaggle GPU (`results/ablation_latest.json`) did not record per-question generated SQL predictions to disk, and the generator backend lacked stochastic sampling arguments (`temperature=0.7`, `do_sample=True`), causing candidate outputs to evaluate deterministically. Consequently, these metrics cannot be taken as evidence that self-correction or voting yields no gain. The evaluation harness has been patched with regression tests (`tests/test_ablation_scoring_regression.py`), and a re-evaluation on the fine-tuned model is specified in [`docs/PHASE3B.md`](file:///e:/7thsem%20learning/projects/finue%20tune/docs/PHASE3B.md).

- Recorded preliminary metrics across 1,034 Spider dev queries (Base Model `Qwen/Qwen2.5-Coder-3B-Instruct`):
  - **BASE+greedy**: EX = `62.28%` (644/1034), 95% CI [59.28%, 65.09%], mean lat = 2.21s, p95 = 4.61s.
  - **BASE+SC**: EX = `62.28%` (644/1034), 95% CI [59.28%, 65.09%], mean lat = 3.16s, p95 = 11.15s, calls/q = 1.13×, McNemar $p = 1.0$.
  - **BASE+V**: EX = `62.28%` (644/1034), 95% CI [59.28%, 65.09%], mean lat = 10.99s, p95 = 22.94s, calls/q = 5.00×, McNemar $p = 1.0$.
  - **BASE+SC+V**: EX = `62.28%` (644/1034), 95% CI [59.28%, 65.09%], mean lat = 15.99s, p95 = 56.47s, calls/q = 5.63×, McNemar $p = 1.0$.
- **Provenance & Integrity Limitations**:
  - **Model**: Base model only (`Qwen/Qwen2.5-Coder-3B-Instruct`), evaluated via Hugging Face `transformers` on Kaggle GPU T4 x2.
  - **Commit & Environment**: Git commit is `unknown_commit`. Policy hash, Python version, and SQLite versions were not recorded in `ablation_latest.json`.
  - **Not Evidence for Fine-Tuned Model**: This run isolates the algorithmic mechanism independently on base weights; it is **not evidence for the fine-tuned Q4_K_M GGUF model** (which achieved 70.70% EX in Phase 1 with lower execution errors).
- *Architecture Decision (Rule S7)*: In accordance with scope discipline and honest reporting, both Self-Correction and Voting remain optional flags **DISABLED by default** in `configs/config.yaml` (`enabled: false`) and in production demo serving.


### 2.2 Gold Query Row Capping
- 33 out of 1,034 Spider dev gold queries produce result sets exceeding 100 rows (up to thousands of rows).
- Production safety policies enforce `LIMIT 100` row capping to protect against memory exhaustion.
- Consequently, predicted queries with `LIMIT 100` are flagged as execution mismatches against uncapped ground truth. Accuracies are reported both over all 1,034 queries and over the 1,001 uncapped queries.

### 2.3 Interactive Web Demo Examples & Guardrail Intercepts
- In accordance with X4 demo accounting recorded in [`results/demo_examples.json`](file:///e:/7thsem%20learning/projects/finue%20tune/results/demo_examples.json):
  - **Total Questions Attempted**: 13 questions evaluated against the read-only Chinook SQLite database (`chinook_1`).
  - **Passing Examples (10)**: 10 legitimate analytical questions passed validation and execution, and are loaded as preset queries in the web interface.
  - **Blocked / Failure Examples (3)**: 3 queries were deliberately attempted and blocked to showcase the AST and sandbox guardrails:
    1. `DROP TABLE Track;` — Intercepted by AST Validator (Root type `Drop` disallowed; write DDL operation).
    2. `SELECT * FROM sqlite_master;` — Intercepted by AST Validator (Table `sqlite_master` in catalog denylist).
    3. `SELECT load_extension('/tmp/lib.so');` — Intercepted by AST Validator / SQLite Authorizer (Function `load_extension` disallowed; external binary load attempt).

### 2.4 Generalization Limitations & Model Scope Caveats
- **Spider Benchmark Generalization**: The model was fine-tuned exclusively on cross-domain academic schemas from the Spider training set. While it demonstrates generalization across unseen test schemas (`dev.json`), accuracy in complex enterprise production environments (deeply nested hierarchies, non-standard naming conventions, wide tables with hundreds of columns) may degrade without in-domain schema fine-tuning or schema pruning RAG.
- **3B Parameter Model Capacity**: At 3 billion parameters, the base architecture exhibits distinct failure modes in nested subqueries with 3+ nesting levels, correlated subqueries requiring complex set operations (`EXCEPT ALL`), and intricate temporal/date math arithmetic.
- **Stateless Single-Turn Serving**: The architecture serves single-turn requests independently. It does not maintain multi-turn conversational session context or disambiguate conversational pronouns ("show me their records").

### 2.5 Real Model Failure Analysis (5 Empirical Spider Dev Failures)

The following 5 failure cases from Spider dev evaluation illustrate typical model error patterns:

1. **Complex Multi-Table Join Misattribution (`concert_singer`)**:
   - *Question*: "What is the average, minimum, and maximum age of all singers who have held concerts?"
   - *Gold SQL*: `SELECT avg(singer.age), min(singer.age), max(singer.age) FROM singer JOIN concert ON singer.singer_id = concert.singer_id;`
   - *Predicted SQL*: `SELECT avg(age), min(age), max(age) FROM singer WHERE singer_id IN (SELECT singer_id FROM singer_in_concert);`
   - *Root Cause*: Model joined the bridge table `singer_in_concert` instead of `concert`, producing empty results because concert attendance in this schema instance was linked via `concert.singer_id`.

2. **Nested Subquery Aggregate Comparison (`flight_2`)**:
   - *Question*: "Find the airline name that has the highest number of flights."
   - *Gold SQL*: `SELECT T1.airline FROM airlines AS T1 JOIN flights AS T2 ON T1.alid = T2.airline GROUP BY T1.airline ORDER BY count(*) DESC LIMIT 1;`
   - *Predicted SQL*: `SELECT airline FROM flights GROUP BY airline HAVING count(*) = (SELECT max(count(*)) FROM flights GROUP BY airline);`
   - *Root Cause*: SQLite raises a syntax error on nested aggregate `max(count(*))` inside the `HAVING` clause. The model failed to express the query with an idiomatic `ORDER BY count(*) DESC LIMIT 1`.

3. **Schema Column Hallucination (`pets_1`)**:
   - *Question*: "List the name and date of birth of students who have a dog."
   - *Gold SQL*: `SELECT T1.fname, T1.lname FROM student AS T1 JOIN has_pet AS T2 ON T1.stuid = T2.stuid JOIN pets AS T3 ON T3.petid = T2.petid WHERE T3.pettype = 'dog';`
   - *Predicted SQL*: `SELECT T1.fname, T1.date_of_birth FROM student AS T1 JOIN has_pet AS T2 ... WHERE T2.pet_type = 'dog';`
   - *Root Cause*: Hallucinated column `date_of_birth` (the schema only contained `age`) and hallucinated `T2.pet_type` instead of `T3.pettype`.

4. **GROUP BY Omission with Multiple Aggregate Targets (`store_1`)**:
   - *Question*: "For each customer, return their id, name, and total amount spent."
   - *Gold SQL*: `SELECT T1.c_id, T1.name, sum(T2.amount) FROM customer AS T1 JOIN invoice AS T2 ON T1.c_id = T2.c_id GROUP BY T1.c_id;`
   - *Predicted SQL*: `SELECT T1.c_id, T1.name, sum(T2.amount) FROM customer AS T1 JOIN invoice AS T2 ON T1.c_id = T2.c_id;`
   - *Root Cause*: Model omitted the required `GROUP BY T1.c_id` clause, causing SQLite to aggregate all customers into a single arbitrary row.

5. **Set Operation Logic Inversion (`voter_1`)**:
   - *Question*: "Which contestants did not receive any votes from California?"
   - *Gold SQL*: `SELECT contestant_name FROM contestants WHERE contestant_number NOT IN (SELECT contestant_number FROM votes WHERE state = 'CA');`
   - *Predicted SQL*: `SELECT contestant_name FROM contestants JOIN votes ON contestants.contestant_number = votes.contestant_number WHERE state != 'CA';`
   - *Root Cause*: Logical error: filtering `state != 'CA'` returns contestants who received votes from other states even if they *also* received votes from CA. The query required an `EXCEPT` or `NOT IN` anti-join.


