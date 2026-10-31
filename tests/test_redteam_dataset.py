"""Tests for Red-Team dataset counts, split sizes, uniqueness, and hash integrity."""

import hashlib
import json
from pathlib import Path


def test_redteam_dataset_integrity():
    root = Path(__file__).resolve().parent.parent
    dataset_path = root / "data" / "redteam" / "redteam_cases.jsonl"
    heldout_path = root / "data" / "redteam" / "heldout_cases.jsonl"
    sha_file = root / "data" / "redteam" / "heldout.sha256"

    assert dataset_path.exists(), "data/redteam/redteam_cases.jsonl missing"
    assert heldout_path.exists(), "data/redteam/heldout_cases.jsonl missing"
    assert sha_file.exists(), "data/redteam/heldout.sha256 missing"

    # Verify SHA-256 of heldout dataset matches frozen hash (allowing for platform line endings)
    with open(heldout_path, "rb") as f:
        raw_bytes = f.read()
    computed_sha = hashlib.sha256(raw_bytes).hexdigest()
    computed_sha_lf = hashlib.sha256(raw_bytes.replace(b"\r\n", b"\n")).hexdigest()
    with open(sha_file, "r", encoding="utf-8") as f:
        expected_sha = f.read().strip()

    assert expected_sha in (computed_sha, computed_sha_lf), (
        f"Heldout SHA-256 mismatch! Expected {expected_sha}, got {computed_sha}"
    )

    # Load all cases
    all_cases = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_cases.append(json.loads(line))

    assert len(all_cases) >= 190, f"Expected at least 190 cases, got {len(all_cases)}"

    # Check unique IDs
    ids = [c["id"] for c in all_cases]
    assert len(ids) == len(set(ids)), "Case IDs must be strictly unique"

    # Check categories and splits
    sql_attack_categories = [
        "ddl_dml",
        "stacked_statements",
        "comment_smuggling",
        "system_table_sniffing",
        "sensitive_column_extraction",
        "resource_abuse_dos",
        "encoding_whitespace",
        "dangerous_functions",
    ]

    dev_cases = [c for c in all_cases if c["split"] == "dev"]
    heldout_cases = [c for c in all_cases if c["split"] == "heldout"]

    assert len(dev_cases) >= 130, f"Expected >= 130 dev cases, got {len(dev_cases)}"
    assert len(heldout_cases) >= 60, f"Expected >= 60 heldout cases, got {len(heldout_cases)}"

    # Load relabeled mapping to account for audited benign controls
    relabel_file = root / "results" / "relabel_log.json"
    relabel_map = {}
    if relabel_file.exists():
        with open(relabel_file, "r", encoding="utf-8") as f:
            relabel_data = json.load(f)
            relabel_map = {r["id"]: r["old_category"] for r in relabel_data.get("records", [])}

    for cat in sql_attack_categories:
        dev_cat = [c for c in dev_cases if c["category"] == cat or relabel_map.get(c["id"]) == cat]
        heldout_cat = [
            c for c in heldout_cases if c["category"] == cat or relabel_map.get(c["id"]) == cat
        ]

        # Total dev cases originating from category must be 10, heldout must be 5
        assert len(dev_cat) == 10, (
            f"Category {cat} must have 10 dev cases (including audited controls), got {len(dev_cat)}"
        )
        assert len(heldout_cat) == 5, (
            f"Category {cat} must have 5 heldout cases (including audited controls), got {len(heldout_cat)}"
        )

    # Prompt injection category (>= 60 cases: 40 dev, 20 heldout)
    dev_inj = [c for c in dev_cases if c["category"] == "prompt_injection"]
    heldout_inj = [c for c in heldout_cases if c["category"] == "prompt_injection"]
    assert len(dev_inj) >= 40, f"Expected >= 40 dev injection cases, got {len(dev_inj)}"
    assert len(heldout_inj) >= 20, f"Expected >= 20 heldout injection cases, got {len(heldout_inj)}"
    for c in dev_inj + heldout_inj:
        assert c["expected"] == "block"
        assert c["path"] == "nl"

    # Check benign controls
    benign_dev = [c for c in dev_cases if c["category"] == "benign"]
    benign_heldout = [c for c in heldout_cases if c["category"] == "benign"]

    assert len(benign_dev) >= 40, f"Expected >= 40 benign dev cases, got {len(benign_dev)}"
    assert len(benign_heldout) >= 15, (
        f"Expected >= 15 benign heldout cases, got {len(benign_heldout)}"
    )

    for c in benign_dev + benign_heldout:
        assert c["expected"] == "allow", f"Benign case {c['id']} must expect 'allow'"
        assert c["path"] == "sql", f"Benign case {c['id']} must have path='sql'"
