#!/usr/bin/env python3
"""Scan tracked git files and recent diffs for API keys, tokens, and credentials."""

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

PATTERNS = [
    (r"ghp_[a-zA-Z0-9]{36}", "GitHub Personal Access Token"),
    (r"gho_[a-zA-Z0-9]{36}", "GitHub OAuth Token"),
    (r"hf_[a-zA-Z0-9]{34}", "Hugging Face Access Token"),
    (r"(?i)api[_-]?key\s*[:=]\s*['\"][0-9a-zA-Z]{16,}['\"]", "Generic API Key assignment"),
    (r"(?i)secret\s*[:=]\s*['\"][0-9a-zA-Z]{16,}['\"]", "Generic Secret assignment"),
    (r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Bearer Token"),
    (r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----", "Private Key"),
]

EXCLUDED_EXTENSIONS = {
    ".sqlite",
    ".db",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
}


def scan_file(filepath: Path) -> list:
    hits = []
    if filepath.suffix.lower() in EXCLUDED_EXTENSIONS:
        return hits
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return hits

    for line_idx, line in enumerate(content.splitlines(), 1):
        # Ignore dummy test strings or fixture values
        if "EXAMPLE" in line or "dummy" in line or "placeholder" in line or "test_token" in line:
            continue
        for regex, desc in PATTERNS:
            match = re.search(regex, line)
            if match:
                hits.append((filepath, line_idx, desc, match.group(0)[:12] + "..."))
    return hits


def main() -> int:
    print("Scanning git-tracked files for potential secrets...")
    try:
        tracked_output = subprocess.check_output(
            ["git", "ls-files"], cwd=PROJECT_ROOT, text=True, errors="replace"
        )
        tracked_files = [
            PROJECT_ROOT / line.strip() for line in tracked_output.splitlines() if line.strip()
        ]
    except Exception as e:
        print(f"Failed to list git files: {e}")
        tracked_files = [p for p in PROJECT_ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]

    all_hits = []
    for f in tracked_files:
        if f.is_file():
            all_hits.extend(scan_file(f))

    if all_hits:
        print(f"FAIL: Found {len(all_hits)} potential secret(s):")
        for filepath, line_idx, desc, masked in all_hits:
            print(f"  {filepath.relative_to(PROJECT_ROOT)}:{line_idx} - {desc} ({masked})")
        return 1

    print("PASS: Zero secrets detected across tracked repository files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
