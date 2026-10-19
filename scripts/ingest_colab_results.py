"""Ingest Colab Phase 1 execution results bundle into repository.

Extracts results/, results/training/, and models/qlora_adapter/ from phase1_results.zip.
Triggers artifact registration, result merging, figure generation, eval documentation,
and Phase 1 verification without inventing or faking metrics.
"""

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def find_results_zip(custom_path: str = None) -> Path:
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified zip file not found at: {custom_path}")

    # Check default locations
    local_zip = PROJECT_ROOT / "phase1_results.zip"
    if local_zip.exists():
        return local_zip

    user_downloads = Path.home() / "Downloads" / "phase1_results.zip"
    if user_downloads.exists():
        return user_downloads

    raise FileNotFoundError(
        "Could not find phase1_results.zip in repo root or ~/Downloads. "
        "Please provide path via --zip /path/to/phase1_results.zip."
    )


def ingest_results(zip_path: Path) -> None:
    print(f"Ingesting Colab Phase 1 results from: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        print(f"Zip archive contains {len(namelist)} items.")

        # Extract results/, results/training/, models/qlora_adapter/
        for name in namelist:
            if name.startswith("results/") or name.startswith("models/qlora_adapter/"):
                if not name.startswith("results/smoke/"):
                    zf.extract(name, PROJECT_ROOT)

            # Record GGUF file location if present in zip
            if name.endswith(".gguf"):
                target_gguf = PROJECT_ROOT / "models" / Path(name).name
                target_gguf.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src_file, open(target_gguf, "wb") as dst_file:
                    dst_file.write(src_file.read())
                print(f"Extracted GGUF model binary to: {target_gguf}")

    print("Unpacked results and artifacts successfully.")

    # 1. Run register_artifacts.py
    print("\n1. Running register_artifacts.py...")
    subprocess.run([sys.executable, "scripts/register_artifacts.py"], check=True)

    # 2. Run merge_eval_results.py
    print("\n2. Running merge_eval_results.py...")
    subprocess.run([sys.executable, "scripts/merge_eval_results.py"], check=True)

    # 3. Run make_figures.py
    print("\n3. Running make_figures.py...")
    subprocess.run([sys.executable, "scripts/make_figures.py"], check=True)

    # 4. Run make_eval_doc.py
    print("\n4. Running make_eval_doc.py...")
    subprocess.run([sys.executable, "scripts/make_eval_doc.py"], check=True)

    # 5. Run check_phase1.py
    print("\n5. Running check_phase1.py...")
    subprocess.run([sys.executable, "scripts/check_phase1.py"], check=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Phase 1 Colab results zip.")
    parser.add_argument("--zip", type=str, default=None, help="Path to phase1_results.zip")
    args = parser.parse_args()

    zip_file = find_results_zip(args.zip)
    ingest_results(zip_file)


if __name__ == "__main__":
    main()
