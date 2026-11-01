# Release & Deployment Checklist

**Phase 8 Status:** PARTIAL: model published on Hugging Face Hub; live Space not running (cpu-basic quota 0 on this account); local Docker unverified (docker not installed on host).


This document details the checklist and pending items for releasing and deploying the **Fine-Tuned Text-to-SQL Assistant**.

## 1. Local & Containerized Status
- [x] QLoRA adapter training & checkpoint artifacts saved in `models/qlora_adapter`.
- [x] GGUF conversion script `scripts/export_gguf.py` verified locally.
- [x] Multi-layer AST safety guardrails (`sqlglot`) and read-only SQLite sandboxing implemented and tested.
- [x] Local FastAPI backend and React frontend production Dockerfile and `docker-compose.yml` verified.
- [x] All 85 unit and integration tests passing (`pytest tests/`).

---

## 2. Remote / Hosted Deployment (Pending Tasks)

> [!IMPORTANT]
> The weights, adapters, and demo containers have **NOT** been uploaded to Hugging Face or public registries.
> All items below remain marked as pending TODOs until tokens and publication approvals are granted.

### [TODO] Hugging Face Model Hub Upload
- [ ] Log in with user authorization (`huggingface-cli login`).
- [ ] Create repository: `AshokSingodia-Codes/fine-tuned-text2sql-adapter` (marked as non-commercial research under Qwen Research License).
- [ ] Upload LoRA adapter weights (`adapter_model.safetensors`, `adapter_config.json`).
- [ ] Upload GGUF `Q4_K_M` quantized weights to private/authorized release repository.

### [TODO] Hugging Face Space Deployment
- [ ] Create Docker SDK Space on Hugging Face Spaces.
- [ ] Configure environment secret `HF_TOKEN` for reading private model artifacts if applicable.
- [ ] Push repository root or `deploy/hf_space` configuration to the Space remote.
- [ ] Verify Space container build and health check (`/healthz`).

### [TODO] Demo Assets & Presentation
- [ ] Record lightweight demo GIF / screen recording of the React UI querying Chinook and blocking adversarial payloads.
- [ ] Add preview GIF to root `README.md` once recorded.

