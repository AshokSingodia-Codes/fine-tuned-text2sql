"""Unit test verifying that red-team block rates in README and RESUME_NUMBERS match results/redteam_latest.json."""

import json
import re
from pathlib import Path


def test_redteam_block_rate_matches_json() -> None:
    redteam_p = Path("results/redteam_latest.json")
    assert redteam_p.exists(), "results/redteam_latest.json must exist"

    with open(redteam_p, "r", encoding="utf-8") as f:
        data = json.load(f)

    path_a = data.get("path_a", {}).get("summary", {})
    rate_info = path_a.get("attack_block_rate", {})

    k = rate_info.get("k")
    n = rate_info.get("n")
    rate_pct = f"{rate_info.get('rate', 0.0) * 100:.2f}%"

    pattern = re.compile(rf"{re.escape(rate_pct)}.*?\(?{k}\s*/\s*{n}\)?")

    # Verify README.md
    readme_txt = Path("README.md").read_text(encoding="utf-8")
    assert pattern.search(
        readme_txt
    ), f"Expected pattern for '{rate_pct} ({k} / {n})' in README.md"

    # Verify docs/RESUME_NUMBERS.md
    rn_txt = Path("docs/RESUME_NUMBERS.md").read_text(encoding="utf-8")
    assert pattern.search(
        rn_txt
    ), f"Expected pattern for '{rate_pct} ({k} / {n})' in docs/RESUME_NUMBERS.md"
