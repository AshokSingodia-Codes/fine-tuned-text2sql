"""End-to-end validation of the full database handling flow."""

import os
import pathlib
import shutil
import sqlite3
import sys
import tempfile

sys.path.insert(0, ".")

from src.t2s.safety.executor import SafeSQLExecutor
from src.t2s.safety.policy import SafetyPolicy
from src.t2s.safety.validator import SQLValidator
from src.t2s.serving.dbs import DatabaseRegistry
from src.t2s.serving.service import Text2SQLService

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"

results = []


def check(label, cond, detail=""):
    status = PASS if cond else FAIL
    results.append((status, label, detail))
    print(f"  {status}  {label}" + (f"  ({detail})" if detail else ""))


print("\n" + "=" * 60)
print("  DATABASE FLOW END-TO-END VALIDATION")
print("=" * 60)

# ─── 1. Directory structure ───────────────────────────────────
print("\n[1] Directory Structure")
spider_dir = pathlib.Path("data/raw/spider/database")
db_dir = pathlib.Path("db/seeds")
check("Spider database dir exists", spider_dir.exists(), str(spider_dir))
check("db/seeds dir exists", db_dir.exists(), str(db_dir))
spider_dbs = list(spider_dir.glob("*/*.sqlite")) if spider_dir.exists() else []
check("Spider databases present", len(spider_dbs) > 0, f"{len(spider_dbs)} found")
chinook = db_dir / "chinook.sqlite"
check("Chinook seed database exists", chinook.exists(), str(chinook))

# ─── 2. DatabaseRegistry ─────────────────────────────────────
print("\n[2] DatabaseRegistry")

reg = DatabaseRegistry("data/raw/spider/database")
dbs = reg.list_databases()
check("list_databases() returns results", len(dbs) > 0, f"{len(dbs)} databases")

path = reg.get_db_path("concert_singer")
check("get_db_path('concert_singer') found", path is not None and path.exists())

# Path traversal guards
check("Traversal '../..' blocked", reg.get_db_path("../../etc/passwd") is None)
check("Slash in db_id blocked", reg.get_db_path("sub/dir") is None)
check("Backslash in db_id blocked", reg.get_db_path("sub\\dir") is None)

# Schema DDL
try:
    ddl = reg.get_schema_ddl("concert_singer")
    check("Schema DDL non-empty", len(ddl) > 50, f"{len(ddl)} chars")
    check("Schema DDL has CREATE TABLE", "CREATE TABLE" in ddl)
except Exception as e:
    check("Schema DDL", False, str(e))

# ─── 3. Upload directory flow ─────────────────────────────────
print("\n[3] Upload Directory Flow")
tmpdir = tempfile.mkdtemp()
try:
    # Create test DB
    test_db = pathlib.Path(tmpdir) / "mycompany.sqlite"
    conn = sqlite3.connect(test_db)
    conn.execute(
        "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, dept TEXT, salary REAL)"
    )
    conn.executemany(
        "INSERT INTO employees VALUES (?,?,?,?)",
        [
            (1, "Alice", "Engineering", 95000),
            (2, "Bob", "Marketing", 72000),
            (3, "Carol", "Engineering", 105000),
        ],
    )
    conn.commit()
    conn.close()

    reg2 = DatabaseRegistry("data/raw/spider/database")
    reg2.register_upload_dir(tmpdir)

    dbs2 = reg2.list_databases()
    found = any(d["db_id"] == "mycompany" for d in dbs2)
    check("Uploaded DB appears in list_databases()", found)

    up_path = reg2.get_db_path("mycompany")
    check("get_db_path finds uploaded DB", up_path is not None and up_path.exists())

    info = reg2.get_db_info_from_path(str(test_db), "mycompany")
    check(
        "get_db_info_from_path returns tables", len(info["tables"]) == 1, f"tables={info['tables']}"
    )
    check("table count correct", info["table_count"] == 1)

    # Ensure uploaded DB can serve schema
    ddl2 = reg2.get_schema_ddl("mycompany")
    check("Schema DDL works for uploaded DB", "employees" in ddl2)

finally:
    shutil.rmtree(tmpdir)

