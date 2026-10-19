"""Package repository files for Google Colab Phase 1 execution.

Builds phase1_bundle.zip in the repository root containing source, data,
scripts, notebooks, tests, requirements, and documentation.
Excludes virtual environments, git data, mock outputs, and large model binaries.
"""

import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def package_for_colab() -> None:
    spider_db_dir = PROJECT_ROOT / "data" / "raw" / "spider" / "database"
    if not spider_db_dir.exists() or not spider_db_dir.is_dir():
        print(
            f"ERROR: Missing Spider database directory at '{spider_db_dir}'. "
            "Please ensure Spider databases are downloaded before bundling.",
            file=sys.stderr,
        )
        sys.exit(1)

    zip_path = PROJECT_ROOT / "phase1_bundle.zip"
    if zip_path.exists():
        zip_path.unlink()

    included_dirs = [
        "src",
        "scripts",
        "notebooks",
        "tests",
        "data/processed",
        "data/raw/spider",
        "docs",
    ]

    included_patterns = [
        "requirements*.txt",
        "pyproject.toml",
        "AGENTS.md",
        "PLAN.md",
        "README.md",
    ]

    excluded_parts = {
        ".venv",
        ".git",
        "__pycache__",
        "merged_model",
        "smoke",
        ".pytest_cache",
        "phase1_bundle.zip",
        "phase1_results.zip",
    }

    files_to_add = []

    # Gather matching root files
    for root_file in PROJECT_ROOT.glob("*"):
        if root_file.is_file():
            if any(root_file.match(pat) for pat in included_patterns):
                files_to_add.append(root_file)

    # Gather matching directory contents
    for d in included_dirs:
        dir_path = PROJECT_ROOT / d
        if not dir_path.exists():
            continue
        for path in dir_path.rglob("*"):
            if not path.is_file():
                continue

            rel = path.relative_to(PROJECT_ROOT)
            parts = rel.parts

            # Check exclusions
            if any(ex in parts for ex in excluded_parts):
                continue
            if path.suffix == ".gguf" or path.suffix == ".safetensors":
                continue

            files_to_add.append(path)

    print(f"Bundling {len(files_to_add)} files into {zip_path.name}...")

    top_level_entries = set()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in files_to_add:
            arcname = file_path.relative_to(PROJECT_ROOT).as_posix()
            zf.write(file_path, arcname=arcname)
            top_level_entries.add(arcname.split("/")[0])

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"Successfully created {zip_path.name} ({size_mb:.2f} MB).")
    print(f"Top-level zip entries: {sorted(list(top_level_entries))}")


if __name__ == "__main__":
    package_for_colab()
