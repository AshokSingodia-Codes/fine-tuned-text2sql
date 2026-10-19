# Hugging Face Space (Docker, CPU) Deployment Guide

This document describes the exact steps to deploy the **Fine-Tuned Text-to-SQL Assistant** to a **Hugging Face Space** using the Docker SDK on the standard free CPU tier (`cpu-basic`).

---

## 1. Space Hardware & Runtime Characteristics

- **Hardware Tier:** `cpu-basic` (Free)
  - **vCPU:** 2 vCPUs
  - **RAM:** 16 GB Memory
  - **Serving Port:** `7860` (standard Space port)
- **Sleep & Inactivity Behavior:**
  - Free CPU Spaces sleep automatically after **48 hours** of continuous inactivity.
  - When a user visits the URL, Hugging Face automatically wakes the Space via a **cold start**.
- **Cold-Start Model Loading:**
  - The GGUF model file (~1.9 GB) is fetched at container startup into a cache directory if not already mounted.
  - While loading, the `/ready` endpoint returns HTTP `503 Service Unavailable` with `{"status": "initializing"}`. The frontend UI polls `/ready` and renders an informative loading banner.

---

## 2. Environment Variables & Space Secrets

Configure these variables in your Space under **Settings -> Variables & Secrets**:

| Name | Type | Value / Purpose |
|---|---|---|
| `APP_PROFILE` | Variable | `demo` (disables public `/metrics`, applies demo banner) |
| `PORT` | Variable | `7860` |
| `MODEL_BACKEND` | Variable | `openai_compat` or `llama_cpp` (or `mock` for smoke tests) |
| `MODEL_PATH` | Variable | `models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf` |
| `DISABLE_AUTH` | Variable | `true` (enables public browser querying in demo) |
| `HF_TOKEN` | Secret | Scoped Hugging Face Read Token for accessing private model repo |

---

## 3. Step-by-Step Deployment Procedure

1. **Create New Space:**
   - Go to [Hugging Face Spaces](https://huggingface.co/spaces).
   - Select **Space Name**: `text2sql-assistant-demo`.
   - Select **SDK**: **Docker** (Blank).
   - Hardware: **CPU Basic (2 vCPU, 16 GB RAM)**.
2. **Push Repository:**
   - Clone the Space git repository locally:
     ```bash
     git clone https://huggingface.co/spaces/<YOUR-USERNAME>/text2sql-assistant-demo hf-space-deploy
     cd hf-space-deploy
     ```
   - Copy the repository files (`Dockerfile`, `.dockerignore`, `src/`, `configs/`, `config/`, `frontend/`, `db/`, `NOTICE`, `README.md`).
   - Push to `main`:
     ```bash
     git add -A
     git commit -m "deploy: initial text2sql guarded demo container"
     git push origin main
     ```
3. **Set Secrets & Build:**
   - Under Space **Settings**, add the `HF_TOKEN` secret.
   - The Space will automatically build the multi-stage Docker container (compiling React Vite assets into `frontend/dist` and launching FastAPI on port 7860).
4. **Access the Demo:**
   - The live web app will be accessible at: `https://huggingface.co/spaces/<YOUR-USERNAME>/text2sql-assistant-demo`.
   - The Chinook demo database (`chinook_1`) is pre-loaded as read-only.
