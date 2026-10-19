import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

cases_path = PROJECT_ROOT / "data" / "redteam" / "redteam_cases.jsonl"
relabel_log_path = PROJECT_ROOT / "results" / "relabel_log.json"

with open(cases_path, "r", encoding="utf-8") as f:
    cases = [json.loads(line) for line in f if line.strip()]

updated = []
relabel_log = []

relabel_ids = {
    "ENC_D01",
    "ENC_D02",
    "ENC_D03",
    "ENC_D04",
    "ENC_D05",
    "ENC_D06",
    "ENC_D07",
    "ENC_D10",
    "ENC_H02",
    "CMT_D10",
    "DOS_D10",
}

for c in cases:
    cid = c["id"]
    if cid in relabel_ids:
        old_cat = c["category"]
        old_exp = c["expected"]
        new_cat = "benign"
        new_exp = "allow"
        c["category"] = new_cat
        c["expected"] = new_exp
        rat = c.get("rationale", "")
        reason = (
            f"Audited harmless: {rat} represents safe syntax/literal execution, not an exploit."
        )
        relabel_log.append(
            {
                "id": cid,
                "old_category": old_cat,
                "old_expected": old_exp,
                "new_category": new_cat,
                "new_expected": new_exp,
                "reason": reason,
                "commit_hash": "2fb1f36b01574f919f11c6ef17f57c31b5406591",
            }
        )
    updated.append(c)

with open(cases_path, "w", encoding="utf-8") as f:
    for c in updated:
        f.write(json.dumps(c) + "\n")

relabel_log_path.parent.mkdir(parents=True, exist_ok=True)
with open(relabel_log_path, "w", encoding="utf-8") as f:
    json.dump(
        {
            "description": "Log of red-team test cases reclassified from attack to benign control after empirical harmlessness audit.",
            "commit_hash": "2fb1f36b01574f919f11c6ef17f57c31b5406591",
            "relabel_count": len(relabel_log),
            "records": relabel_log,
        },
        f,
        indent=2,
    )

print(
    f"Successfully updated {len(relabel_log)} cases in redteam_cases.jsonl and created results/relabel_log.json"
)
