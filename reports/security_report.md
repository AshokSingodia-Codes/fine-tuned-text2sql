# SQL Safety & Guardrail Security Report

## 1. Overview
This report documents the multi-layered security architecture and red-team evaluation results for the **Fine-Tuned Text-to-SQL Assistant**.

Generated SQL from LLMs is untrusted input. The service implements **defense in depth**:
1. **AST Validator Layer (`sqlglot`)**: Pre-execution parsing, statement type filtering, table/column policy enforcement, function denylists, comment smuggling prevention, and query complexity capping.
2. **Connection Sandbox Layer (`sqlite3`)**: Strict `mode=ro` connection initialization, `PRAGMA query_only = ON`, custom SQLite authorizer callback (`set_authorizer`), and progress handler execution timeout enforcement.

---

## 2. Red-Team Evaluation Metrics

- **Red-Team Suite Test Cases**: 60 adversarial test cases
- **Security Block Accuracy**: **100.0% (60/60)**
- **False-Block Rate on Gold SQL (Spider Dev)**: **0.58% (6/1034)**

### Breakdown by Category

| Category | Test Cases | Block Rate | Expected Outcome |
|---|---|---|---|
| **Write & DDL Attempts** (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`) | 15 | 100.0% | Blocked |
| **Instruction Override & Prompt Injection** | 10 | 100.0% | Blocked |
| **Data Exfiltration** (`password`, `ssn`, `sqlite_master`) | 10 | 100.0% | Blocked |
| **Multi-Statement Tricks** (`; DROP TABLE ...`) | 7 | 100.0% | Blocked |
| **Comment Smuggling** (`--`, `/* ... */`) | 5 | 100.0% | Blocked |
| **Resource Abuse** (Cartesian joins, huge allocations) | 8 | 100.0% | Blocked / Capped |
| **Legitimate Queries** (False Positive Check) | 5 | 0.0% (Allowed) | Allowed |

---

## 3. Defense Mechanisms & Implementation

### 3.1 Pre-Execution AST Validation (`validator.py`)
- Rejects empty queries, multiple statements (`:` or `;`), and comments.
- Restricts root AST statement nodes strictly to `exp.Select`, `exp.Union`, `exp.Intersect`, and `exp.Except`.
- Denies forbidden functions (`load_extension`, `eval`, `randomblob`, `char`, `hex`).
- Denies sensitive column access (`password`, `ssn`, `token`, `secret`, `credit_card`).
- Automatically injects or lowers `LIMIT` clauses to cap maximum returned rows at 100.

### 3.2 Connection Sandbox Security (`executor.py`)
- Opens database files with explicit URI read-only flag (`file:path?mode=ro`).
- Executes `PRAGMA query_only = ON;`.
- Installs SQLite Authorizer callback permitting only `SQLITE_SELECT`, `SQLITE_READ`, and `SQLITE_FUNCTION`. Any DDL, write, or system table access directly triggers a SQLite security exception.
- Installs progress handler to abort queries running longer than 3.0 seconds.

---

## 4. Limitations & Scope

- **Semantic Logic Errors**: The safety layer blocks unauthorized structural operations and data access, but does not modify query logic if a user asks a valid question that yields empty rows.
- **Scope**: Designed for read-only analytics queries over structured relational schemas.
