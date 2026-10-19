"""Self-contained runner script for Phase 3 on Kaggle GPU.

Can be run directly in Kaggle terminal or notebook:
  python scripts/run_phase3_kaggle.py --backend transformers --model-path Qwen/Qwen2.5-Coder-3B-Instruct

Workflow:
1. Runs full Spider dev (1,034 queries) on configs D, E, F, G under the same hardware and prompt.
2. Runs 3 random seeds (42, 101, 2024) on a 300-question stratified subset for sampling configs (F, G)
   to report the empirical score spread.
3. Computes bootstrap 95% CIs, McNemar paired tests vs D, latency percentiles, and model call averages.
4. Generates results/ablation_latest.json and bundles everything into /kaggle/working/phase3_results.zip.

Note: Use --skip-seeds to skip the multi-seed 300-subset run if CUDA OOM occurs during seed sweep.
The main D/E/F/G full-dev run loads the model once per config; the seed sweep reloads it, which
can cause CUDA OOM on 14.56 GiB T4 GPUs. Add PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
to your environment or use --skip-seeds to avoid the crash.
"""

import argparse
import datetime
import gc
import json
import random
import sys
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.eval_spider import evaluate_config, load_spider_dev_data  # noqa: E402


def build_stratified_subset(
    dev_items: List[Dict[str, Any]], target_size: int = 300, seed: int = 42
) -> List[Dict[str, Any]]:
    """Sample an exact stratified subset matching difficulty breakdown."""
    if len(dev_items) <= target_size:
        return list(dev_items)
    rng = random.Random(seed)
    by_diff = defaultdict(list)
    for it in dev_items:
        by_diff[it.get("hardness", "medium").lower()].append(it)

    total_orig = len(dev_items)
    selected = []
    for diff, items in by_diff.items():
        count = int(round(len(items) / total_orig * target_size))
        sampled = rng.sample(items, min(count, len(items)))
        selected.extend(sampled)

    # Adjust rounding if off by 1-2 items
    if len(selected) < target_size:
        remaining = [it for it in dev_items if it not in selected]
        selected.extend(rng.sample(remaining, target_size - len(selected)))
    elif len(selected) > target_size:
        selected = selected[:target_size]

    return selected


