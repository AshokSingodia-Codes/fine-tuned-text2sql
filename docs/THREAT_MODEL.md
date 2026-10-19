# Threat Model & Security Architecture

**Document Version:** 2.1.0 (Phase 2 Hardened Security Evaluation)  
**Classification:** Engineering Specification  
**Verification Date:** 2026-10-18  

---

## 1. System Overview & Assets

The Text-to-SQL system translates natural language user questions into executable SQL queries, applies an Abstract Syntax Tree (AST) validation filter, and executes permitted queries in an isolated read-only execution sandbox.

### Core Assets to Protect
1. **Database Integrity & State:** Preventing unauthorized writes, modifications, schema drops, or table corruption (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`).
2. **Confidentiality of Restricted Data:** Safeguarding credentials, password hashes, PII (SSNs, credit card numbers), tokens, and internal database catalogs (`sqlite_master`, `sqlite_schema`).
3. **Availability & Compute Resources:** Preventing CPU-spinning denial-of-service, unbounded Cartesian explosion, recursive CTE bombs, and large memory allocations (`randomblob`, `zeroblob`).
4. **Audit Trail Integrity:** Ensuring query logs and validation decisions cannot be forged or poisoned via log injection.
5. **Host Environment:** Preventing arbitrary code execution via database extension loading (`load_extension`), shell escapes, or dynamic function evaluation.

---

## 2. Trust Boundaries & Architecture Diagram

```
[ Untrusted Client ]
       │
═══════╪═══════════════════════════════════════════════════════════ [ Boundary 1: Network Ingress ]
       ▼
 [ FastAPI Gateway / Reverse Proxy ]
   - Rate Limiter (Token bucket per client IP)
   - Authentication & API Key Verification
   - Schema & DDL Introspection Endpoints
       │
═══════╪═══════════════════════════════════════════════════════════ [ Boundary 2: Application Core ]
       ▼
 [ Prompt Construction & LLM Serving ]
   - System Prompt Guardrails
   - Qwen2.5-Coder-3B-Instruct / GGUF Inference
       │
       ▼ (Candidate SQL)
 [ SQL AST Validator (sqlglot) ]  <────────── [ Layer 1: Static AST Guardrail ]
   - Pure AST node type inspection (no false keyword substring collisions)
   - Disallow non-SELECT root types and DDL/DML AST nodes (exp.Drop, exp.Delete, etc.)
   - Tokenized comment rejection
   - Max AST depth enforcement (depth <= 15)
   - Join complexity limits (joins <= 4 per branch, total joins <= 6)
   - Column & table denylist enforcement
   - Limit injection (max 100 rows)
       │
═══════╪═══════════════════════════════════════════════════════════ [ Boundary 3: Database Isolation ]
       ▼ (Rewritten & Allowed SQL)
 [ Safe Read-Only Sandbox ]       <────────── [ Layer 2: Runtime Sandbox Defense ]
   - URI connection parameter: mode=ro
   - PRAGMA query_only = ON
   - SQLite Authorizer Callback (SQLITE_DENY on non-SELECT)
   - Progress handler timeout (3.0s hard cutoff)
   - Row truncation limit (max 100 rows returned)
       │
       ▼
 [ SQLite Target Database Engine ]
```

---

## 3. Attacker Profiles

| Attacker Profile | Capabilities & Vector | Motivation |
|---|---|---|
| **External Malicious User** | Submits adversarial natural language questions or direct queries through public API endpoints. | Data exfiltration (PII/secrets), table destruction, service outage. |
| **Authenticated Tenant** | Has valid API credentials; attempts privilege escalation or querying columns outside designated tenant schema. | Access unauthorized business data, inspect catalog metadata. |
| **Prompt Injection Adversary** | Uses adversarial jailbreak phrasing, roleplay, and system overrides to force the LLM to output malicious SQL. | Circumvent LLM system prompt instructions. |
| **Compromised Supply Chain** | Tampered weights file, malicious tokenizer, or poisoned dependency. | Execute arbitrary code during model initialization. |

---

## 4. STRIDE Threat Analysis Matrix

| Threat Category | Specific Attack Vector | Target Component | Mitigations & Defenses | Status |
|---|---|---|---|---|
| **Spoofing** | Client IP spoofing via `X-Forwarded-For` to bypass rate limits | FastAPI Gateway (`ratelimit.py`) | Rate limiter extracts trusted client IP; reverse proxy must strip untrusted client headers. | Hardened |
| **Tampering** | Stacked query injection (`; DROP TABLE ...`) | AST Validator (`validator.py`) | Multi-statement token detection and AST statement count check reject stacked queries. | Hardened |
| **Tampering** | Comment smuggling (`/* ... */`, `--`) | AST Validator (`validator.py`) | Tokenizer inspects token stream and attached comments; disallows any comment token. | Hardened |
| **Repudiation** | Log injection / CRLF manipulation in audit logs | Logging & Audit (`audit.py`) | Sanitizes newlines (`\r`, `\n`) and escapes special characters in recorded SQL queries. | Hardened |
| **Information Disclosure** | System table extraction (`sqlite_master`, `sqlite_schema`) | AST Validator & Authorizer | AST validator blocks table references; SQLite authorizer denies access to catalog tables. | Hardened |
| **Information Disclosure** | Sensitive column exfiltration (`password`, `ssn`, `token`) | AST Validator (`validator.py`) | Explicit column denylist inspects AST column identifiers and aliases. | Hardened |
| **Information Disclosure** | Verbose error stack traces exposing schema details | API Error Handler (`app.py`) | Sanitized API error messages; returns generic error codes without internal tracebacks. | Hardened |
| **Information Disclosure** | Schema extraction via `/v1/validate` probe | Validation Endpoint (`app.py`) | Returns binary validation verdicts without returning parsed AST internals to caller. | Hardened |
| **Denial of Service** | Unbounded Cartesian join explosion ($A \times B \times C \dots$) | AST Validator & Sandbox | AST validator caps joins to 4 per branch and 6 total; Sandbox row cap truncates to 100 rows. | Hardened |
| **Denial of Service** | Memory exhaustion via `randomblob(10^9)` / `zeroblob` | AST Validator (`policy.py`) | Blocked functions list explicitly forbids memory allocation functions. | Hardened |
| **Denial of Service** | Deep recursive CTE bombs (`WITH RECURSIVE bomb ...`) | Sandbox Progress Handler | 3.0-second timeout handler halts SQLite VM instruction execution. | Hardened |
| **Elevation of Privilege** | Dynamic extension execution (`load_extension()`) | AST Validator & Sandbox | Function denylist blocks `load_extension`; SQLite authorizer denies extension loading. | Hardened |
| **Supply Chain** | Untrusted model file or poisoned GGUF weight artifact | Model Loader (`backends.py`) | SHA-256 verification of model weights before mounting into serving runtime. | Hardened |

---

## 5. Defense-in-Depth Empirical Evidence

The system does not rely on a single defensive layer. The effectiveness of each independent defense layer was empirically verified using the Phase 2 evaluation harness ([`scripts/eval_redteam.py`](file:///e:/7thsem%20learning/projects/finue%20tune/scripts/eval_redteam.py)):

### Layer 1: Static AST Guardrail (Path A Evidence)
* **Execution Evidence:** Tested against 120 attack SQL payloads across 8 attack categories and 65 benign control queries.
* **Attack Block Rate:** **87.50%** (105/120) [95% Wilson CI: 80.40% - 92.28%].
* **Benign Control Pass Rate:** **100.00%** (65/65) [95% Wilson CI: 94.42% - 100.00%].
* **Latency Overhead:** $p_{50} = 2.44\,\text{ms}$, $p_{95} = 7.28\,\text{ms}$.
* **Artifact Reference:** [`results/redteam_latest.json`](file:///e:/7thsem%20learning/projects/finue%20tune/results/redteam_latest.json).

### Layer 2: End-to-End Pipeline & Prompt Defense (Path B Evidence)
* **Execution Evidence:** Tested against 60 prompt injection jailbreak payloads (40 dev + 20 held-out).
* **Attack Success Rate:** **0.00%** (0/60) [95% Wilson CI: 0.00% - 6.02%].
* **Outcome Breakdown:** 44 intercepted by validator, 5 stopped by sandbox, 11 executed harmlessly as standard SELECTs, 0 attack successes.
* **Scope Note:** Path B measures Qwen2.5-Coder-3B-Instruct on this prompt set (60 prompts) only.
* **Artifact Reference:** [`results/redteam_latest.json`](file:///e:/7thsem%20learning/projects/finue%20tune/results/redteam_latest.json), [`results/path_b_model_outputs.json`](file:///e:/7thsem%20learning/projects/finue%20tune/results/path_b_model_outputs.json).

### Layer 3: Runtime Sandbox Isolation (Path C Evidence)
* **Execution Evidence:** Direct execution of 120 attack SQL payloads with the AST validator **completely bypassed**.
* **Sandbox Defense Rate:** **68.33%** (82/120) [95% Wilson CI: 59.55% - 75.98%].
* **Mechanisms Stopping Attacks:**
  * SQLite Security Authorizer Callback: 14 attacks blocked.
  * Read-Only Connection / PRAGMA `query_only`: 66 attacks blocked.
  * Row Limit Truncation (100 row cap): 2 attacks constrained.
* **Zero Database Mutation:** In 100% of test cases, the database SHA-256 file hash remained strictly identical before and after query execution.
* **Artifact Reference:** [`results/redteam_latest.json`](file:///e:/7thsem%20learning/projects/finue%20tune/results/redteam_latest.json).

### Layer 4: Real End-to-End Pipeline (Path D Headline Evidence)
* **Execution Evidence:** Attack SQL payloads evaluated through the full production pipeline (`SQLValidator` $\to$ `SafeSQLExecutor`).
* **Attack Success Rate:** **0.00%** (0/120) [95% Wilson CI: 0.00% - 3.10%].
* **Pipeline Outcomes:**
  * Validator Blocked: 105 attacks ($87.50\%$)
  * Sandbox Blocked: 4 attacks ($3.33\%$)
  * Executed Harmless (Benign whitespace/quotes): 11 queries ($9.17\%$)
  * Attack Success: 0 ($0.00\%$)
* **DoS Wall-Clock Termination:** $p_{50} = 0.002\,\text{s}$, $p_{95} = 0.004\,\text{s}$, $\max = 0.004\,\text{s}$.
* **Artifact Reference:** [`results/redteam_latest.json`](file:///e:/7thsem%20learning/projects/finue%20tune/results/redteam_latest.json).

### Layer 5: Held-Out V2 Evaluation & Provenance Integrity
* **Dataset Provenance:** `heldout_v1` was used during active iterative tuning (e.g., `max_joins` tuned after `DOS_H02`, validator adjustments after `BEN_H13`, `ENC_H02` relabeled post-audit) and is consequently demoted to development split status.
* **Held-Out V2 Specification:** `heldout_v2` consists of 72 novel test cases (48 adversarial across all 8 threat categories + 24 benign controls).
* **Provenance & Independence Limitation:** As explicitly required by integrity conditions, **heldout_v2 was authored by the AI agent itself (`author: agent`), and therefore is NOT an independent third-party evaluation set**. Furthermore, it was evaluated before git commit, so its pre-fix state is frozen strictly by its SHA-256 hash.
* **Frozen Pre-Fix Evaluation Result (Zero Policy Tuning):** Evaluated strictly once without policy tuning:
  * Static Attack Block: 39/48 (81.25%, 95% Wilson CI: [68.06%, 89.81%]).
  * Benign Control Pass Rate: 24/24 (100.00%, 95% Wilson CI: [86.20%, 100.00%]).
  * Sandbox Stopped: 5/9 unblocked payloads.
  * Policy Escape Rate: 4/48 (8.33%, 95% Wilson CI: [3.29%, 19.55%]) — queries expected to be blocked that passed the validator and executed through the sandbox (`ENC_V2_02`, `ENC_V2_03`, `ENC_V2_05`, `FNC_V2_05`).
  * Empirical Harm Rate: **0.00% (0/48)** (95% Wilson CI: [0.00%, 7.41%]) — zero queries caused database mutation, leaked credentials/forbidden columns, returned >100 rows, or timed out >3.5s.
* **Post-Fix Evaluation (Demoted to `heldout_v2_dev`):** Evaluated under the frozen post-fix defense policy (`scripts/eval_heldout_v2_dev.py`):
  * Static Attack Block: 46/48 (95.83%, 95% Wilson CI: [86.02%, 98.85%]).
  * Policy Escape Rate: 0/48 (0.00%, 95% Wilson CI: [0.00%, 7.41%]).
  * Empirical Harm Rate: 0/48 (0.00%, 95% Wilson CI: [0.00%, 7.41%]).
  * Remaining 2 unblocked attacks: `SEN_V2_06` (custom tenant schema entity table; blocked by SQLite sandbox) and `DOS_V2_04` (recursive CTE bomb; blocked by SQLite sandbox authorizer).
* **Artifact Reference:** [`results/eval_heldout_v2.json`](file:///e:/7thsem%20learning/projects/finue%20tune/results/eval_heldout_v2.json), [`results/eval_heldout_v2_dev.json`](file:///e:/7thsem%20learning/projects/finue%20tune/results/eval_heldout_v2_dev.json).

---

## 6. Known Limitations & Gaps (Honest Wording per Rule R9)

1. **Complex Resource Abuse (DoS) Queries:** Queries like `WITH RECURSIVE cnt ...` or `generate_series` cannot be proven harmless by AST inspection alone. They pass the validator and are defended at runtime by the SQLite sandbox progress handler timeout (3.0s).
2. **Recursive CTE Policy & False Block:** SQLite's authorizer issues action code `SQLITE_RECURSIVE` (code 33) for **ALL** recursive CTEs regardless of recursion bounds or termination clauses. Because the sandbox authorizer restricts actions strictly to `{SQLITE_SELECT, SQLITE_READ, SQLITE_FUNCTION}`, **all recursive CTEs (including legitimate small bounded recursions like `WITH RECURSIVE cnt(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM cnt WHERE x < 10) SELECT * FROM cnt;`) are unconditionally blocked at connection authorization time**. This is an intentional security trade-off to eliminate recursive CTE bomb attacks, but represents an explicit false-block for any legitimate recursive queries.
3. **Join Limit Policy Tradeoff & Development Tuning Disclosure:**
   * *Counting Mechanics:* The validator enforces `max_joins_per_branch = 4` across each individual `exp.Select` branch and subquery, and `max_total_joins = 6` across the root statement.
   * *Spider Dev Tradeoff Curve:*
     - Limit 2 joins: 14 / 1,034 queries blocked (1.35% false positive rate)
     - Limit 3 joins: 2 / 1,034 queries blocked (0.19% false positive rate)
     - Limit 4 joins: 2 / 1,034 queries blocked (0.19% false positive rate)
     - Limit 5 joins: 0 / 1,034 queries blocked (0.00% false positive rate)
   * *Tuning Disclosure:* The `max_joins` threshold was tuned while inspecting false positive queries on Spider dev. The 2 remaining false-blocked queries (`SPIDER_pets_1_65` and `SPIDER_pets_1_66`) have 5 joins in a single branch. Any prior claim of "0.00% false positives" was inaccurate; the real empirical false positive rate on Spider dev is **0.19% (2 / 1,034)**.
4. **Whitespace and Quoting Variations:** Queries containing extra whitespace, newlines, or bracket quoting (`[singer]`) normalize to valid SELECT statements without malicious intent. They are classified as `executed_harmless` in Path D and audited in [`results/unblocked_audit.json`](file:///e:/7thsem%20learning/projects/finue%20tune/results/unblocked_audit.json).
5. **Semantically Incorrect but Safe SELECTs:** The security layer validates syntax and safety policy, not semantic business logic. A query like `SELECT * FROM sales WHERE year = 2020` when the user asked for 2021 is safe from an injection standpoint, but mathematically incorrect.
6. **Data Exfiltration via Legitimate Allowed Tables:** If an attacker has access to query table `sales`, they can read all legitimate rows in that table up to the 100-row limit. Fine-grained column-level or row-level security (RLS) across multi-tenant schemas is addressed in Phase 6.
7. **Timing Side-Channels:** Subtle differences in execution time between existing versus non-existing values in indexed columns may reveal information via timing side channels.
8. **SQLite-Specific Engine Hardening:** Current sandboxing uses SQLite-specific authorizer callbacks and PRAGMA settings (`mode=ro`, `PRAGMA query_only = ON`). Multi-database sandboxing (PostgreSQL read-only roles and statement timeouts) is implemented in Phase 4.

---

## 7. Production Deployment Security Checklist

- [ ] **Dedicated Read-Only DB User:** PostgreSQL or database server accounts configured with `GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;` and `REVOKE ALL ON SCHEMA public FROM readonly_user;`.
- [ ] **Enforce Read-Only Connection Strings:** Ensure database URIs explicitly mandate read-only mode (`?mode=ro`).
- [ ] **Strict Statement Timeouts:** Hard database engine timeout set to 3.0 seconds (`SET statement_timeout = 3000;`).
- [ ] **Network Isolation:** Database service container isolated inside a private Docker bridge network without public ingress or egress internet access.
- [ ] **Secret Hygiene:** Database passwords and API keys stored in environment variables (`.env`); zero secrets committed to source control (`.env.example` template only).
- [ ] **Reverse Proxy Hardening:** Ensure upstream reverse proxy (Nginx, Caddy) strips and sanitizes incoming `X-Forwarded-*` headers to protect rate limiting.
