# Windows PowerShell Quickstart Guide

This guide provides the exact commands for setting up and running the **Text-to-SQL Assistant** on Windows using PowerShell.

---

## 1. Prerequisites

- **OS**: Windows 10 or 11 (tested on Windows 11 AMD64)
- **Python**: 3.11 or 3.12 (tested on Python 3.12.3)
- **Git**: Installed and available in PowerShell (`git --version`)
- **RAM**: Minimum 6 GB free RAM (system tested with 7.7 GB total RAM)
- **Disk**: 2.5 GB free disk space (model weight is 1.93 GB)

---

## 2. Step-by-Step Setup

### Step 1: Clone the Repository
Open PowerShell and run:
```powershell
git clone https://github.com/AshokSingodia-Codes/fine-tuned-text2sql.git
cd fine-tuned-text2sql
```

### Step 2: Create and Activate Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
*(If PowerShell blocks script activation, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

### Step 3: Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

### Step 4: Install `llama-cpp-python`

#### Recommended: Prebuilt CPU Wheel (Fastest, No C++ Compiler Needed)
```powershell
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu
```

#### Build From Source (Requires CMake & Visual Studio C++ Build Tools)
If building from source without prebuilt wheels:
```powershell
pip install cmake
pip install llama-cpp-python --no-binary llama-cpp-python
```
*Note: If Visual Studio C++ Build Tools are not installed, building from source fails with:*
```text
CMake Error: CMAKE_C_COMPILER not set, after EnableLanguage
CMake Error: CMAKE_CXX_COMPILER not set, after EnableLanguage
error: subprocess-exited-with-error
```

---

## 3. Download Model Weights

Download the fine-tuned 1.93 GB GGUF model directly from Hugging Face Model Hub (public, no token required):
```powershell
pip install huggingface_hub
python -c "from huggingface_hub import hf_hub_download; hf_hub_download(repo_id='Ashoksainibadu/fine-tuned-text2sql', filename='Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf', local_dir='models')"
```

---

## 4. Build Frontend (Optional, for Web UI)
`powershell
cd frontend
npm install
npm run build
cd ..
`
*(If Node.js is not installed, skip this step; all FastAPI endpoints and /docs work without compiling the frontend).*

## 5. Run the Application

### Option A: Real LLM Inference (CPU)
```powershell
$env:MODEL_BACKEND="llama_cpp"
$env:MODEL_PATH="models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf"
$env:DB_DIR="db/seeds"
$env:PORT="8000"
uvicorn src.t2s.serving.app:app --host 127.0.0.1 --port 8000
```

### Option B: Instant Mock Mode (Zero Weight)
```powershell
$env:MODEL_BACKEND="mock"
$env:DB_DIR="db/seeds"
$env:PORT="8000"
uvicorn src.t2s.serving.app:app --host 127.0.0.1 --port 8000
```

Open your browser to:
- **Web UI**: `http://127.0.0.1:8000`
- **Interactive OpenAPI Documentation**: `http://127.0.0.1:8000/docs`

---

## 6. Test Query via PowerShell

Open a second PowerShell window:
```powershell
# 1. Healthcheck
Invoke-RestMethod -Uri http://127.0.0.1:8000/healthz

# 2. Query Chinook database
$body = @{
    db_id = "chinook"
    question = "How many artists are there?"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://127.0.0.1:8000/v1/query -Method Post -ContentType "application/json" -Body $body
```


> Note: CI workflow includes a container build and /healthz and /ready smoke test; CI has not been confirmed green yet.
