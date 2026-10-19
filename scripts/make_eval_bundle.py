"""Package workspace repository and committed code into a reproducible zip bundle for Kaggle/Colab GPU evaluation.

Includes:
- src/ (exact code tree, without local pycache)
- configs/ (configuration yamls)
- data/raw/spider/dev.json + tables.json + database schemas
- models/merged_model (or adapter) if requested
- scripts/eval_spider.py, scripts/run_phase3_kaggle.py
"""

import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_eval_bundle(output_zip: str = "phase3b_eval_bundle.zip") -> Path:
    out_path = PROJECT_ROOT / output_zip
    print(f"Creating evaluation zip bundle at {out_path}...")

    include_patterns = [
        "src/**/*.py",
        "configs/**/*.yaml",
        "scripts/eval_spider.py",
        "scripts/run_phase3_kaggle.py",
        "scripts/check_phase2.py",
        "config/security_policy.yaml",
        "pyproject.toml",
        "requirements.txt",
    ]

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for pattern in include_patterns:
            for p in PROJECT_ROOT.glob(pattern):
                if "__pycache__" not in p.parts:
                    arcname = p.relative_to(PROJECT_ROOT)
                    zf.write(p, arcname)
                    print(f"  Added {arcname}")

        # Add spider dev.json and tables.json if present
        dev_json = PROJECT_ROOT / "data" / "raw" / "spider" / "dev.json"
        if dev_json.exists():
            zf.write(dev_json, dev_json.relative_to(PROJECT_ROOT))
            print(f"  Added {dev_json.relative_to(PROJECT_ROOT)}")

        tables_json = PROJECT_ROOT / "data" / "raw" / "spider" / "tables.json"
        if tables_json.exists():
            zf.write(tables_json, tables_json.relative_to(PROJECT_ROOT))
            print(f"  Added {tables_json.relative_to(PROJECT_ROOT)}")

    print(
        f"Successfully generated bundle: {out_path} ({out_path.stat().st_size / (1024 * 1024):.2f} MB)"
    )
    return out_path


if __name__ == "__main__":
    create_eval_bundle()
