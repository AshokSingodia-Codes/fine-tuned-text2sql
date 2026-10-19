"""Unit tests proving mock backend safety guards."""

import json
import subprocess
import sys
from pathlib import Path


def test_mock_backend_limit_rejection() -> None:
    """Full run without limit or limit > 20 with mock backend must fail."""
    cmd = [sys.executable, "scripts/eval_spider.py", "--backend", "mock"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode != 0, "Full run with mock backend must exit with error"
    assert "strictly prohibited" in res.stderr.lower() or "error" in res.stderr.lower()

    cmd_limit_large = [
        sys.executable,
        "scripts/eval_spider.py",
        "--backend",
        "mock",
        "--limit",
        "100",
    ]
    res_large = subprocess.run(cmd_limit_large, capture_output=True, text=True)
    assert res_large.returncode != 0, "Run with limit > 20 and mock backend must exit with error"

    cmd_latency = [sys.executable, "scripts/bench_latency.py", "--backend", "mock"]
    res_lat = subprocess.run(cmd_latency, capture_output=True, text=True)
    assert res_lat.returncode != 0, "Full latency run with mock backend must exit with error"


def test_mock_backend_smoke_output_directory(tmp_path: Path) -> None:
    """Mock runs with limit <= 20 must write to results/smoke/ and print MOCK RUN warning."""
    latest_file = Path("results/eval_spider_latest.json")
    existed_before = latest_file.exists()
    mtime_before = latest_file.stat().st_mtime if existed_before else None

    cmd = [sys.executable, "scripts/eval_spider.py", "--backend", "mock", "--limit", "5"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0
    assert "MOCK RUN: NOT A REAL RESULT" in res.stdout

    if not existed_before:
        assert not latest_file.exists(), (
            "Mock run must NOT write to results/eval_spider_latest.json"
        )
    else:
        assert latest_file.stat().st_mtime == mtime_before, (
            "Mock run must NOT touch results/eval_spider_latest.json"
        )

    smoke_dir = Path("results/smoke")
    assert smoke_dir.exists()
    smoke_json_files = list(smoke_dir.glob("eval_spider_*.json"))
    assert len(smoke_json_files) > 0, "Mock run must write timestamped file to results/smoke/"

    with open(smoke_json_files[0], "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["metadata"]["backend_used"] == "mock", "Result JSON must include backend field"
