"""Artifact Registration Script.

Scans models/ for real model binary files, verifies size (> 1 MB) and absence of
PLACEHOLDER strings, calculates SHA256 checksums, and updates docs/ARTIFACTS.md.
"""

import hashlib
import sys
from pathlib import Path
from typing import Dict, List

MIN_FILE_SIZE_BYTES = 1024 * 1024  # 1 MB threshold


def calculate_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def check_for_placeholder_text(filepath: Path) -> bool:
    try:
        with open(filepath, "rb") as f:
            header = f.read(4096)
            if b"PLACEHOLDER" in header or b"MOCK_" in header:
                return True
    except Exception:
        pass
    return False


def register_artifacts() -> None:
    print("\n========================================================")
    print("  MODEL ARTIFACT REGISTRATION & VERIFICATION")
    print("========================================================")

    models_dir = Path("models")
    if not models_dir.exists():
        print("Error: models/ directory does not exist.", file=sys.stderr)
        sys.exit(1)

    merged_model_weight = models_dir / "merged_model" / "model.safetensors"
    if not merged_model_weight.exists():
        shards = list((models_dir / "merged_model").glob("model-*.safetensors"))
        if shards:
            merged_model_weight = shards[0]

    target_artifacts = [
        ("QLoRA Adapter Config", models_dir / "qlora_adapter" / "adapter_config.json", False),
        ("QLoRA Adapter Weights", models_dir / "qlora_adapter" / "adapter_model.safetensors", True),
        ("Merged FP16 Model Weights", merged_model_weight, True),
        ("Quantized GGUF Model Binary", models_dir / "Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf", True),
    ]

    artifact_records: List[Dict[str, str]] = []
    missing_count = 0

    for name, p, enforce_size in target_artifacts:
        if not p.exists():
            artifact_records.append(
                {
                    "name": name,
                    "path": str(p),
                    "status": "MISSING",
                    "size": "0 Bytes",
                    "sha256": "N/A",
                    "notes": "File does not exist.",
                }
            )
            if enforce_size:
                missing_count += 1
            continue

        size_bytes = p.stat().st_size

        if check_for_placeholder_text(p):
            print(f"REFUSED: File {p} contains PLACEHOLDER/MOCK content!", file=sys.stderr)
            artifact_records.append(
                {
                    "name": name,
                    "path": str(p),
                    "status": "MISSING (REFUSED - PLACEHOLDER)",
                    "size": f"{size_bytes} Bytes",
                    "sha256": "N/A",
                    "notes": "REFUSED: Contains placeholder text string.",
                }
            )
            missing_count += 1
            continue

        if enforce_size and size_bytes < MIN_FILE_SIZE_BYTES:
            print(f"REFUSED: File {p} is too small ({size_bytes} Bytes < 1 MB)!", file=sys.stderr)
            artifact_records.append(
                {
                    "name": name,
                    "path": str(p),
                    "status": "MISSING (REFUSED - UNDER 1MB)",
                    "size": f"{size_bytes} Bytes",
                    "sha256": "N/A",
                    "notes": f"REFUSED: Size {size_bytes} B is below 1 MB minimum.",
                }
            )
            missing_count += 1
            continue

        print(f"VERIFIED: {name} at {p} ({size_bytes:,} bytes)")
        sha = calculate_sha256(p)
        size_mb = round(size_bytes / (1024 * 1024), 2)
        artifact_records.append(
            {
                "name": name,
                "path": str(p),
                "status": "FOUND",
                "size": f"{size_mb} MB ({size_bytes:,} B)",
                "sha256": sha,
                "notes": "Verified real model binary.",
            }
        )

    # Generate docs/ARTIFACTS.md
    doc_lines = [
        "# Model Artifacts & Binary Tracking Log",
        "",
        "This document records the exact paths, file sizes, SHA256 checksums, and verification status for all model weights, fine-tuned adapters, and quantized GGUF artifacts.",
        "",
        "---",
        "",
        "## 1. Artifact Verification Registry",
        "",
        "| Artifact Name | Path | Status | File Size | SHA256 Checksum | Notes |",
        "|---|---|---|---|---|---|",
    ]

    for rec in artifact_records:
        doc_lines.append(
            f"| **{rec['name']}** | `{rec['path']}` | **{rec['status']}** | {rec['size']} | `{rec['sha256']}` | {rec['notes']} |"
        )

    doc_lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Status Summary",
            "",
            f"- **Verified Real Artifacts**: {len(target_artifacts) - missing_count} / {len(target_artifacts)}",
            f"- **Missing / Refused Artifacts**: {missing_count} / {len(target_artifacts)}",
        ]
    )

    artifacts_md_path = Path("docs/ARTIFACTS.md")
    artifacts_md_path.parent.mkdir(parents=True, exist_ok=True)
    with open(artifacts_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(doc_lines) + "\n")

    print(f"\nUpdated {artifacts_md_path} successfully.")
    if missing_count > 0:
        print(
            f"Note: {missing_count} artifacts are MISSING or REFUSED. Real model files required before Phase 1 run."
        )


if __name__ == "__main__":
    register_artifacts()
