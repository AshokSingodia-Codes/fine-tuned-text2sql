# Model Artifacts & Binary Tracking Log

This document records the exact paths, file sizes, SHA256 checksums, and verification status for all model weights, fine-tuned adapters, and quantized GGUF artifacts.

---

## 1. Artifact Verification Registry

| Artifact Name | Path | Status | File Size | SHA256 Checksum | Notes |
|---|---|---|---|---|---|
| **QLoRA Adapter Config** | `models\qlora_adapter\adapter_config.json` | **FOUND** | 0.0 MB (1,186 B) | `9d18a9b221cbc1ace8b3045fa9cecdacc2220af5614d9d03455d5a876499356f` | Verified real model binary. |
| **QLoRA Adapter Weights** | `models\qlora_adapter\adapter_model.safetensors` | **FOUND** | 114.25 MB (119,801,528 B) | `69368aaf4e081864ab3aed01c44692b3a42673ee3c2e35f5650ddb065d85943b` | Verified real model binary. |
| **Merged FP16 Model Weights** | `models\merged_model\model.safetensors` | **MISSING** | 0 Bytes | `N/A` | File does not exist. |
| **Quantized GGUF Model Binary** | `models\Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf` | **FOUND** | 1840.5 MB (1,929,902,592 B) | `4b414bc4a95d4ef849ef7ec2cb9a2563948e6714a32d208931b06f543c40694c` | Verified real model binary. |

---

## 2. Status Summary

- **Verified Real Artifacts**: 3 / 4
- **Missing / Refused Artifacts**: 1 / 4
