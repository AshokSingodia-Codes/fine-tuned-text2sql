# GGUF Quantization & Model Export Guide

This document provides exact step-by-step commands to convert HuggingFace fine-tuned merged weights into quantized GGUF format (`Q4_K_M`) using `llama.cpp`.

---

## 1. Prerequisites

- Built `llama.cpp` binaries (`convert_hf_to_gguf.py` and `llama-quantize`).
- Merged FP16 model directory (`models/merged_model/`).

---

## 2. Step-by-Step Conversion & Quantization Commands

### Step 1: Clone and Build `llama.cpp` (if not already built)
```bash
git clone https://github.com/ggerganov/llama.cpp third_party/llama.cpp
cd third_party/llama.cpp
make -j
cd ../..
```

### Step 2: Convert HuggingFace Merged Model to FP16 GGUF
```bash
python third_party/llama.cpp/convert_hf_to_gguf.py models/merged_model \
    --outfile models/merged_fp16.gguf
```

### Step 3: Quantize FP16 GGUF to `Q4_K_M`
```bash
./third_party/llama.cpp/llama-quantize \
    models/merged_fp16.gguf \
    models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf \
    Q4_K_M
```

---

## 3. Registering the Quantized Artifact

After generating `Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf`, register the artifact details into `docs/ARTIFACTS.md`:

```bash
python scripts/register_artifacts.py
```
