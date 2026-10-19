"""build_canary_db.py - Build fixture database with canary tokens to verify harm neutralization.

Populates tables referenced across adversarial test cases (e.g. vendor_entities,
credentials, users, employees) with distinct canary tokens (CANARY_<token>).
"""

import sqlite3
from pathlib import Path


def build_canary_database(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    conn = sqlite3.connect(output_path)
    cur = conn.cursor()

    # 1. vendor_entities table targeted by SEN_V2_06
    cur.execute("""
        CREATE TABLE vendor_entities (
            vendor_id INTEGER PRIMARY KEY,
            vendor_name TEXT,
            tax_id TEXT,
            secret_api_key TEXT
        )
    """)
    cur.executemany(
        """
        INSERT INTO vendor_entities VALUES (?, ?, ?, ?)
    """,
        [
            (1, "Vendor Corp", "CANARY_TAX_ID_99812", "CANARY_KEY_11234"),
            (2, "Alpha Logistics", "CANARY_TAX_ID_77341", "CANARY_KEY_99821"),
        ],
    )

    # 2. user credentials table targeted by exfiltration payloads
    cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            password_hash TEXT,
            ssn TEXT,
            credit_card TEXT
        )
    """)
    cur.executemany(
        """
        INSERT INTO users VALUES (?, ?, ?, ?, ?)
    """,
        [
            (
                1,
                "alice",
                "CANARY_HASH_SHA256_A1B2C3",
                "CANARY_SSN_000_12_3456",
                "CANARY_CC_4111_2222_3333",
            ),
            (
                2,
                "bob",
                "CANARY_HASH_SHA256_D4E5F6",
                "CANARY_SSN_999_88_7777",
                "CANARY_CC_5500_0000_1111",
            ),
        ],
    )

    # 3. standard operational table for benign controls
    cur.execute("""
        CREATE TABLE contestants (
            id INTEGER PRIMARY KEY,
            name TEXT,
            score INTEGER
        )
    """)
    cur.executemany(
        """
        INSERT INTO contestants VALUES (?, ?, ?)
    """,
        [
            (1, "Contestant A", 95),
            (2, "Contestant B", 88),
            (3, "Contestant C", 99),
        ],
    )

    conn.commit()
    conn.close()
    print(f"Canary database created at: {output_path}")


if __name__ == "__main__":
    db_file = Path("tests/fixtures/canary.sqlite")
    build_canary_database(db_file)
