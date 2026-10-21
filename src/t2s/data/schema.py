"""SQLite schema reader and DDL serializer."""

import sqlite3
from pathlib import Path
from typing import List, Optional


def get_sqlite_schema_ddl(
    db_path: str, include_sample_rows: bool = False, num_sample_rows: int = 3
) -> str:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Database file not found: {db_path}")

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    cursor = conn.cursor()

    # Get sorted table names (excluding internal sqlite tables)
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
    )
    tables = [row[0] for row in cursor.fetchall()]

    ddl_statements: List[str] = []

    for table in tables:
        # Get column info: cid, name, type, notnull, dflt_value, pk
        cursor.execute(f"PRAGMA table_info('{table}');")
        col_info = cursor.fetchall()
        if not col_info:
            continue

        columns_def: List[str] = []
        pk_cols: List[str] = []
        for col in col_info:
            col_name = col[1]
            col_type = col[2] if col[2] else "TEXT"
            is_pk = col[5]
            if is_pk:
                pk_cols.append(col_name)
            columns_def.append(f"  {col_name} {col_type}")

        # Get foreign keys: id, seq, table, from, to, on_update, on_delete, match
        cursor.execute(f"PRAGMA foreign_key_list('{table}');")
        fk_info = cursor.fetchall()
        fk_defs: List[str] = []
        for fk in fk_info:
            from_col = fk[3]
            target_table = fk[2]
            to_col = fk[4]
            if from_col and target_table and to_col:
                fk_defs.append(f"  FOREIGN KEY ({from_col}) REFERENCES {target_table}({to_col})")

        if pk_cols:
            pk_str = ", ".join(pk_cols)
            columns_def.append(f"  PRIMARY KEY ({pk_str})")

        columns_def.extend(fk_defs)

        table_ddl = f"CREATE TABLE {table} (\n" + ",\n".join(columns_def) + "\n);"

        if include_sample_rows:
            try:
                cursor.execute(f"SELECT * FROM '{table}' LIMIT {num_sample_rows};")
                sample_rows = cursor.fetchall()
                if sample_rows:
                    sample_comments = ["-- Example rows:"]
                    for row in sample_rows:
                        row_str = ", ".join(
                            "NULL"
                            if val is None
                            else f"'{str(val)[:50]}'"
                            if isinstance(val, str)
                            else str(val)
                            for val in row
                        )
                        sample_comments.append(f"-- ({row_str})")
                    table_ddl += "\n" + "\n".join(sample_comments)
            except Exception:
                pass

        ddl_statements.append(table_ddl)

    conn.close()
    return "\n\n".join(ddl_statements)
