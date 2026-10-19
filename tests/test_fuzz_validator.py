"""Property-based fuzz testing for SQLValidator using Hypothesis."""

import hashlib
import json
import sqlite3
import time
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from src.t2s.safety.policy import SafetyPolicy
from src.t2s.safety.validator import SQLValidator

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Load sample gold queries for mutation seeds
_DEV_PATH = PROJECT_ROOT / "data" / "raw" / "spider" / "dev.json"
_SEED_QUERIES = [
    "SELECT count(*) FROM singer",
    "SELECT name, country, age FROM singer WHERE age > 20 ORDER BY age DESC",
    "SELECT avg(age) FROM singer WHERE country = 'France'",
    "SELECT country, count(*) FROM singer GROUP BY country HAVING count(*) > 1",
    "SELECT t1.name, t2.song_name FROM singer as t1 JOIN song as t2 ON t1.singer_id = t2.singer_id",
]
if _DEV_PATH.exists():
    try:
        with open(_DEV_PATH, "r", encoding="utf-8") as f:
            dev_data = json.load(f)
            _SEED_QUERIES.extend([item["query"] for item in dev_data[:50]])
    except Exception:
        pass


def _mutate_sql(base: str, mutation_type: str, param: str) -> str:
    """Apply deterministic structural mutations to seed SQL queries."""
    if mutation_type == "insert":
        pos = len(base) // 2
        return base[:pos] + " " + param + " " + base[pos:]
    elif mutation_type == "case_flip":
        return "".join(c.swapcase() if i % 2 == 0 else c for i, c in enumerate(base))
    elif mutation_type == "comment_inject":
        return base + f" -- {param}"
    elif mutation_type == "block_comment":
        return f"/* {param} */ {base} /* end */"
    elif mutation_type == "truncate":
        cut = max(5, min(len(base) - 1, int(param) if param.isdigit() else 10))
        return base[:cut]
    elif mutation_type == "nesting":
        return f"SELECT * FROM ({base}) AS nested_table"
    elif mutation_type == "stacked":
        return f"{base}; {param};"
    elif mutation_type == "whitespace_unicode":
        return base.replace(" ", f" {param} ")
    return base + " " + param


# Hypothesis strategies
_seed_strategy = st.sampled_from(_SEED_QUERIES)
_mutation_strategy = st.sampled_from(
    [
        "insert",
        "case_flip",
        "comment_inject",
        "block_comment",
        "truncate",
        "nesting",
        "stacked",
        "whitespace_unicode",
        "raw",
    ]
)
_tokens_strategy = st.sampled_from(
    [
        "DROP TABLE users",
        "DELETE FROM t",
        "UPDATE x SET y=1",
        "-- comment",
        "/* bypass */",
        ";",
        "' OR '1'='1",
        "UNION SELECT password FROM users",
        "sqlite_master",
        "load_extension('evil.so')",
        "randomblob(1000000)",
        "\x00",
        "\r\n\t",
        "\ufeff",
        "WHERE 1=1",
        "HAVING 1=1",
    ]
)
_raw_text_strategy = st.text(min_size=0, max_size=500)


@st.composite
def fuzz_sql_strategy(draw):
    strategy_mode = draw(st.sampled_from(["mutate", "raw_text", "combined"]))
    if strategy_mode == "mutate":
        base = draw(_seed_strategy)
        m_type = draw(_mutation_strategy)
        token = draw(_tokens_strategy)
        return _mutate_sql(base, m_type, token)
    elif strategy_mode == "raw_text":
        return draw(_raw_text_strategy)
    else:
        base = draw(_seed_strategy)
        text = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789;'-/* ", max_size=50))
        return f"{base} {text}"


@settings(
    max_examples=1000,
    derandomize=False,
    print_blob=True,
    deadline=None,
)
@given(query=fuzz_sql_strategy())
def test_validator_fuzz_invariants(query: str):
    validator = SQLValidator(SafetyPolicy.load("config/security_policy.yaml"))

    # Invariant 1: Never raises unhandled exception
    t0 = time.perf_counter()
    verdict1 = validator.validate(query)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    # Invariant 2: Deterministic
    verdict2 = validator.validate(query)
    assert verdict1.allowed == verdict2.allowed, "Validator must be strictly deterministic"
    assert verdict1.reasons == verdict2.reasons, "Reasons must be strictly deterministic"

    # Invariant 3: Completes within reasonable latency bound (< 150 ms per sample)
    assert elapsed_ms < 150.0, f"Validator exceeded latency threshold: {elapsed_ms:.2f} ms"

    # Invariant 4 & 5: Independent Oracle & Exactly One Statement
    if verdict1.allowed:
        rewritten = verdict1.rewritten_sql
        assert rewritten, "Allowed queries must provide non-empty rewritten SQL"

        # Invariant 5: Allowed output is exactly one statement
        clean_rewritten = rewritten.rstrip(";").strip()
        # Must not contain multiple statements
        assert ";" not in clean_rewritten, "Allowed rewritten SQL must contain only one statement"
        # Must be SELECT or WITH
        upper_start = clean_rewritten.strip().upper()
        assert upper_start.startswith("SELECT") or upper_start.startswith("WITH"), (
            f"Allowed query did not start with SELECT or WITH: {rewritten}"
        )

        # Invariant 4: Execute on throwaway SQLite DB opened READ-WRITE; file hash must remain unchanged
        tmp_db_path = PROJECT_ROOT / "results" / f"fuzz_oracle_{time.time_ns()}.sqlite"
        tmp_db_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(tmp_db_path)
            conn.execute("CREATE TABLE singer (singer_id INT, name TEXT, age INT);")
            conn.execute("INSERT INTO singer VALUES (1, 'Alice', 25);")
            conn.commit()
            conn.close()

            # Measure initial hash
            with open(tmp_db_path, "rb") as f:
                initial_hash = hashlib.sha256(f.read()).hexdigest()

            # Execute allowed query on read-write connection
            conn_rw = sqlite3.connect(tmp_db_path)
            try:
                cur = conn_rw.cursor()
                cur.execute(rewritten)
                _ = cur.fetchall()
            except Exception:
                # Execution error on valid read query (e.g. unknown column) is OK
                pass
            finally:
                conn_rw.close()

            # Assert DB file hash unchanged (no write/drop/alter occurred)
            with open(tmp_db_path, "rb") as f:
                post_hash = hashlib.sha256(f.read()).hexdigest()

            assert initial_hash == post_hash, (
                f"INDEPENDENT ORACLE VIOLATION: Database file modified by allowed query: {rewritten}"
            )
        finally:
            if tmp_db_path.exists():
                tmp_db_path.unlink()
