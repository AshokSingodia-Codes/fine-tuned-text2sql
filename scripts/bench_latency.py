"""Latency and Hardware Benchmark Script for Serving Path (Config D).

Measures end-to-end query latency (p50, p95, p99), generation throughput (tokens/sec),
peak RSS memory usage (MB), and hardware details on the local serving path.
Outputs results to results/latency_latest.json.
"""

import argparse
import datetime
import json
import os
import platform
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import psutil

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.data.prompts import build_prompt_messages  # noqa: E402
from src.t2s.data.schema import get_sqlite_schema_ddl  # noqa: E402
from src.t2s.gen.backends import (  # noqa: E402
    LlamaCppBackend,
    MockBackend,
    OpenAICompatBackend,
    TransformersBackend,
)


def get_git_commit_hash() -> str:
    env_sha = os.environ.get("COMMIT_SHA")
    if env_sha:
        return env_sha.strip()
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return res.stdout.strip()
    except Exception:
        return "unknown_commit"


def get_hardware_description() -> Dict[str, Any]:
    cpu_name = platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "x86_64")
    cpu_cores_physical = psutil.cpu_count(logical=False) or 4
    cpu_cores_logical = psutil.cpu_count(logical=True) or 8
    ram_gb = round(psutil.virtual_memory().total / (1024**3), 2)

    cuda_available = False
    try:
        import torch

        cuda_available = torch.cuda.is_available()
    except Exception:
        pass

    desc = f"{platform.system()} ({cpu_name}, {cpu_cores_physical} cores, {ram_gb} GB RAM)"
    return {
        "description": desc,
        "os": platform.system(),
        "cpu_name": cpu_name,
        "cpu_physical_cores": cpu_cores_physical,
        "cpu_logical_cores": cpu_cores_logical,
        "total_ram_gb": ram_gb,
        "cuda_available": cuda_available,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark serving path latency and RSS memory.")
    parser.add_argument(
        "--limit", type=int, default=200, help="Number of questions to evaluate (default: 200)"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument(
        "--backend",
        type=str,
        default="mock",
        choices=["mock", "transformers", "openai_compat", "llama_cpp"],
    )
    parser.add_argument(
        "--model-path", type=str, default=None, help="Model name, path, or API base URL"
    )
    parser.add_argument("--output-dir", type=str, default="results", help="Output directory")

    args = parser.parse_args()
    random.seed(args.seed)

    dev_json_path = Path("data/raw/spider/dev.json")
    db_base_dir = Path("data/raw/spider/database")

    if not dev_json_path.exists():
        raise FileNotFoundError(f"Spider dev dataset not found at: {dev_json_path}")

    with open(dev_json_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    if args.limit and args.limit > 0:
        raw_data = raw_data[: args.limit]

    prompts_list = []
    schema_cache: Dict[str, str] = {}

    for item in raw_data:
        db_id = item["db_id"]
        question = item["question"]
        db_path = db_base_dir / db_id / f"{db_id}.sqlite"
        if not db_path.exists():
            db_path = db_base_dir / f"{db_id}.sqlite"

        if db_id not in schema_cache:
            if db_path.exists():
                schema_cache[db_id] = get_sqlite_schema_ddl(str(db_path))
            else:
                schema_cache[db_id] = f"CREATE TABLE {db_id} (id INTEGER);"

        msgs = build_prompt_messages(schema_ddl=schema_cache[db_id], question=question)
        prompts_list.append(msgs)

    # Initialize Backend
    if args.backend == "mock":
        backend = MockBackend()
    elif args.backend == "transformers":
        model_name = args.model_path or "Qwen/Qwen2.5-Coder-3B-Instruct"
        backend = TransformersBackend(model_name=model_name)
    elif args.backend == "llama_cpp" or (args.model_path and args.model_path.endswith(".gguf")):
        model_file = args.model_path or "models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf"
        backend = LlamaCppBackend(model_path=model_file)
    elif args.backend == "openai_compat":
        backend = OpenAICompatBackend(api_base=args.model_path or "http://localhost:8000/v1")
    else:
        backend = MockBackend()

    process = psutil.Process(os.getpid())

    print(f"Running latency benchmark on {len(prompts_list)} questions...")
    latencies_sec: List[float] = []
    total_tokens = 0
    start_bench_time = time.perf_counter()

    for msgs in prompts_list:
        t0 = time.perf_counter()
        out = backend.generate([msgs])[0]
        t1 = time.perf_counter()
        lat_sec = t1 - t0
        latencies_sec.append(lat_sec)

        tokens = (
            out.get("tokens", len(out.get("text", "").split())) if isinstance(out, dict) else 10
        )
        total_tokens += tokens

    total_bench_time = time.perf_counter() - start_bench_time
    peak_rss_mb = round(process.memory_info().rss / (1024 * 1024), 2)

    latencies_sec.sort()
    n = len(latencies_sec)

    p50_sec = round(latencies_sec[int(0.50 * n)], 4) if n > 0 else 0.0
    p95_sec = round(latencies_sec[int(0.95 * n)], 4) if n > 0 else 0.0
    p99_sec = round(latencies_sec[min(int(0.99 * n), n - 1)], 4) if n > 0 else 0.0
    tokens_per_sec = round(total_tokens / total_bench_time, 2) if total_bench_time > 0 else 0.0

    hardware_info = get_hardware_description()

    report_data = {
        "num_questions": n,
        "metadata": {
            "date": datetime.datetime.now().isoformat(),
            "git_commit_hash": get_git_commit_hash(),
            "seed": args.seed,
            "sample_count": n,
            "num_questions": n,
            "backend_used": args.backend,
        },
        "hardware": hardware_info,
        "metrics": {
            "p50_latency_sec": p50_sec,
            "p95_latency_sec": p95_sec,
            "p99_latency_sec": p99_sec,
            "tokens_per_second": tokens_per_sec,
            "tokens_per_sec": tokens_per_sec,
            "peak_rss_mb": peak_rss_mb,
            "total_benchmark_sec": round(total_bench_time, 2),
        },
    }

    # Mock Backend Guard Checks (Task 2)
    if args.backend == "mock":
        if args.limit is None or args.limit > 20:
            print(
                "ERROR: Full latency benchmark runs (no --limit or --limit > 20) with mock backend are strictly prohibited.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("\nMOCK RUN: NOT A REAL RESULT")
        out_dir = Path("results/smoke")
    else:
        out_dir = Path(args.output_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_file = out_dir / f"latency_{timestamp}.json"

    with open(timestamped_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    if args.backend != "mock":
        latest_file = out_dir / "latency_latest.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"\nSaved real latency results to:\n  - {timestamped_file}\n  - {latest_file}")
    else:
        print(f"\nSaved smoke latency results to:\n  - {timestamped_file}")

    print(f"\nLatency Benchmark Results ({n} queries):")
    print(f"  - p50 Latency: {p50_sec} s")
    print(f"  - p95 Latency: {p95_sec} s")
    print(f"  - p99 Latency: {p99_sec} s")
    print(f"  - Throughput: {tokens_per_sec} tokens/sec")
    print(f"  - Peak RSS Memory: {peak_rss_mb} MB")


if __name__ == "__main__":
    main()
