# Portfolio & Resume Presentation Kit

This kit contains ATS-friendly resume bullet points, walkthrough pitch scripts, and portfolio summary profiles grounded directly in [`docs/RESUME_NUMBERS.md`](RESUME_NUMBERS.md) and [`results/`](../results/).

---

## 1. Resume Entry (ATS-Safe, 4 Core Bullets)

```text
Fine-Tuned Text-to-SQL Assistant: QLoRA + Guarded Local LLM Serving
Technologies: Python, PyTorch, Hugging Face (PEFT/TRL), GGUF (llama.cpp), sqlglot, SQLite, FastAPI, React, Docker

• Fine-Tuning & Quantization: Adapted Qwen2.5-Coder-3B via QLoRA (r=16, alpha=32) over 8,634 Spider pairs with zero train/dev data leakage; compressed 6.2 GB weights to 1.9 GB GGUF Q4_K_M, achieving 70.70% Execution Accuracy on 1,034 Spider dev queries (+8.42 pp over zero-shot base) with 4.68s median CPU latency.
• Multi-Layered Security Sandbox: Architected deterministic defense-in-depth via sqlglot AST validator (2.44ms p50) and read-only SQLite authorizer callbacks; blocked 87.50% of attacks statically (105/120) and achieved 0.00% attack success across 120 direct red-team exploits and 60 prompt injection attacks with 0.19% false-positive rate on Spider dev.
• Reliability & Consensus Voting: Built execution-guided self-correction (max-2 retry feedback loop) and 5-way plurality voting service normalizing and hashing result multisets; engineered end-to-end regression test harnesses to verify scored candidates against execution feedback.
• Production Serving & Packaging: Developed asynchronous FastAPI serving layer with bounded concurrency semaphore (1 active generation, queue depth 10) rejecting overload at 503; integrated static React + Vite web UI into single-container Docker image with Prometheus metrics and automated GitHub Actions CI (80 tests passing).
```

---

## 2. Walkthrough Pitch Scripts

### 90-Second Elevator Pitch
> *"Most text-to-SQL demonstrations either rely on expensive proprietary LLM APIs or blindly execute raw model output against a database. In this project, I built a safe, end-to-end Text-to-SQL assistant designed to run entirely on local CPU instances.
> 
> First, on the modeling side, I fine-tuned Qwen2.5-Coder-3B using QLoRA with rank 16 across all linear projections, training on 8,634 Spider pairs with zero data leakage. I then quantized the model to 4-bit GGUF Q4_K_M, shrinking it by 69% from 6.2 GB down to 1.9 GB while retaining over 98.7% of its fine-tuned accuracy, achieving 70.70% Execution Accuracy on the 1,034 Spider dev set.
> 
> Second, on security, prompt engineering is never enough for SQL execution. I built a multi-layered defense-in-depth pipeline: a deterministic AST validator using sqlglot that inspects syntax trees in 2.4 milliseconds, paired with in-process SQLite read-only connection authorizers. In empirical red-teaming across 120 adversarial attacks and 60 prompt injections, we achieved a 0.00% pipeline attack success rate while maintaining a 99.37% pass rate on legitimate queries.
> 
> Finally, I packaged the system with a bounded FastAPI serving layer that manages CPU concurrency queues to prevent server crashes, integrated a dark-mode React interface, and backed everything by an automated CI test suite with 80 passing tests and zero fabricated metrics."*

---

