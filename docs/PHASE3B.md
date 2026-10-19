# Phase 3b Protocol: Fine-Tuned Model Self-Correction & Voting Evaluation Specification

**Document Version:** 1.0.0  
**Status:** SPECIFICATION ONLY (No active execution per instruction)  
**Goal:** Empirically evaluate Execution-Guided Self-Correction and Consensus Voting on the **fine-tuned merged model** (FP16/BF16) using current committed repository code, resolving the parity observed on the zero-shot base model.

---

## 1. Motivation & Context

In Phase 3, the initial ablation (`results/ablation_latest.json`) was executed exclusively on the **base model** (`Qwen/Qwen2.5-Coder-3B-Instruct`), yielding parity at $62.28\%$ EX across all configurations because the unadapted model suffered from systematic reasoning and schema errors.

In Phase 1, the fine-tuned merged model achieved **$71.57\%$ Execution Accuracy** with a significantly lower execution error rate ($6.87\%$ vs. $14.22\%$ for base). Because execution-guided self-correction specifically repairs syntax and schema execution errors, testing on the fine-tuned weights provides the true benchmark of whether runtime repair and voting elevate accuracy beyond greedy inference.

---

## 2. Experimental Protocol

### 2.1 Configurations
1. **FT+greedy**: Fine-tuned model, greedy decoding ($\tau = 0.0$), AST validator + read-only sandbox.
2. **FT+SC**: FT+greedy + Execution-Guided Self-Correction (max 2 repair retries on database errors; policy blocks not retried).
3. **FT+V**: Consensus Voting ($N=5$ candidates sampled at temperature $\tau = 0.7$, AST validated, executed in sandbox, grouped by result set, majority selected, tie-break by latency/length).
4. **FT+SC+V**: Both mechanisms enabled (self-correction active on candidate queries failing execution during voting).

### 2.2 Dataset Split & Stratification
- **Evaluation Set**: Exact 300-question difficulty-stratified subset of the Spider **dev** set ($n=300$).
- **Seed**: `--seed 42`.
- **Hardware Target**: Cloud GPU (e.g., Kaggle GPU T4 x2 or Colab A100/T4) with `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` and `torch.cuda.empty_cache()` between runs to prevent CUDA OOM.
- **Mandatory Diagnostic Invariant**: The run **must save per-question final SQL (`item_results`) for every configuration** and report the count of questions where the final scored SQL differs from greedy. For voting configs (+V, +SC+V), the number of questions where final SQL differs from greedy **must be > 0**; if 0, the run is considered invalid/suspect.

---

## 3. Mandatory Metadata & Provenance Schema

Any script running Phase 3b must record the following metadata fields directly in the output JSON (`results/ablation_phase3b_<timestamp>.json` and `results/ablation_phase3b_latest.json`):
```json
{
  "metadata": {
    "git_commit": "<sha>",
    "dirty_tree": "<true/false>",
    "policy_sha256": "<sha256 of config/security_policy.yaml + src/t2s/safety/*.py>",
    "python_version": "<sys.version>",
    "sqlite_version": "<sqlite3.sqlite_version>",
    "hardware": {
      "gpu_model": "<torch.cuda.get_device_name(0)>",
      "vram_gb": "<float>",
      "cpu_model": "<platform.processor()>",
      "host_os": "<platform.platform()>"
    },
    "hardening_active": {
      "ast_validator": true,
      "read_only_sandbox": true,
      "max_row_limit": 100,
      "authorizer_active": true
    },
    "sample_count": 300,
    "seed": 42
  }
}
```

---

## 4. Reusability Architecture

The Phase 3b runner does **not** reimplement model inference, self-correction, or voting logic. It directly imports:
- `from src.t2s.service.self_correct import SelfCorrectionRunner`
- `from src.t2s.service.voting import ConsensusVoter`
- `from src.t2s.eval.exec_eval import compare_query_results, execute_sql_query`
- `from src.t2s.safety.validator import SQLValidator`
- `from src.t2s.safety.executor import SafeSQLExecutor`

See [`scripts/make_eval_bundle.py`](file:///e:/7thsem%20learning/projects/finue%20tune/scripts/make_eval_bundle.py) and [`notebooks/run_phase3b_eval.ipynb`](file:///e:/7thsem%20learning/projects/finue%20tune/notebooks/run_phase3b_eval.ipynb).
