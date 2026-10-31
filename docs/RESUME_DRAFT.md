# Production-Hardened Text-to-SQL Assistant: Resume Bullets

### Core Resume Entry (Target: AI Engineer / LLM Systems)

**Fine-Tuned Text-to-SQL Assistant: QLoRA + Guarded Local LLM Serving** (FastAPI, React, SQLite, llama.cpp, sqlglot)
- **Fine-Tuning & Quantization**: Fine-tuned `Qwen2.5-Coder-3B` using QLoRA ($r=16$) across 7,784 Spider pairs; 4-bit quantized (GGUF Q4_K_M) to cut memory by 69.4% (6.2 GB $\rightarrow$ 1.9 GB), achieving **70.70% Execution Accuracy** on Spider dev ($n=1,034$, 98.8% accuracy retention vs FP16) with 4.68s p50 CPU latency *(Caveat: Base 62.28% evaluated on cloud GPU; hardware not identical)*.
- **AST Guardrails & Sandboxing**: Implemented dual-layer defensive runtime using `sqlglot` AST parsing and a read-only SQLite sandbox; blocked **96.3%** (105/109) of adversarial SQL injections *(on custom red-team suite)* and **0/48 harm** on frozen held-out attacks, maintaining a 0.19% false-positive rate on Spider gold queries.
- **Serving Architecture & Resiliency**: Architected production serving stack on FastAPI with token-bucket rate limiting, concurrency semaphore, bounded queue backlog, payload clamping (64 KB), and security headers; verified 503 graceful rejection under overload, path traversal blocking on `db_id`, and PII query redaction in SQLite audit logs.
- **Production Packaging & Evaluation**: [PENDING: Live Space Deployment] Built single-container Docker packaging serving FastAPI and compiled React + Vite frontend; verified zero data leakage between train/dev splits via automated CI suites maintaining 88% overall test coverage (94% on AST validator).