### 5-Minute Technical Interview Deep Dive
> *"When designing this project, my goal was to solve two major production hurdles in generative database interfaces: **reasoning accuracy on constrained hardware** and **execution security**.
> 
> **1. Modeling & Parameter-Efficient Fine-Tuning:**
> I started by benchmarking the base 3B instruct model on 1,034 Spider dev queries, which yielded 62.28% zero-shot accuracy. To bridge the domain gap without massive GPU costs, I implemented QLoRA using 4-bit NormalFloat base quantization and low-rank adapters on all attention and feed-forward projections. Through ablation sweeps on an unseen validation split, rank 16 with alpha 32 reached the optimal validation loss of 0.3510. The merged FP16 model hit 71.57% accuracy. To serve on edge CPUs, I quantized the model using llama.cpp to GGUF Q4_K_M. This cut the RAM footprint from 6.2 GB to 1.9 GB while retaining 70.70% accuracy—less than a 1 percentage point drop—with a 4.68-second median latency on standard CPU cores.
> 
> **2. Defense-in-Depth Security Architecture:**
> Many systems try to enforce security using system prompts or secondary LLM evaluators. That approach adds significant latency and remains vulnerable to jailbreaks. Instead, I built a compiler-grade security pipeline:
> - Layer 1 is a static AST validator built with `sqlglot`. It parses queries in under 3 milliseconds, asserts that the AST root is strictly a SELECT statement, enforces a 4-join ceiling to stop Cartesian explosion attacks, and checks tables and functions against strict policies.
> - Layer 2 and 3 operate at the database connection level: opening databases with SQLite read-only URIs and binding C-level authorizer callbacks to intercept any dynamic bytecode execution attempting writes or administrative commands.
> - Layer 4 enforces a 100-row limit and execution timeouts.
> In red-teaming against 120 adversarial queries—including comment smuggling, stacked queries, and recursive CTE bombs—Layer 1 caught 87.5% statically, and the sandbox neutralized 100% of the rest, giving a 0.00% pipeline attack success rate. Furthermore, legitimate queries pass at 99.37%, with only two false blocks due to intentional join limits.
> 
> **3. Reliability & Honest Engineering:**
> I implemented execution-guided self-correction with error feedback and plurality voting over 5 sampled candidates. During Phase 3 benchmarking in the cloud, our diagnostic audit caught that the generation backend had omitted sampling flags, generating identical candidates. Rather than claiming artificial gains, I documented the run as unverified per Rule R9, added scoring regression tests, and created a formal re-evaluation specification.
> 
> **4. Production Serving & Packaging:**
> For deployment, I built an asynchronous FastAPI application with an internal concurrency semaphore and a bounded queue of depth 10. When the server is saturated, incoming queries receive a clean HTTP 503 instead of crashing the process. The React single-page frontend is built into static assets served directly by FastAPI in a single lightweight Docker container. Every single metric across the repository is backed by versioned JSON files in `results/`."*

---

## 3. LinkedIn / Portfolio Announcement Draft

```text
🚀 Excited to open-source the Fine-Tuned Text-to-SQL Assistant: QLoRA + Guarded Local LLM Serving!

Natural language interfaces to relational databases are powerful, but deploying them in production poses two huge challenges: model reasoning accuracy on lightweight hardware and the critical danger of unauthorized SQL execution.

Here is how I tackled it:
🔹 QLoRA Fine-Tuning: Adapted Qwen2.5-Coder-3B on 8,634 Spider training pairs (zero data leakage) and quantized to GGUF Q4_K_M. Footprint cut by 69% (6.2 GB → 1.9 GB) while retaining 70.70% Execution Accuracy on 1,034 Spider dev queries (+8.42 pp over base zero-shot) running locally on CPU.
🔹 Compiler-Grade Defense-in-Depth: Built a multi-layered security sandbox combining a deterministic AST validator (sqlglot, 2.44ms p50) with read-only SQLite authorizer callbacks. Result: 0.00% attack success across 120 adversarial red-team exploits and 60 prompt injection attacks, with a 99.37% pass rate on legitimate queries.
🔹 Robust Serving: Packaged with FastAPI (bounded concurrency queues + token bucket rate limiting), a modern dark-mode React frontend, Prometheus telemetry, and Docker.

Every number is empirically measured and reproducible. Check out the code, model card, and technical deep-dive:
🔗 GitHub: https://github.com/AshokSingodia-Codes/fine-tuned-text2sql

#AI #MachineLearning #LLM #TextToSQL #OpenSource #Python #FastAPI #GenAI #Security
```
