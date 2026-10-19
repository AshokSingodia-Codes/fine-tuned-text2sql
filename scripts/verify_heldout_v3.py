"""Verification harness for independent heldout_v3 dataset.

Refuses to run evaluation unless:
1. data/redteam/heldout_v3_cases.jsonl exists with valid schema.
2. data/redteam/heldout_v3.sha256 exists and matches.
3. The dataset file is tracked and committed in git (verified via git status / log).
4. Prints the git commit hash and SHA-256 before allowing any evaluation.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_v3() -> bool:
    v3_path = PROJECT_ROOT / "data" / "redteam" / "heldout_v3_cases.jsonl"
    sha_path = PROJECT_ROOT / "data" / "redteam" / "heldout_v3.sha256"

    if not v3_path.exists():
        print("ERROR: data/redteam/heldout_v3_cases.jsonl does not exist.")
        print("The user must place the independent heldout_v3 dataset before running verification.")
        return False

    if not sha_path.exists():
        print("ERROR: data/redteam/heldout_v3.sha256 does not exist.")
        return False

    computed = compute_sha256(v3_path)
    with open(sha_path, "r", encoding="utf-8") as f:
        expected = f.read().strip()

    if computed != expected:
        print(f"ERROR: SHA-256 mismatch for heldout_v3 ({computed} != {expected}).")
        return False

    # Check git tracking and commit status
    try:
        git_log = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%H %s", "--", str(v3_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        if not git_log.stdout.strip():
            print("ERROR: heldout_v3_cases.jsonl is not committed in git!")
            print("Integrity policy requires the file to be committed before evaluation.")
            return False

        commit_info = git_log.stdout.strip()
    except Exception as e:
        print(f"ERROR: Failed checking git status for heldout_v3: {e}")
        return False

    # Validate schema
    required_keys = {"id", "category", "path", "payload", "expected"}
    total_cases = 0
    with open(v3_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            if not line.strip():
                continue
            total_cases += 1
            try:
                item = json.loads(line)
            except Exception as e:
                print(f"ERROR: Invalid JSON on line {idx + 1}: {e}")
                return False
            missing = required_keys - set(item.keys())
            if missing:
                print(f"ERROR: Line {idx + 1} missing required keys: {missing}")
                return False

    print("==================================================")
    print("    HELDOUT_V3 DATASET VERIFICATION: SUCCESS      ")
    print("==================================================")
    print("Dataset Path:   data/redteam/heldout_v3_cases.jsonl")
    print(f"Total Cases:    {total_cases}")
    print(f"SHA-256:        {computed}")
    print(f"Commit Hash:    {commit_info}")
    print("==================================================")
    return True


if __name__ == "__main__":
    if not verify_v3():
        sys.exit(1)
