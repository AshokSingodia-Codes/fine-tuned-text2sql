"""Execution Accuracy Evaluation Harness for Spider Dev Set.

Evaluates Spider dev set (1,034 questions) across 4 model configurations:
- Config A: Base zero-shot
- Config B: Base 3-shot
- Config C: Fine-tuned (merged FP16)
- Config D: Quantized GGUF Q4_K_M

Calculates Execution Accuracy (EX), valid SQL rate, execution error rate,
timeout rate, guardrail block rate, and difficulty breakdown.
Saves reproducible metrics to results/eval_spider_latest.json.
"""

import argparse
import datetime
import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.data.schema import get_sqlite_schema_ddl  # noqa: E402
from src.t2s.eval.exec_eval import compare_query_results, execute_sql_query  # noqa: E402
from src.t2s.gen.backends import (  # noqa: E402
    LlamaCppBackend,
    MockBackend,
    OpenAICompatBackend,
    TransformersBackend,
)
from src.t2s.prompts import build_prompt_messages  # noqa: E402
from src.t2s.safety.executor import SafeSQLExecutor  # noqa: E402
from src.t2s.safety.policy import SafetyPolicy  # noqa: E402
from src.t2s.safety.validator import SQLValidator  # noqa: E402
from src.t2s.service.self_correct import SelfCorrectionRunner  # noqa: E402
from src.t2s.service.voting import ConsensusVoter  # noqa: E402


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


FEW_SHOT_3_EXAMPLES = [
    {
        "schema_ddl": "CREATE TABLE department (\n  Department_ID INTEGER,\n  Name TEXT,\n  PRIMARY KEY (Department_ID)\n);",
        "question": "How many departments are there?",
        "query": "SELECT count(*) FROM department;",
    },
    {
        "schema_ddl": "CREATE TABLE head (\n  head_ID INTEGER,\n  name TEXT,\n  born_state TEXT,\n  PRIMARY KEY (head_ID)\n);",
        "question": "List the names of all heads born in California.",
        "query": "SELECT name FROM head WHERE born_state = 'California';",
    },
    {
        "schema_ddl": "CREATE TABLE instructor (\n  ID INTEGER,\n  name TEXT,\n  salary REAL,\n  PRIMARY KEY (ID)\n);",
        "question": "What is the average salary of instructors?",
        "query": "SELECT avg(salary) FROM instructor;",
    },
]


