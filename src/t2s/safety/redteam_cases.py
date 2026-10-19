"""Adversarial Red-Team Test Cases for SQL Safety Layer evaluation."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class RedTeamCase:
    id: str
    category: str
    split: str
    path: str
    payload: str
    expected: str
    rationale: str
    source: str = "hand"

    @property
    def prompt_or_sql(self) -> str:
        """Backwards compatibility for Phase 0/1 test suites."""
        return self.payload

    @property
    def expected_blocked(self) -> bool:
        """Backwards compatibility for Phase 0/1 test suites."""
        return self.expected == "block"

    @property
    def description(self) -> str:
        """Backwards compatibility for Phase 0/1 test suites."""
        return self.rationale


def load_redteam_cases(filepath: str | Path | None = None) -> List[RedTeamCase]:
    """Load red-team cases from JSONL dataset."""
    if filepath is None:
        filepath = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "data"
            / "redteam"
            / "redteam_cases.jsonl"
        )
    else:
        filepath = Path(filepath)

    if not filepath.exists():
        return []

    cases: List[RedTeamCase] = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            cases.append(
                RedTeamCase(
                    id=data["id"],
                    category=data["category"],
                    split=data["split"],
                    path=data["path"],
                    payload=data["payload"],
                    expected=data["expected"],
                    rationale=data["rationale"],
                    source=data.get("source", "hand"),
                )
            )
    return cases


REDTEAM_CASES: List[RedTeamCase] = load_redteam_cases()
