"""Load testing benchmark for Text-to-SQL API serving layer.

Tests throughput and latency percentiles (p50, p95, p99) under 1, 2, and 4 concurrent users.
Records graceful 429 / 503 response rates when servers degrade.
"""

import argparse
import datetime
import json
import platform
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Dict

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TEST_QUESTIONS = [
    ("chinook_1", "How many artists are in the database?"),
    ("chinook_1", "List the top 5 longest tracks."),
    ("chinook_1", "Find all albums by artist Iron Maiden."),
    ("chinook_1", "Count the number of customers from Brazil."),
    ("chinook_1", "What is the total invoice amount for customer 1?"),
]


def send_request(base_url: str, db_id: str, question: str, timeout: float = 10.0) -> Dict[str, Any]:
    url = f"{base_url}/v1/query"
    start = time.perf_counter()
    try:
        res = requests.post(
            url,
            json={"db_id": db_id, "question": question, "enable_consensus": False},
            headers={"X-API-Key": "demo-secret-key"},
            timeout=timeout,
        )
        status_code = res.status_code
        dur = time.perf_counter() - start
        return {"status_code": status_code, "latency_sec": dur, "error": None}
    except Exception as e:
        dur = time.perf_counter() - start
        return {"status_code": 500, "latency_sec": dur, "error": str(e)}


def run_concurrency_tier(
    base_url: str, concurrency: int, total_requests: int = 20
) -> Dict[str, Any]:
    print(f"Running load test tier: concurrency={concurrency}, requests={total_requests}...")
    tasks = []
    for i in range(total_requests):
        db_id, question = TEST_QUESTIONS[i % len(TEST_QUESTIONS)]
        tasks.append((db_id, question))

    start_total = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(send_request, base_url, db_id, q) for db_id, q in tasks]
        results = [f.result() for f in futures]
    wall_clock = time.perf_counter() - start_total

    latencies = sorted([r["latency_sec"] for r in results])
    status_counts = {}
    for r in results:
        code = r["status_code"]
        status_counts[code] = status_counts.get(code, 0) + 1

    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0.0
    p95 = latencies[min(int(len(latencies) * 0.95), len(latencies) - 1)] if latencies else 0.0
    p99 = latencies[min(int(len(latencies) * 0.99), len(latencies) - 1)] if latencies else 0.0
    throughput = len(results) / wall_clock if wall_clock > 0 else 0.0

    return {
        "concurrency": concurrency,
        "total_requests": total_requests,
        "wall_clock_sec": round(wall_clock, 3),
        "throughput_req_per_sec": round(throughput, 2),
        "p50_latency_sec": round(p50, 4),
        "p95_latency_sec": round(p95, 4),
        "p99_latency_sec": round(p99, 4),
        "status_distribution": status_counts,
        "error_5xx_rate": round(
            (status_counts.get(500, 0) + status_counts.get(503, 0) + status_counts.get(504, 0))
            / total_requests,
            4,
        ),
        "rate_limited_429_rate": round(status_counts.get(429, 0) / total_requests, 4),
    }


def main():
    parser = argparse.ArgumentParser(description="Text-to-SQL Load Test Runner")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument(
        "--backend",
        default="stub",
        choices=["stub", "real"],
        help="Serving backend (stub/mock or real GGUF)",
    )
    parser.add_argument(
        "--requests-per-tier", type=int, default=20, help="Number of requests per concurrency tier"
    )
    parser.add_argument("--output", default="results/loadtest_latest.json", help="Output file path")
    args = parser.parse_args()

    import psutil

    hw_info = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "total_ram_gb": round(psutil.virtual_memory().total / (1024**3), 2),
        "python_version": sys.version,
    }

    tier_results = {}
    for c in [1, 2, 4]:
        tier_results[f"concurrency_{c}"] = run_concurrency_tier(
            args.url, concurrency=c, total_requests=args.requests_per_tier
        )

    report = {
        "metadata": {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "target_url": args.url,
            "backend": f"{args.backend} ({'Qwen2.5-Coder-3B-Q4_K_M.gguf' if args.backend == 'real' else 'mock'})",
            "benchmark_scope": f"Load benchmark using {args.backend} backend",
            "hardware": hw_info,
            "note": "Measures concurrency semaphore, bounded queue depth, request latency, and 429/503/504 degradation.",
        },
        "tiers": tier_results,
    }

    out_file = PROJECT_ROOT / args.output
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(report, indent=2))
    print(f"[SUCCESS] Load test report saved to {out_file}")


if __name__ == "__main__":
    main()
