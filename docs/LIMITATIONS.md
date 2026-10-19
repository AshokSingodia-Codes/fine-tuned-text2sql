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

### 2.1 Ablation Parity & Zero-Shot Self-Correction
- Empirical findings across 1,034 Spider dev queries demonstrate that zero-shot base models (e.g., `Qwen/Qwen2.5-Coder-3B-Instruct` without task-specific fine-tuning on SQL error trajectories) do **not** gain execution accuracy from naive self-correction retries.
- While self-correction correctly triggered on ~13% of queries with database execution or syntax errors, the zero-shot base model produced equivalent failure modes upon re-prompting.
- Similarly, greedy consensus voting ($N=5$ with temperature 0.0) produces identical candidate samples, leaving EX unchanged at `62.28%`.
- *Architecture Decision (Rule S7)*: In accordance with scope discipline and honest reporting, both Self-Correction and Voting remain optional flags disabled by default in `configs/config.yaml` until fine-tuned error-reflection checkpoints are trained.

### 2.2 Gold Query Row Capping
- 33 out of 1,034 Spider dev gold queries produce result sets exceeding 100 rows (up to thousands of rows).
- Production safety policies enforce `LIMIT 100` row capping to protect against memory exhaustion.
- Consequently, predicted queries with `LIMIT 100` are flagged as execution mismatches against uncapped ground truth. Accuracies are reported both over all 1,034 queries and over the 1,001 uncapped queries.
