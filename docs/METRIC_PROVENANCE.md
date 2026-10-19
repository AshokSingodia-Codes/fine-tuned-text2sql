# Metric Provenance & Verification Audit

This document provides a strict audit of all performance, latency, accuracy, model size, and security metrics currently present in repository reports, documentation, and metadata files.

---

## 1. Comprehensive Metric Provenance Matrix

| Metric Name | Claimed Value | Source File & JSON Key | Generating Script | Backend Used | Classification | Proof / Evidence |
|---|---|---|---|---|---|---|
| **System A Execution Accuracy** | 2.77% | `reports/metrics_baseline_A.json` $\rightarrow$ `internal_eval.exec_accuracy` | `scripts/run_baseline.py` | `mock` (`MockBackend`) | **MOCK** | `reports/predictions_A.jsonl` contains `"pred": "SELECT 1;"` for all items. |
| **System B Execution Accuracy** | 2.77% | `reports/metrics_baseline_B.json` $\rightarrow$ `internal_eval.exec_accuracy` | `scripts/run_baseline.py` | `mock` (`MockBackend`) | **MOCK** | `reports/predictions_B.jsonl` contains `"pred": "SELECT 1;"` for all items. |
| **System C Execution Accuracy** | 1.06% | `reports/metrics_finetuned_C.json` $\rightarrow$ `internal_eval.exec_accuracy` | `scripts/evaluate_finetuned.py` | `mock` (`MockBackend`) | **MOCK** | `reports/predictions_C.jsonl` contains `"pred": "SELECT 1;"` for all items. |
| **System D (Q4_K_M) Accuracy** | 1.03% | `reports/metrics_quantized.json` $\rightarrow$ `quantization_formats.Q4_K_M.exec_accuracy` | Hand-edited JSON | None | **UNVERIFIABLE** | Static estimation; no real GGUF model run occurred. |
| **Base Model Size** | 6.2 GB | `reports/metrics_quantized.json` | Hand-edited JSON | None | **UNVERIFIABLE** | Theoretical estimate for 3B parameter model in FP16 precision. |
| **GGUF Q4_K_M Size** | 1.9 GB | `reports/metrics_quantized.json` | Hand-edited JSON | None | **UNVERIFIABLE** | Theoretical estimate for 4-bit quantized GGUF file. |
| **Serving Latency (p50/p95/p99)** | 0.0s | `reports/benchmark.json` $\rightarrow$ `benchmark_summary` | `scripts/benchmark.py` | `mock` (`MockBackend`) | **MOCK** | `reports/benchmark.json` explicitly records `"backend": "mock"`. |
| **Red-Team Block Rate** | 100.0% (60/60) | `reports/metrics_safety.json` $\rightarrow$ `redteam_suite` | `scripts/run_redteam.py` | Unit AST Validator | **VERIFIED-REAL (AST Unit Only)** | Tested 60 adversarial SQL strings directly against `SQLValidator` code; no LLM model used. |
| **False-Block Rate on Gold SQL** | 0.58% (6/1034) | `reports/metrics_safety.json` $\rightarrow$ `false_block_check` | `scripts/run_redteam.py` | Unit AST Validator | **VERIFIED-REAL (AST Unit Only)** | Evaluated 1,034 Spider dev gold queries against `SQLValidator.validate()`. |

---

## 2. Findings & Mandatory Re-measurement Plan

- **Model Inference Metrics (EX Accuracy, Latency)**: **ALL** previous model predictions were generated via `MockBackend` returning dummy `"SELECT 1;"` strings. These historical baseline numbers are classified as **MOCK** or **UNVERIFIABLE**.
- **Phase 1 Ingestion Status**: Once Phase 1 execution results are generated on Google Colab GPU/GGUF server and ingested via `scripts/ingest_colab_results.py`, all old metrics in the table above are officially flagged as **superseded by Phase 1 real run** (`results/eval_spider_latest.json` and `results/latency_latest.json`).
- **AST Validator Security Metrics**: The 100% block rate on the 60 adversarial test cases and 0.58% false-block rate are **VERIFIED-REAL at the unit-validator level** (`sqlglot` AST parser). End-to-end LLM prompt injection security will be re-evaluated during Phase 2.

