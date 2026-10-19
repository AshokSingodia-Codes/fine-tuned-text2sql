---
language:
- en
license: other
license_name: qwen-research
license_link: https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct/raw/main/LICENSE
base_model: Qwen/Qwen2.5-Coder-3B-Instruct
tags:
- text-to-sql
- qlora
- sqlglot
- safe-serving
- sqlite
---

# Model Card: Fine-Tuned Text-to-SQL Assistant (QLoRA)

This repository contains the fine-tuned LoRA adapter and serving configuration for **Text-to-SQL Assistant**, adapted from `Qwen/Qwen2.5-Coder-3B-Instruct` on Spider benchmark training pairs and guarded with AST SQL safety guardrails and a read-only SQLite execution sandbox.

---

## 1. Model Details

- **Base Model:** `Qwen/Qwen2.5-Coder-3B-Instruct` (Hangzhou Tongyi Laboratory Technology Co., Ltd. / Alibaba Cloud)
- **Adapter Architecture:** QLoRA ($r=16$, $\alpha=32$, target modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`)
- **Serving Quantization:** GGUF Q4_K_M (1.9 GB footprint, cut from 6.2 GB FP16)
- **Serving Path:** Safe SQLite execution sandbox with sqlglot AST validation

---

## 2. Licensing, Attribution & Usage Terms (CRITICAL)

### Base Model License: Qwen Research License Agreement
The base model `Qwen/Qwen2.5-Coder-3B-Instruct` is governed by the **Qwen Research License Agreement** (Release Date: September 19, 2024), **NOT** Apache-2.0.
- **Permitted Purpose:** Non-commercial research and evaluation purposes only.
- **Commercial Use:** Strict prohibition on commercial use without obtaining a separate commercial license from Alibaba Cloud (`model-business@notice.qwencloud.com`).
- **Derivative Distribution:** Any redistribution of fine-tuned adapters, merged checkpoints, or quantized weights must retain the Qwen Research License copy, include prominent modification notices, and provide the attribution:
  > *"Qwen is licensed under the Qwen RESEARCH LICENSE AGREEMENT, Copyright (c) Alibaba Cloud. All Rights Reserved."*
  > *"Built with Qwen"*
- **Notice on Commercial Alternatives:** For unrestricted commercial applications, users should retrain or serve an Apache-2.0 licensed model from the Qwen2.5-Coder family (e.g. 1.5B, 7B, 14B, or 32B).

### Other Third-Party Licenses
- **Training Dataset (Spider):** Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0).
- **Demo Database (Chinook):** MIT License (Copyright (c) 2008-2024 Luis Rocha).
- **SQL Parser (sqlglot):** MIT License (Copyright (c) Toby Mao).

---

## 3. Empirical Accuracy & Latency Benchmarks

All metrics below are derived directly from reproducible runs recorded in `results/eval_spider_latest.json` and `results/latency_latest.json` (Rule R1):

| Model Configuration | Format / Size | Execution Accuracy (Spider Dev, n=1,034) | 95% Wilson / Bootstrap CI | Latency p50 | Latency p95 | Serving Hardware |
|---|---|---|---|---|---|---|
| **Base Zero-Shot** | FP16 (6.2 GB) | **62.28%** (644 / 1,034) | [59.38%, 65.18%] | 2.16 s | 5.82 s | Linux GPU (Cloud) |
| **Base 3-Shot** | FP16 (6.2 GB) | **66.15%** (684 / 1,034) | [63.25%, 68.96%] | 2.23 s | 6.01 s | Linux GPU (Cloud) |
| **Fine-Tuned Merged** | FP16 (6.2 GB) | **71.57%** (740 / 1,034) | [68.86%, 74.27%] | 2.19 s | 5.91 s | Linux GPU (Cloud) |
| **Fine-Tuned Quantized** | GGUF Q4_K_M (1.9 GB) | **70.70%** (731 / 1,034) | [67.89%, 73.40%] | 4.68 s | 11.23 s | Local CPU (4 cores, 31.4 GB RAM) |
| **Fine-Tuned + Guardrail** | GGUF Q4_K_M (1.9 GB) | **70.50%** (729 / 1,034) | [67.69%, 73.21%] | 4.71 s | 11.31 s | Local CPU (4 cores, 31.4 GB RAM) |

---

## 4. Security & Safety Evaluation

Evaluated against multi-path adversarial red-team suites (`results/redteam_latest.json`, `results/METRICS.md`):

- **Path A Static AST Attack Block Rate:** **87.50% (105 / 120)** raw attacks blocked statically; **96.33% (105 / 109)** adjusted for audited harmless queries.
- **Path C Read-Only Sandbox Defense Rate:** **100.00% (120 / 120)** of attack payloads intercepted or neutralized at database layer.
- **Path D Full Pipeline Attack Success Rate:** **0.00% (0 / 120)** across all 120 direct adversarial SQL attacks.
- **Path B End-to-End Prompt Injection Success:** **0.00% (0 / 60)** on natural language instruction override attacks.
- **Spider Dev Legitimate Query False-Positive Rate:** **0.19% (2 / 1,034)** false blocks on Spider dev; **99.37% (1,103 / 1,110)** legitimate query pass rate on combined benchmark.
- **Policy Escape vs Harm Split (Held-Out V2):** Pre-fix policy escape rate was **8.33% (4 / 48)**, but **Harm Rate was 0.00% (0 / 48)** because the read-only sandbox authorizer neutralized every escaped payload.
- **Held-Out Evaluation Caveat:** An independent `heldout_v3` test suite has not yet been evaluated under the active safety policy freeze.

---

## 5. Deployment Instructions

### Adapter Loading (PyTorch / Transformers)
```python
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base_model_name = "Qwen/Qwen2.5-Coder-3B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(base_model_name)
base_model = AutoModelForCausalLM.from_pretrained(base_model_name, device_map="auto")
model = PeftModel.from_pretrained(base_model, "AshokSingodia-Codes/fine-tuned-text2sql-adapter")
```

### Private GGUF Serving
To comply with the Qwen Research License, pre-quantized merged GGUF files should be maintained in a private Hugging Face repository and downloaded at container runtime via a scoped Space secret `HF_TOKEN`.
