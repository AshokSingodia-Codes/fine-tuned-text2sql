# Kaggle GPU Setup & Execution Guide (Phase 1)

This guide walks you through executing the **Phase 1 Evaluation & Quantization Pipeline** on **Kaggle GPU** to eliminate Google Colab disconnects, browser timeouts, and idle limits.

---

## Why Kaggle GPU over Google Colab?

| Feature | Google Colab (Free) | Kaggle GPU (Free) |
|---|---|---|
| **GPU Quota** | Dynamic (~3–4 hrs before limit) | **30 hours per week** (dedicated) |
| **GPU Hardware** | 1x Tesla T4 (15 GB) | **2x Tesla T4 (2x16 GB)** or 1x P100 (16 GB) |
| **System RAM** | 12.7 GB | **30.0 GB** |
| **Session Disconnects** | Drops after 30 min idle / tab close | **Zero disconnects** in Commit mode |
| **Headless Cloud Execution** | Requires browser tab open constantly | **"Save & Run All (Commit)" runs up to 12 hours** in cloud |
| **Trained Adapter Re-use** | Requires Google Drive auth every time | **Pre-packaged in bundle**, skips 45-min training |

---

## Step 1: Generate the Kaggle Bundle Locally

From your local project terminal, create the bundle:
```powershell
python scripts/package_for_kaggle.py
```
This produces `kaggle_bundle.zip` (~304 MB) in the repository root. It includes:
- Spider dataset and SQLite databases (`data/raw/spider/`)
- Pre-trained QLoRA adapter weights (`models/qlora_adapter/adapter_model.safetensors`, 119.8 MB)
- Training telemetry (`results/training/training_config.json`)
- All scripts, evaluators, prompts, and test suites

---

## Step 2: Upload Bundle to Kaggle as a Dataset

1. Go to [kaggle.com](https://www.kaggle.com/) and sign in.
2. Click **Create** (top left) $\rightarrow$ **New Dataset**.
3. Drag & drop `kaggle_bundle.zip` (or browse to `e:\7thsem learning\projects\finue tune\kaggle_bundle.zip`).
4. Set the Dataset title to `t2s-kaggle-bundle` (or any name you like).
5. Click **Create**. Kaggle processes the upload in ~30–60 seconds.

---

## Step 3: Create & Configure Kaggle Notebook

1. In Kaggle, click **Create** $\rightarrow$ **New Notebook**.
2. Click **File** $\rightarrow$ **Import Notebook** $\rightarrow$ upload [`notebooks/run_phase1_kaggle.ipynb`](../notebooks/run_phase1_kaggle.ipynb).
3. In the right-hand **Notebook Settings** panel:
   - **Accelerator**: Select **GPU T4 x 2** (preferred) or **GPU P100**.
   - **Internet**: Toggle to **Internet on** *(Note: Kaggle requires phone number verification once to enable Internet access)*.
4. In the right sidebar under **Input**, click **+ Add Input**, search for your uploaded dataset (`t2s-kaggle-bundle`), and click the **+** icon to attach it.

---

## Step 4: Run Headless (No Disconnection Risk!)

Instead of running cells interactively and watching them for hours:
1. In the top-right toolbar of the notebook, click **Save Version**.
2. Select **Save & Run All (Commit)**.
3. Click **Save**.

> [!TIP]
> **You can now safely close the browser and shut down your computer!**
> Kaggle will execute the entire pipeline inside an isolated cloud container:
> 1. Verifies GPU & leakage checks.
> 2. Detects the existing QLoRA adapter and skips re-training.
> 3. Merges adapter weights into base FP16 weights (`models/merged_model`).
> 4. Builds `llama.cpp` and quantizes to GGUF `Q4_K_M` (`models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf`).
> 5. Evaluates Configs A, B, C (Transformers GPU) and Config D (GGUF Q4_K_M) across all 1,034 Spider dev queries.
> 6. Benchmarks serving latency and peak RSS memory across 200 questions.
> 7. Merges JSON outputs, generates comparison figures, and verifies Phase 1 acceptance.
> 8. Packs everything into `/kaggle/working/phase1_results.zip`.

---

## Step 5: Download & Ingest Results Locally

1. Once the notebook run completes (you will get an email notification):
   - Open your notebook on Kaggle.
   - Go to the **Output** section in the right panel.
   - Download **`phase1_results.zip`**.
2. Move or copy `phase1_results.zip` into your local project directory or `~/Downloads/`.
3. In your local terminal, run the ingestion harness:
   ```powershell
   python scripts/ingest_colab_results.py --zip phase1_results.zip
   ```
4. This automatically:
   - Unpacks real evaluation JSONs into `results/`
   - Unpacks the quantized GGUF model into `models/`
   - Runs `register_artifacts.py`
   - Runs `merge_eval_results.py`
   - Generates official charts via `make_figures.py`
   - Updates `docs/EVALUATION.md`
   - Executes acceptance verification via `check_phase1.py`
