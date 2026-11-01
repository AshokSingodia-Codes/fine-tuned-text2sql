# Evaluation & Benchmark Reproduction Guide

This guide details how to reproduce all benchmark numbers reported in `docs/RESUME_NUMBERS.md` and `results/`.

---

## 1. Prerequisites & Raw Data Setup

The repository ships clean without the raw Spider benchmark dataset to keep the repository size lightweight. To reproduce evaluations on Spider dev ($n=1,034$):

### Step 1: Download Spider Dataset
```bash
# Create data directories
mkdir -p data/raw/spider
cd data/raw/spider

# Download Spider dataset zip (CC BY-SA 4.0)
curl -L -o spider.zip https://yale-lily.github.io/spider

# Unpack dataset
unzip spider.zip
```
Ensure `data/raw/spider/dev.json` and `data/raw/spider/database/` are populated.

---

## 2. Leakage Verification (Rule R3)
Run the automated check ensuring zero train-to-dev data leakage:
```bash
python scripts/check_leakage.py
```
Expected output:
```text
Zero overlap of (question, db_id) pairs between train and dev sets.
PASS: Leakage check clean.
```

---

## 3. Running Model Evaluations

All evaluation scripts accept `--seed 42` (default) and output timestamped and `_latest.json` copies to `results/`.

### Config D: Quantized GGUF Q4_K_M on CPU (Spider Dev)
```bash
python scripts/eval_spider.py --config D --backend llama_cpp --model-path models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf --seed 42
```
Expected output:
- **Execution Accuracy (EX)**: `70.70% (731 / 1,034)`
- Evidence: `results/eval_spider_latest.json`

### Production Guarded Pipeline (Config D + AST Safety Guardrail)
```bash
python scripts/eval_spider.py --config D --guarded --backend llama_cpp --model-path models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf --seed 42
```
Expected output:
- **Guarded EX Accuracy**: `70.50% (729 / 1,034)`

---

## 4. Running Security & Safety Red-Teaming
```bash
python scripts/eval_redteam.py
```
Expected output:
- **Path A Raw Block Rate**: `87.50% (105 / 120)`
- **Path C Sandbox Defense Rate**: `100.00% (120 / 120)`
- **Path D Full Pipeline Attack Success Rate**: `0.00% (0 / 120)`

### Full Phase 2 Regression Gate Verification
```bash
python scripts/check_phase2.py
```
Checks dataset counts, Wilson 95% confidence intervals, and frozen policy SHA-256 hash (`682e3439354213f37b7645592a57b439a94f3d5073794fa86a349ca5761a8daa`).