def load_spider_dev_data(
    dev_json_path: str = "data/raw/spider/dev.json",
    db_base_dir: str = "data/raw/spider/database",
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    path = Path(dev_json_path)
    if not path.exists():
        raise FileNotFoundError(f"Spider dev dataset not found at: {dev_json_path}")

    with open(path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    if limit and limit > 0:
        raw_data = raw_data[:limit]

    dev_items = []
    schema_cache: Dict[str, str] = {}

    for item in raw_data:
        db_id = item["db_id"]
        question = item["question"]
        gold_sql = item["query"]
        hardness = item.get("hardness", "medium")

        db_path = Path(db_base_dir) / db_id / f"{db_id}.sqlite"
        if not db_path.exists():
            db_path = Path(db_base_dir) / f"{db_id}.sqlite"

        if db_id not in schema_cache:
            if db_path.exists():
                schema_cache[db_id] = get_sqlite_schema_ddl(str(db_path))
            else:
                schema_cache[db_id] = f"CREATE TABLE {db_id} (id INTEGER);"

        dev_items.append(
            {
                "db_id": db_id,
                "question": question,
                "gold_sql": gold_sql,
                "hardness": hardness,
                "db_path": str(db_path),
                "schema_ddl": schema_cache[db_id],
            }
        )

    return dev_items


def compute_bootstrap_ci(
    matches: List[int], n_bootstraps: int = 1000, ci: float = 0.95, seed: int = 42
) -> List[float]:
    """Compute 95% bootstrap confidence interval for binary accuracy vector."""
    if not matches:
        return [0.0, 0.0]
    n = len(matches)
    rng = random.Random(seed)
    boot_means = []
    for _ in range(n_bootstraps):
        sample = [matches[rng.randint(0, n - 1)] for _ in range(n)]
        boot_means.append(sum(sample) / n)
    boot_means.sort()
    lower_idx = int((1.0 - ci) / 2.0 * n_bootstraps)
    upper_idx = int((1.0 + ci) / 2.0 * n_bootstraps) - 1
    return [round(boot_means[lower_idx], 4), round(boot_means[upper_idx], 4)]


def compute_mcnemar_test(matches_d: List[int], matches_other: List[int]) -> Dict[str, Any]:
    """Paired McNemar test comparing Config D with another config."""
    if len(matches_d) != len(matches_other) or not matches_d:
        return {"p_value": 1.0, "statistic": 0.0, "contingency": {}}

    b = 0  # D correct, other incorrect
    c = 0  # D incorrect, other correct
    a = 0  # both correct
    d = 0  # both incorrect

    for yd, yo in zip(matches_d, matches_other):
        if yd == 1 and yo == 0:
            b += 1
        elif yd == 0 and yo == 1:
            c += 1
        elif yd == 1 and yo == 1:
            a += 1
        else:
            d += 1

    # Exact binomial or continuity corrected chi-squared
    n_discordant = b + c
    if n_discordant == 0:
        return {
            "p_value": 1.0,
            "statistic": 0.0,
            "contingency": {"both_correct": a, "d_only": b, "other_only": c, "both_incorrect": d},
        }

    # Edwards continuity-corrected McNemar statistic
    stat = ((abs(b - c) - 1) ** 2) / n_discordant if abs(b - c) > 1 else 0.0
    # Two-sided p-value approximation via chi2(df=1)
    import math

    def chi2_sf(x: float) -> float:
        # Survival function of chi2 with 1 degree of freedom = 2 * (1 - norm_cdf(sqrt(x)))
        if x <= 0:
            return 1.0
        return math.erfc(math.sqrt(x / 2.0))

    p_val = round(chi2_sf(stat), 4)
    return {
        "statistic": round(stat, 4),
        "p_value": p_val,
        "contingency": {"both_correct": a, "d_only": b, "other_only": c, "both_incorrect": d},
    }


def evaluate_config(
    config_id: str,
    config_name: str,
    dev_items: List[Dict[str, Any]],
    backend_name: str = "mock",
    model_path: Optional[str] = None,
    timeout_seconds: float = 3.0,
    seed: int = 42,
    baseline_d_matches: Optional[List[int]] = None,
) -> Dict[str, Any]:
    print(f"\n--- Evaluating Config {config_id}: {config_name} (Backend: {backend_name}) ---")

    # Initialize safety & service components
    policy = SafetyPolicy.load()
    validator = SQLValidator(policy)
    executor = SafeSQLExecutor(
        timeout_seconds=policy.timeout_seconds,
        max_rows=policy.max_row_limit,
    )
    self_corrector = SelfCorrectionRunner(
        validator=validator,
        executor=executor,
        max_retries=2,
    )
    consensus_voter = ConsensusVoter(
        validator=validator,
        executor=executor,
        per_candidate_timeout_seconds=policy.timeout_seconds,
        total_budget_seconds=15.0,
        max_concurrent=4,
    )

    # Few shot handling
    use_few_shot = config_id == "B"
    few_shots = FEW_SHOT_3_EXAMPLES if use_few_shot else None

    # Construct prompts
    prompts_list = []
    for item in dev_items:
        msgs = build_prompt_messages(
            schema_ddl=item["schema_ddl"],
            question=item["question"],
            few_shot_examples=few_shots,
        )
        prompts_list.append(msgs)

    # Instantiate Backend
    if backend_name == "mock":
        backend = MockBackend()
    elif backend_name == "transformers":
        model_name = model_path or "Qwen/Qwen2.5-Coder-3B-Instruct"
        backend = TransformersBackend(model_name=model_name)
    elif backend_name == "llama_cpp" or (model_path and model_path.endswith(".gguf")):
        model_file = model_path or "models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf"
        backend = LlamaCppBackend(model_path=model_file)
    elif backend_name == "openai_compat":
        backend = OpenAICompatBackend(api_base=model_path or "http://localhost:8000/v1")
    else:
        backend = MockBackend()

    total = len(dev_items)
    correct_count = 0
    valid_sql_count = 0
    exec_error_count = 0
    timeout_count = 0
    guardrail_blocked_count = 0
    total_model_calls = 0
    latencies_sec = []
    binary_matches: List[int] = []

    difficulty_counts: Dict[str, Dict[str, int]] = {
        "easy": {"total": 0, "correct": 0},
        "medium": {"total": 0, "correct": 0},
        "hard": {"total": 0, "correct": 0},
        "extra": {"total": 0, "correct": 0},
    }

    item_results = []
    start_gen_time = time.perf_counter()

    for item, prompt_msgs in zip(dev_items, prompts_list):
        t_item0 = time.perf_counter()
        db_path = item["db_path"]
        gold_sql = item["gold_sql"]
        hardness = item["hardness"].lower()
        if hardness not in difficulty_counts:
            hardness = "medium"

        difficulty_counts[hardness]["total"] += 1

        # Configuration Dispatch
        if config_id in ["A", "B", "C", "D"]:
            # Standard single greedy pass
            total_model_calls += 1
            out = backend.generate([prompt_msgs])[0]
            raw_pred = out.get("text", "") if isinstance(out, dict) else str(out)
            pred_sql = raw_pred.strip()
            if ";" in pred_sql:
                pred_sql = pred_sql.split(";")[0] + ";"

            verdict = validator.validate(pred_sql)
            if not verdict.allowed:
                guardrail_blocked_count += 1
                p_ok, p_res, p_err = False, None, "Blocked by AST validator"
            else:
                p_ok, p_res, p_err = execute_sql_query(
                    db_path, verdict.rewritten_sql, timeout_seconds
                )

        elif config_id == "E":
            # Config E: Base + Self-Correction (max 2 retries on exec/syntax error)
            def repair_gen(msgs: List[Dict[str, str]]) -> str:
                nonlocal total_model_calls
                total_model_calls += 1
                r = backend.generate([msgs])[0]
                return r.get("text", "") if isinstance(r, dict) else str(r)

            total_model_calls += 1
            init_out = backend.generate([prompt_msgs])[0]
            init_sql = init_out.get("text", "") if isinstance(init_out, dict) else str(init_out)

            corr_res = self_corrector.run(
                db_path=db_path,
                initial_sql=init_sql,
                generate_fn=repair_gen,
                base_prompt_messages=prompt_msgs,
            )
            pred_sql = corr_res.final_sql
            verdict = corr_res.verdict
            if not corr_res.allowed:
                guardrail_blocked_count += 1
                p_ok, p_res, p_err = False, None, "Blocked by policy"
            else:
                exec_r = corr_res.exec_res
                p_ok = exec_r.success if exec_r else False
                p_res = exec_r.rows if exec_r else None
                p_err = exec_r.error if exec_r else None

        elif config_id == "F":
            # Config F: Voting (N=5 candidates, majority execution outcome)
            n_cands = 5
            total_model_calls += n_cands
            # Generate stochastic candidates using temperature 0.7
            if hasattr(backend, "generate"):
                try:
                    cands_out = backend.generate(
                        [prompt_msgs] * n_cands, do_sample=True, temperature=0.7
                    )
                except TypeError:
                    cands_out = backend.generate([prompt_msgs] * n_cands)
            else:
                cands_out = backend.generate([prompt_msgs] * n_cands)

            cands_sql = [
                (o.get("text", "") if isinstance(o, dict) else str(o)).strip() for o in cands_out
            ]

            vote_res = consensus_voter.select_best_candidate(
                db_path=db_path,
                candidate_sqls=cands_sql,
            )
            pred_sql = vote_res.winner_sql
            verdict = vote_res.winner_verdict

            if not verdict.allowed:
                guardrail_blocked_count += 1
                p_ok, p_res, p_err = False, None, "Blocked by policy"
            else:
                exec_r = vote_res.winner_exec_res
                p_ok = exec_r.success if exec_r else False
                p_res = exec_r.rows if exec_r else None
                p_err = exec_r.error if exec_r else None

        elif config_id == "G":
            # Config G: Voting (N=5) + Self-Correction on each failing candidate
            n_cands = 5
            cands_sql = []
            for _ in range(n_cands):

                def repair_gen_g(msgs: List[Dict[str, str]]) -> str:
                    nonlocal total_model_calls
                    total_model_calls += 1
                    r = backend.generate([msgs])[0]
                    return r.get("text", "") if isinstance(r, dict) else str(r)

                total_model_calls += 1
                init_out = backend.generate([prompt_msgs])[0]
                init_sql = init_out.get("text", "") if isinstance(init_out, dict) else str(init_out)
                c_res = self_corrector.run(
                    db_path=db_path,
                    initial_sql=init_sql,
                    generate_fn=repair_gen_g,
                    base_prompt_messages=prompt_msgs,
                )
                cands_sql.append(c_res.final_sql)

            vote_res = consensus_voter.select_best_candidate(
                db_path=db_path,
                candidate_sqls=cands_sql,
            )
            pred_sql = vote_res.winner_sql
            verdict = vote_res.winner_verdict
            if not verdict.allowed:
                guardrail_blocked_count += 1
                p_ok, p_res, p_err = False, None, "Blocked by policy"
            else:
                exec_r = vote_res.winner_exec_res
                p_ok = exec_r.success if exec_r else False
                p_res = exec_r.rows if exec_r else None
                p_err = exec_r.error if exec_r else None
        else:
            raise ValueError(f"Unknown config_id: {config_id}")

        item_lat = time.perf_counter() - t_item0
        latencies_sec.append(item_lat)

        # Execute Gold SQL
        g_ok, g_res, g_err = execute_sql_query(db_path, gold_sql, timeout_seconds)

        if p_ok:
            valid_sql_count += 1
        elif p_err and "timeout" in p_err.lower():
            timeout_count += 1
        else:
            exec_error_count += 1

        # Compare execution results
        is_correct = compare_query_results(
            g_res if g_ok else None, p_res if p_ok else None, gold_sql
        )
        match_int = 1 if is_correct else 0
        binary_matches.append(match_int)

        if is_correct:
            correct_count += 1
            difficulty_counts[hardness]["correct"] += 1

        item_results.append(
            {
                "question": item["question"],
                "db_id": item["db_id"],
                "gold": gold_sql,
                "pred": pred_sql,
                "verdict_allowed": verdict.allowed,
                "exec_match": is_correct,
                "gold_ok": g_ok,
                "pred_ok": p_ok,
                "pred_error": p_err,
                "latency_sec": round(item_lat, 3),
            }
        )

    gen_duration = time.perf_counter() - start_gen_time

    # Latency percentiles
    latencies_sec.sort()
    avg_latency = sum(latencies_sec) / total if total > 0 else 0.0
    p95_latency = latencies_sec[int(0.95 * total)] if total > 0 else 0.0

    exec_acc = round(correct_count / total, 4) if total > 0 else 0.0
    valid_rate = round(valid_sql_count / total, 4) if total > 0 else 0.0
    exec_err_rate = round(exec_error_count / total, 4) if total > 0 else 0.0
    timeout_rate = round(timeout_count / total, 4) if total > 0 else 0.0
    blocked_rate = round(guardrail_blocked_count / total, 4) if total > 0 else 0.0
    avg_model_calls = round(total_model_calls / total, 2) if total > 0 else 1.0

    bootstrap_ci = compute_bootstrap_ci(binary_matches, seed=seed)

    # McNemar vs D
    mcnemar_stat = None
    if baseline_d_matches is not None and len(baseline_d_matches) == total:
        mcnemar_stat = compute_mcnemar_test(baseline_d_matches, binary_matches)

    diff_breakdown = {}
    for d, counts in difficulty_counts.items():
        d_tot = counts["total"]
        d_corr = counts["correct"]
        diff_breakdown[d] = {
            "total": d_tot,
            "correct": d_corr,
            "accuracy": round(d_corr / d_tot, 4) if d_tot > 0 else 0.0,
        }

    print(
        f"Result for Config {config_id}: EX Acc = {exec_acc * 100:.2f}% [95% CI: {bootstrap_ci[0] * 100:.2f}% - {bootstrap_ci[1] * 100:.2f}%], "
        f"Avg Latency = {avg_latency:.2f}s, p95 = {p95_latency:.2f}s, Calls/Q = {avg_model_calls}"
    )

    return {
        "config_id": config_id,
        "config_name": config_name,
        "total_examples": total,
        "execution_accuracy": exec_acc,
        "bootstrap_ci_95": bootstrap_ci,
        "valid_sql_rate": valid_rate,
        "execution_error_rate": exec_err_rate,
        "timeout_rate": timeout_rate,
        "blocked_by_guardrail_rate": blocked_rate,
        "avg_model_calls_per_question": avg_model_calls,
        "avg_latency_sec": round(avg_latency, 3),
        "p95_latency_sec": round(p95_latency, 3),
        "mcnemar_vs_d": mcnemar_stat,
        "difficulty_breakdown": diff_breakdown,
        "generation_duration_sec": round(gen_duration, 2),
        "binary_matches": binary_matches,
        "item_results": item_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Spider dev Execution Accuracy across configs."
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Limit number of dev items (e.g. 20 for smoke test)"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument(
        "--config",
        type=str,
        default="all",
        choices=["all", "A", "B", "C", "D", "E", "F", "G", "phase3_ablation"],
    )
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

    dev_items = load_spider_dev_data(limit=args.limit)
    print(f"Loaded {len(dev_items)} Spider dev questions for evaluation.")

    configs_to_run = []
    if args.config == "all":
        configs_to_run = [
            ("A", "Base Zero-Shot"),
            ("B", "Base 3-Shot"),
            ("C", "Fine-Tuned FP16"),
            ("D", "Quantized GGUF Q4_K_M"),
            ("E", "Fine-Tuned + Self-Correction"),
            ("F", "Fine-Tuned + Consensus Voting (N=5)"),
            ("G", "Fine-Tuned + Both (Self-Correction + Voting)"),
        ]
    elif args.config == "phase3_ablation":
        configs_to_run = [
            ("D", "Baseline Guarded Greedy (D)"),
            ("E", "Self-Correction (E)"),
            ("F", "Consensus Voting N=5 (F)"),
            ("G", "Both Self-Correction + Voting (G)"),
        ]
    elif args.config == "A":
        configs_to_run = [("A", "Base Zero-Shot")]
    elif args.config == "B":
        configs_to_run = [("B", "Base 3-Shot")]
    elif args.config == "C":
        configs_to_run = [("C", "Fine-Tuned FP16")]
    elif args.config == "D":
        configs_to_run = [("D", "Quantized GGUF Q4_K_M")]
    elif args.config == "E":
        configs_to_run = [("E", "Fine-Tuned + Self-Correction")]
    elif args.config == "F":
        configs_to_run = [("F", "Fine-Tuned + Consensus Voting (N=5)")]
    elif args.config == "G":
        configs_to_run = [("G", "Fine-Tuned + Both (Self-Correction + Voting)")]

    eval_results = {}
    baseline_d_matches = None

    for c_id, c_name in configs_to_run:
        res = evaluate_config(
            config_id=c_id,
            config_name=c_name,
            dev_items=dev_items,
            backend_name=args.backend,
            model_path=args.model_path,
            seed=args.seed,
            baseline_d_matches=baseline_d_matches,
        )
        if c_id == "D":
            baseline_d_matches = res.get("binary_matches")
        eval_results[c_id] = res

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    git_hash = get_git_commit_hash()

    report_payload = {
        "metadata": {
            "date": datetime.datetime.now().isoformat(),
            "git_commit_hash": git_hash,
            "seed": args.seed,
            "dataset_split": "Spider dev",
            "eval_limit": args.limit,
            "backend_used": args.backend,
            "prompt_template": "System: 'You are a text-to-SQL assistant. Return only one SQLite SELECT query. No explanations.' | User: '### SQLite Schema:\\n{schema}\\n\\n### Question:\\n{question}'",
        },
        "configs": eval_results,
    }

    # Mock Backend Guard Checks (Task 2)
    if args.backend == "mock":
        if args.limit is None or args.limit > 20:
            print(
                "ERROR: Full evaluation runs (no --limit or --limit > 20) with mock backend are strictly prohibited.",
                file=sys.stderr,
            )
            sys.exit(1)
        print("\nMOCK RUN: NOT A REAL RESULT")
        out_dir = Path("results/smoke")
    else:
        out_dir = Path(args.output_dir)

    out_dir.mkdir(parents=True, exist_ok=True)

    timestamped_file = out_dir / f"eval_spider_{timestamp}.json"

    with open(timestamped_file, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    if args.backend != "mock":
        latest_file = out_dir / "eval_spider_latest.json"
        with open(latest_file, "w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2)

        # Also write per-config file if single config evaluated (for merge_eval_results.py)
        if len(configs_to_run) == 1:
            single_cfg_id = configs_to_run[0][0]
            cfg_file = out_dir / f"eval_spider_{single_cfg_id}.json"
            with open(cfg_file, "w", encoding="utf-8") as f:
                json.dump(report_payload, f, indent=2)
            print(f"Saved config {single_cfg_id} evaluation metrics to: {cfg_file}")

        print(f"\nSaved real evaluation metrics to:\n  - {timestamped_file}\n  - {latest_file}")
    else:
        print(f"\nSaved smoke test metrics to:\n  - {timestamped_file}")


if __name__ == "__main__":
    main()
