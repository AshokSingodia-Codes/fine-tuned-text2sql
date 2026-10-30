#!/usr/bin/env python3
"""Interactive Launcher for Fine-Tuned Text-to-SQL Assistant.

Provides a clean interactive menu to query databases, start the web interface,
validate SQL safety, or run the test suite.
"""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def print_banner() -> None:
    print("=" * 64)
    print("  🛡️  Fine-Tuned Text-to-SQL Assistant (Safe Local LLM Serving)")
    print("=" * 64)
    print("  1. 💬 Ask Questions in Terminal (Interactive CLI / REPL)")
    print("  2. 🌐 Start Local Web Interface (FastAPI + React UI)")
    print("  3. 🛡️  Validate a Raw SQL Query (Safety Guardrail Check)")
    print("  4. 🧪 Run Verification & Test Suite (pytest)")
    print("  5. 🚪 Exit")
    print("=" * 64)


def run_interactive_cli() -> None:
    cli_script = PROJECT_ROOT / "scripts" / "query_cli.py"
    subprocess.run([sys.executable, str(cli_script)])


def run_web_interface() -> None:
    print("\n  Starting FastAPI Serving Backend on http://localhost:8000...")
    print("  To launch the React UI, open a second terminal and run:")
    print("    cd frontend && npm install && npm run dev\n")
    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "src.t2s.serving.app:app",
                "--port",
                "8000",
                "--reload",
            ]
        )
    except KeyboardInterrupt:
        print("\n  Web backend stopped.")


def run_sql_validator() -> None:
    print("\n  Enter a SQL statement to test against AST safety rules:")
    query = input("  SQL> ").strip()
    if query:
        cli_script = PROJECT_ROOT / "scripts" / "query_cli.py"
        subprocess.run([sys.executable, str(cli_script), "--validate", query])
    input("  Press Enter to return to menu...")


def run_tests() -> None:
    print("\n  Running test suite (pytest -q)...")
    subprocess.run([sys.executable, "-m", "pytest", "-q"])
    input("\n  Press Enter to return to menu...")


def main() -> None:
    while True:
        clear_screen()
        print_banner()
        choice = input("  Select an option (1-5): ").strip()
        if choice == "1":
            run_interactive_cli()
            input("\n  Press Enter to return to menu...")
        elif choice == "2":
            run_web_interface()
            input("\n  Press Enter to return to menu...")
        elif choice == "3":
            run_sql_validator()
        elif choice == "4":
            run_tests()
        elif choice in ("5", "q", "exit"):
            print("\n  Goodbye!\n")
            break
        else:
            print(f"  Invalid selection '{choice}'. Please select 1, 2, 3, 4, or 5.")
            input("  Press Enter to continue...")


if __name__ == "__main__":
    main()