def main():
    parser = argparse.ArgumentParser(description="Phase 3 Evaluation on Kaggle GPU")
    parser.add_argument(
        "--backend",
        type=str,
        default="transformers",
        choices=["transformers", "llama_cpp", "openai_compat", "mock"],
    )
    parser.add_argument("--model-path", type=str, default="Qwen/Qwen2.5-Coder-3B-Instruct")
    parser.add_argument("--output-dir", type=str, default="results")
    parser.add_argument(
        "--skip-seeds", action="store_true", help="Skip 3-seed 300-question subset run"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of dev questions (for test)"
    )
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("==================================================================")
    print("           PHASE 3 BENCHMARK: FULL SPIDER DEV EVALUATION           ")
    print("==================================================================")
    print(f"Backend:          {args.backend}")
    print(f"Model:            {args.model_path}")
    print(f"Time (UTC):       {datetime.datetime.now(datetime.timezone.utc).isoformat()}")

    # 1. Load full Spider dev items (1,034)
    dev_items = load_spider_dev_data(limit=args.limit)
    print(f"Loaded {len(dev_items)} Spider dev questions.")

    # 2. Evaluate full run on Configs D, E, F, G (Seed 42)
    configs_to_run = [
        ("D", "Guarded Greedy Baseline (D)"),
        ("E", "Self-Correction (E)"),
        ("F", "Consensus Voting N=5 (F)"),
        ("G", "Both Self-Correction + Voting (G)"),
    ]

    full_results = {}
    baseline_d_matches = None

    for cid, cname in configs_to_run:
        print(f"\n>>> Running Config {cid}: {cname} (Seed 42, N={len(dev_items)})...")
        res = evaluate_config(
            config_id=cid,
            config_name=cname,
            dev_items=dev_items,
            backend_name=args.backend,
            model_path=args.model_path,
            seed=42,
            baseline_d_matches=baseline_d_matches,
        )
        if cid == "D":
            baseline_d_matches = res.get("binary_matches")
        full_results[cid] = res

    # 3. Multi-seed stability evaluation on 300-question stratified subset for sampling configs (F, G)
    seeds = [42, 101, 2024]
    subset_300 = build_stratified_subset(dev_items, target_size=300, seed=42)
    print("\n==================================================================")
    print(f"  MULTI-SEED EVALUATION ON 300-QUESTION STRATIFIED SUBSET ({seeds})")
    print("==================================================================")

    seed_results = {}
    if not args.skip_seeds:
        for cid, cname in [
            ("D", "Baseline Greedy (D)"),
            ("F", "Consensus Voting (F)"),
            ("G", "Both (G)"),
        ]:
            seed_results[cid] = {}
            for s in seeds:
                print(f"Evaluating Config {cid} with seed {s} on 300 subset...")
                # Flush GPU memory before each model reload to avoid CUDA OOM
                # (T4 14.56 GiB fills up after 3+ consecutive model loads)
                gc.collect()
                try:
                    import torch

                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                        free_gb = torch.cuda.mem_get_info()[0] / 1e9
                        print(f"  GPU free memory before {cid} seed {s}: {free_gb:.2f} GB")
                except Exception:
                    pass
                try:
                    sub_res = evaluate_config(
                        config_id=cid,
                        config_name=cname,
                        dev_items=subset_300,
                        backend_name=args.backend,
                        model_path=args.model_path,
                        seed=s,
                    )
                    seed_results[cid][str(s)] = {
                        "accuracy": sub_res["execution_accuracy"],
                        "calls_per_q": sub_res["avg_model_calls_per_question"],
                        "avg_lat": sub_res["avg_latency_sec"],
                    }
                except torch.cuda.OutOfMemoryError as oom:
                    print(f"  CUDA OOM for Config {cid} seed {s}: {oom}")
                    print("  Skipping remaining seed sweep. Use --skip-seeds to avoid this.")
                    seed_results[cid][str(s)] = {"error": "CUDA_OOM", "accuracy": None}
                    break

    # 4. Generate ablation summary
    ablation_payload = {
        "metadata": {
            "date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "backend": args.backend,
            "model": args.model_path,
            "total_questions": len(dev_items),
            "seed": 42,
        },
        "full_dev_results": full_results,
        "seed_spread_300_subset": seed_results,
    }

    # Save to results/ablation_latest.json
    ablation_file = out_dir / "ablation_latest.json"
    with open(ablation_file, "w", encoding="utf-8") as f:
        json.dump(ablation_payload, f, indent=2)

    # Save timestamped copy
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_file = out_dir / f"eval_spider_phase3_{ts}.json"
    with open(ts_file, "w", encoding="utf-8") as f:
        json.dump(ablation_payload, f, indent=2)

    # Also update eval_spider_latest.json with configs
    latest_spider = out_dir / "eval_spider_latest.json"
    if latest_spider.exists():
        with open(latest_spider, "r", encoding="utf-8") as f:
            spider_data = json.load(f)
    else:
        spider_data = {"metadata": {}, "configs": {}}
    spider_data["configs"].update(full_results)
    with open(latest_spider, "w", encoding="utf-8") as f:
        json.dump(spider_data, f, indent=2)

    print("\n==================================================================")
    print("                  PHASE 3 ABLATION SUMMARY TABLE                  ")
    print("==================================================================")
    print(
        f"{'Config':<8} | {'EX Accuracy':<18} | {'Bootstrap 95% CI':<18} | {'Calls/Q':<8} | {'Avg Lat':<8} | {'p95 Lat':<8} | {'McNemar p-val':<12}"
    )
    print("-" * 88)
    for cid, res in full_results.items():
        acc = f"{res['execution_accuracy'] * 100:.2f}%"
        ci = f"[{res['bootstrap_ci_95'][0] * 100:.1f}%, {res['bootstrap_ci_95'][1] * 100:.1f}%]"
        calls = f"{res['avg_model_calls_per_question']:.2f}"
        lat = f"{res['avg_latency_sec']:.2f}s"
        p95 = f"{res['p95_latency_sec']:.2f}s"
        mcnemar = (
            "baseline" if cid == "D" else str(res.get("mcnemar_vs_d", {}).get("p_value", "N/A"))
        )
        print(f"{cid:<8} | {acc:<18} | {ci:<18} | {calls:<8} | {lat:<8} | {p95:<8} | {mcnemar:<12}")
    print("==================================================================")

    # 5. Bundle for download into /kaggle/working/phase3_results.zip
    working_zip = Path("/kaggle/working/phase3_results.zip")
    if not working_zip.parent.exists():
        working_zip = PROJECT_ROOT / "phase3_results.zip"

    with zipfile.ZipFile(working_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in Path("results").glob("*.json"):
            zf.write(p, arcname=p.as_posix())
        print(f"\nCreated bundle at: {working_zip}")


if __name__ == "__main__":
    main()