# ─── 4. Demo mode allowlist ───────────────────────────────────
print("\n[4] Demo Mode Security")
os.environ["APP_PROFILE"] = "demo"
os.environ["DEMO_DB_ALLOWLIST"] = "chinook_1"
reg3 = DatabaseRegistry("data/raw/spider/database")

# Should block spider databases
blocked = reg3.get_db_path("concert_singer")
check("Demo mode blocks concert_singer", blocked is None)

# Should block academic too
blocked2 = reg3.get_db_path("academic")
check("Demo mode blocks academic", blocked2 is None)

os.environ.pop("APP_PROFILE", None)
os.environ.pop("DEMO_DB_ALLOWLIST", None)

# ─── 5. Safety executor (read-only enforcement) ───────────────
print("\n[5] Safety Guardrail — Validator")

policy = SafetyPolicy.load()
validator = SQLValidator(policy)

cases = [
    ("SELECT name FROM singer", True, "basic SELECT"),
    ("DROP TABLE singer", False, "DROP blocked"),
    ("INSERT INTO t VALUES(1)", False, "INSERT blocked"),
    ("UPDATE t SET x=1", False, "UPDATE blocked"),
    ("DELETE FROM t", False, "DELETE blocked"),
    ("SELECT * FROM sqlite_master", False, "sqlite_master blocked"),
    ("SELECT name FROM singer; DROP TABLE singer", False, "multi-statement blocked"),
]

for sql, should_allow, label in cases:
    v = validator.validate(sql)
    ok = v.allowed == should_allow
    check(
        f"Validator: {label}",
        ok,
        f"allowed={v.allowed} expected={should_allow}"
        + (f" reasons={v.reasons}" if not ok else ""),
    )

# ─── 6. SafeSQLExecutor (read-only sandbox) ───────────────────
print("\n[6] Safe Executor — Read-Only Sandbox")

executor = SafeSQLExecutor(timeout_seconds=5.0, max_rows=100)
concert_path = str(DatabaseRegistry("data/raw/spider/database").get_db_path("concert_singer"))

# Should work — NOTE: signature is execute_read_only(db_path, sql)
r = executor.execute_read_only(concert_path, "SELECT COUNT(*) FROM singer")
check(
    "SELECT COUNT(*) executes", r.success and r.row_count > 0, f"rows={r.rows} count={r.row_count}"
)
check("SELECT returns columns", len(r.columns) > 0, f"columns={r.columns}")

# Should be blocked at executor level (PRAGMA query_only + authorizer)
r2 = executor.execute_read_only(concert_path, "DROP TABLE singer")
check("DROP TABLE blocked at executor", not r2.success, f"error={str(r2.error)[:80]}")

# INSERT blocked
r3 = executor.execute_read_only(concert_path, "INSERT INTO singer VALUES(999,'Test','US',25.0)")
check("INSERT blocked at executor", not r3.success, f"error={str(r3.error)[:80]}")

# Verify row limit applied
r4 = executor.execute_read_only(concert_path, "SELECT * FROM singer")
check(
    "Row limit enforced",
    r4.row_count <= executor.max_rows,
    f"returned={r4.row_count} limit={executor.max_rows} truncated={r4.truncated}",
)

# ─── 7. Full service query flow (mock backend) ─────────────────
print("\n[7] Full Service Query — Mock Backend")

svc = Text2SQLService(
    backend_name="mock", model_path="mock", db_base_dir="data/raw/spider/database"
)

result = svc.process_query(
    db_id="concert_singer",
    question="How many singers are there?",
    include_sample_rows=False,
    enable_consensus=False,
    n_samples=1,
)

check("process_query returns result", isinstance(result, dict))
check("result has 'sql' key", "sql" in result)
check("result has 'allowed' key", "allowed" in result)
check("result has 'timings_ms' key", "timings_ms" in result)
check("request_id is present", bool(result.get("request_id")))

# ─── Summary ──────────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(1 for s, _, _ in results if s == PASS)
failed = sum(1 for s, _, _ in results if s == FAIL)
warned = sum(1 for s, _, _ in results if s == WARN)
print(f"  RESULTS: {passed} passed  |  {failed} failed  |  {warned} warnings")
print("=" * 60 + "\n")

if failed:
    print("  FAILED TESTS:")
    for s, label, detail in results:
        if s == FAIL:
            print(f"    - {label}: {detail}")

sys.exit(0 if failed == 0 else 1)
