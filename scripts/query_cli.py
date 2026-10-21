#!/usr/bin/env python3
"""
Text-to-SQL CLI — Query any SQLite database in plain English.

Usage examples
--------------
# Quick one-shot query (mock backend, instant):
  python scripts/query_cli.py --db mydb.sqlite --question "How many users signed up last month?"

# Use real GGUF model (requires ~2 GB model file):
  python scripts/query_cli.py \\
      --db mydb.sqlite \\
      --question "Top 5 products by revenue" \\
      --backend llama_cpp \\
      --model models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf

# Interactive REPL mode — ask multiple questions:
  python scripts/query_cli.py --db mydb.sqlite --interactive

# Validate a hand-written SQL query through the safety guardrail:
  python scripts/query_cli.py --validate "SELECT * FROM users WHERE id = 1"

# Point at a whole directory of .sqlite files:
  python scripts/query_cli.py --db-dir /path/to/databases/ --db mydb --question "..."
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Allow running from repo root without pip install -e .
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _build_service(db_path: str, backend: str, model_path: str):
    """Build the Text2SQLService pointing at a single sqlite file."""
    from src.t2s.serving.dbs import DatabaseRegistry
    from src.t2s.serving.service import Text2SQLService

    db_file = Path(db_path).resolve()
    if not db_file.exists():
        print(f"[ERROR] Database file not found: {db_file}", file=sys.stderr)
        sys.exit(1)

    db_dir = str(db_file.parent)
    svc = Text2SQLService(backend_name=backend, model_path=model_path, db_base_dir=db_dir)
    # Also register the file's directory so flat .sqlite files are found
    svc.db_registry.register_upload_dir(db_dir)
    return svc, db_file.stem


def _run_query(svc, db_id: str, question: str, consensus: bool, n_samples: int) -> dict:
    return svc.process_query(
        db_id=db_id,
        question=question,
        include_sample_rows=False,
        enable_consensus=consensus,
        n_samples=n_samples,
    )


def _print_result(result: dict, json_out: bool = False) -> None:
    if json_out:
        print(json.dumps(result, indent=2, default=str))
        return

    allowed = result.get("allowed", False)
    sql = result.get("sql", "")
    reasons = result.get("reasons", [])
    rows = result.get("rows", [])
    columns = result.get("columns", [])
    timings = result.get("timings_ms", {})

    print()
    if allowed:
        print("  [OK] ALLOWED", end="")
    else:
        print("  [!!] BLOCKED BY GUARDRAIL", end="")

    if result.get("consensus_score"):
        print(f"  [Consensus: {result['consensus_score']} agreed]", end="")
    if result.get("retried"):
        print("  [Self-corrected]", end="")
    print()

    print(f"\n  Generated SQL:\n  {'-'*60}")
    for line in (sql or "-- No SQL generated").splitlines():
        print(f"  {line}")

    if not allowed and reasons:
        print(f"\n  Block reason(s):")
        for r in reasons:
            print(f"    - {r}")

    if allowed and columns:
        print(f"\n  Results ({result.get('row_count', len(rows))} rows):")
        col_w = [max(len(str(c)), max((len(str(r[i])) for r in rows), default=0)) for i, c in enumerate(columns)]
        header = "  | " + " | ".join(str(c).ljust(col_w[i]) for i, c in enumerate(columns)) + " |"
        sep = "  +" + "+".join("-" * (w + 2) for w in col_w) + "+"
        print(sep)
        print(header)
        print(sep)
        for row in rows[:50]:
            print("  | " + " | ".join(str(v if v is not None else "NULL").ljust(col_w[i]) for i, v in enumerate(row)) + " |")
        print(sep)
        if result.get("row_count", 0) > 50:
            print(f"  ... (showing 50 of {result['row_count']} rows)")

    t_total = timings.get("total_ms", 0)
    t_inf = timings.get("inference_ms", 0)
    t_exec = timings.get("execution_ms", 0)
    print(f"\n  Timing: total={t_total}ms  inference={t_inf}ms  execution={t_exec}ms")
    print()


def _validate_mode(sql: str) -> None:
    from src.t2s.safety.policy import SafetyPolicy
    from src.t2s.safety.validator import SQLValidator

    policy = SafetyPolicy.load()
    validator = SQLValidator(policy)
    verdict = validator.validate(sql)
    print()
    if verdict.allowed:
        print("  [OK] ALLOWED by AST guardrail")
        if verdict.rewritten_sql and verdict.rewritten_sql != sql:
            print(f"  Rewritten: {verdict.rewritten_sql}")
    else:
        print("  [!!] BLOCKED by AST guardrail")
        for r in verdict.reasons:
            print(f"    - {r}")
    print()


def _interactive_mode(svc, db_id: str, consensus: bool, n_samples: int) -> None:
    print(f"\n  Text-to-SQL Interactive REPL  [db: {db_id}]")
    print("  Type your question in plain English. Type 'exit' or Ctrl-C to quit.\n")
    while True:
        try:
            question = input("  > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Goodbye.")
            break
        if not question:
            continue
        if question.lower() in ("exit", "quit", "q"):
            print("  Goodbye.")
            break
        result = _run_query(svc, db_id, question, consensus, n_samples)
        _print_result(result)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Text-to-SQL CLI — Query any SQLite database in plain English.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Database source
    db_group = parser.add_mutually_exclusive_group()
    db_group.add_argument("--db", metavar="FILE.sqlite",
                          help="Path to a SQLite database file")
    db_group.add_argument("--db-dir", metavar="DIR",
                          help="Directory containing .sqlite files (use with --db-id)")

    parser.add_argument("--db-id", metavar="NAME",
                        help="Database ID when using --db-dir (filename without extension)")

    # Query / mode
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--question", "-q", metavar="TEXT",
                      help="Natural language question to convert to SQL and execute")
    mode.add_argument("--interactive", "-i", action="store_true",
                      help="Start an interactive REPL session")
    mode.add_argument("--validate", metavar="SQL",
                      help="Validate a raw SQL string through the safety guardrail (no model needed)")

    # Model backend
    parser.add_argument("--backend", default="mock",
                        choices=["mock", "llama_cpp", "openai_compat"],
                        help="Inference backend (default: mock — no model required)")
    parser.add_argument("--model", default="models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf",
                        metavar="PATH",
                        help="Path to model weights (GGUF for llama_cpp backend)")

    # Options
    parser.add_argument("--no-consensus", action="store_true",
                        help="Disable majority voting (faster, less accurate)")
    parser.add_argument("--n-samples", type=int, default=5,
                        help="Number of SQL candidates for voting (default: 5)")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON result (machine-readable)")
    parser.add_argument("--list-tables", action="store_true",
                        help="List all tables and row counts in the database (no query)")

    args = parser.parse_args()

    # -- Validate-only mode (no DB needed) ------------------------
    if args.validate:
        _validate_mode(args.validate)
        return

    # -- Resolve database -----------------------------------------
    if args.db_dir:
        db_dir = Path(args.db_dir)
        if not args.db_id:
            # List available databases (flat + nested spider-style)
            flat  = sorted(p.stem for p in db_dir.glob("*.sqlite"))
            nested = sorted(p.parent.name for p in db_dir.glob("*/*.sqlite"))
            all_dbs = sorted(set(flat + nested))
            if not all_dbs:
                print(f"[ERROR] No .sqlite files found in: {db_dir}", file=sys.stderr)
                sys.exit(1)
            print(f"\n  Available databases in {db_dir} ({len(all_dbs)} total):")
            for d in all_dbs:
                print(f"    - {d}")
            print(f"\n  Re-run with --db-id <name> to select one.\n")
            return
        db_path = str(Path(args.db_dir) / f"{args.db_id}.sqlite")
        # Also check nested spider-style
        if not Path(db_path).exists():
            db_path = str(Path(args.db_dir) / args.db_id / f"{args.db_id}.sqlite")
        svc, db_id = _build_service(db_path, args.backend, args.model)
        db_id = args.db_id
    elif args.db:
        svc, db_id = _build_service(args.db, args.backend, args.model)
    else:
        parser.print_help()
        print("\n[ERROR] Provide --db <file> or --db-dir <dir>\n", file=sys.stderr)
        sys.exit(1)

    consensus = not args.no_consensus

    # -- List tables mode -----------------------------------------
    if args.list_tables:
        import sqlite3 as _sq
        db_path_obj = Path(args.db if args.db else
                           str(Path(args.db_dir) / args.db_id / f"{args.db_id}.sqlite"))
        if not db_path_obj.exists():
            db_path_obj = Path(args.db_dir) / f"{args.db_id}.sqlite"
        print(f"\n  Tables in [{db_id}]  ({db_path_obj.stat().st_size // 1024} KB)")
        print(f"  {'-'*48}")
        try:
            conn = _sq.connect(str(db_path_obj))
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in c.fetchall() if not r[0].startswith("sqlite_")]
            for tbl in tables:
                try:
                    c.execute(f'SELECT COUNT(*) FROM "{tbl}"')  # noqa
                    cnt = c.fetchone()[0]
                except Exception:
                    cnt = "?"
                print(f"  {tbl:<40} {cnt:>8} rows")
            conn.close()
        except Exception as e:
            print(f"  Error: {e}")
        print()
        return

    # -- Run mode -------------------------------------------------
    if args.interactive:
        _interactive_mode(svc, db_id, consensus, args.n_samples)
    elif args.question:
        result = _run_query(svc, db_id, args.question, consensus, args.n_samples)
        _print_result(result, json_out=args.json)
    else:
        print(f"\n  Connected to database: {db_id}")
        print("  Use --question 'your question' or --interactive\n")


if __name__ == "__main__":
    main()
