# Execution Progress Log

| Phase | Title | Status | Date | Key Numbers | Evidence Files |
|---|---|---|---|---|---|
| **Phase 0** | Repo Audit & Baseline Freeze | ✅ COMPLETED | 2026-10-18 | 44/44 Tests Passed, 0 Leakage, Model Artifacts Verified | `results/baseline/pytest.txt`, `results/baseline/ruff.txt`, `docs/CURRENT_STATE.md`, `docs/ARTIFACTS.md`, `scripts/check_leakage.py` |
| **Phase 1** | Real Evaluation (Execution Accuracy) | ✅ COMPLETED | 2026-10-18 | EX(A)=62.28%, EX(B)=66.15%, EX(C)=71.57%, EX(D)=70.70%, Latency p50=4.68s, 44 tests pass | `results/eval_spider_latest.json`, `results/latency_latest.json`, `results/figures/ex_comparison.png`, `docs/EVALUATION.md`, `docs/PHASE1_SUMMARY.md` |
| **Phase 2** | Hardened & Honest Security Evaluation | ✅ COMPLETED | 2026-10-18 | Attack Block(A)=87.50%, Attack Success(D)=0.00%, Prompt Attack Success(B)=0.00%, Benign Pass=100.00%, FPR=0.18%, 1000 Fuzz Green | `results/redteam_latest.json`, `results/unblocked_audit.json`, `results/false_blocks.json`, `docs/THREAT_MODEL.md` |
| **Phase 3** | Execution-Guided Self-Correction & Voting | ✅ COMPLETED | 2026-10-19 | Accepted by user 2026-10-19. Dev n=1,034 ablation on base model: BASE+greedy, BASE+SC, BASE+V, BASE+SC+V all EX=62.28% (base model parity), Calls/Q: BASE+SC=1.13×, BASE+V=5.0×, BASE+SC+V=5.63×, Latency multipliers: 1.43× (BASE+SC), 4.97× (BASE+V), 7.23× (BASE+SC+V). 6/6 unit tests pass, 72/72 suite green | `results/ablation_latest.json`, `src/t2s/service/self_correct.py`, `src/t2s/service/voting.py`, `tests/test_phase3_service.py`, `scripts/check_phase3.py`, `docs/EVALUATION.md#5`, `docs/LIMITATIONS.md#21` |
| **Phase 4** | Multi-Database Layer (SQLite + Postgres) | ⏭️ SKIPPED | 2026-10-19 | Skipped by decision (MVP path); not claimed on the resume | - |
| **Phase 5** | Schema RAG for Large Databases | ⏳ PENDING | - | - | - |
| **Phase 6** | Governance: PII Masking, RLS & Auth | ⏭️ SKIPPED | 2026-10-19 | Skipped by decision (MVP path); not claimed on the resume | - |
| **Phase 7** | Domain Adaptation Experiment | ⏭️ SKIPPED | 2026-10-19 | Skipped by decision (MVP path); not claimed on the resume | - |
| **Phase 8** | Production Packaging & Deployment (MVP, SQLite) | PARTIAL: model published on Hugging Face Hub; live Space not running (cpu-basic quota 0 on this account); local Docker unverified (docker not installed on host) | 2026-10-20 | Serving limits active (queue=10, conc=1), /ready & /metrics auth, multi-stage Dockerfile, Hugging Face Space guide, load test (concurrency 1/2/4 green) | `Dockerfile`, `deploy/README_DEPLOY.md`, `NOTICE`, `docs/MODEL_CARD.md`, `hf_release/README.md`, `scripts/push_to_hf.py`, `tests/test_serving_limits.py`, `results/demo_examples.json`, `results/loadtest_latest.json` |
| **Phase 9** | Documentation & Portfolio Packaging | ✅ COMPLETED | 2026-10-20 | Table generator `scripts/make_readme_tables.py`, honest numbers in README/MODEL_CARD, `docs/RESUME_NUMBERS.md` single source of truth, failure query analysis, blog post draft | `scripts/make_readme_tables.py`, `README.md`, `docs/RESUME_NUMBERS.md`, `docs/ARCHITECTURE.md`, `docs/LIMITATIONS.md`, `docs/BLOG.md` |
| **Phase 10** | Resume & Interview Readiness | ✅ COMPLETED | 2026-10-20 | 4 ATS-ready resume bullets (zero fabricated metrics), 25 grounded interview Q&As in `docs/INTERVIEW_PREP.md`, 90s/5min pitch scripts in `docs/PORTFOLIO_KIT.md` | `docs/INTERVIEW_PREP.md`, `docs/PORTFOLIO_KIT.md`, `docs/RESUME_NUMBERS.md` |

### Phase 3 Provenance Record
- **Command / Execution Run**: Kaggle notebook execution (`notebook6f1ee3abad`), duration 35,618.8s (logged at 2026-10-18T22:14:39.006516+00:00).
- **Machine & Hardware**: Kaggle GPU T4 x2 (14.56 GiB VRAM each). CPU model: not recorded. Host OS: Linux (container). Python version: not recorded. SQLite version: not recorded.
- **Model Artifacts Evaluated**:
  - Config D, E, F, G: Evaluated using base `Qwen/Qwen2.5-Coder-3B-Instruct` (Hugging Face `transformers` backend) to isolate the self-correction and consensus voting algorithmic gains independently from fine-tuning weights. (Note: Fine-tuned GGUF Q4_K_M is evaluated separately under Config C/D in `results/eval_spider_latest.json`).
- **Dataset Sample Size ($n$) & Seed**: $n = 1,034$ Spider dev questions; `--seed 42`.
- **Version Control & Policy Integrity**:
  - Git commit hash: `unknown_commit` (recorded in JSON metadata).
  - Dirty tree status: not recorded.
  - Policy file hash: not recorded in `ablation_latest.json` (Phase 3 ablation evaluated base model generation and database execution repair without mutating safety policy).
