"""Upload fine-tuned LoRA adapter files to Hugging Face Hub.

Uses HF_TOKEN environment variable (never hardcoded or written to git).
"""

import os
import sys
from pathlib import Path

from huggingface_hub import HfApi

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def push_adapter_to_hf(
    repo_id: str,
    adapter_dir: str = "models/qlora_adapter",
    private: bool = False,
) -> None:
    token = os.getenv("HF_TOKEN")
    if not token:
        print("[ERROR] HF_TOKEN environment variable is not set. Please set it before uploading.")
        sys.exit(1)

    adapter_path = PROJECT_ROOT / adapter_dir
    if not adapter_path.exists():
        print(f"[ERROR] Adapter directory not found at {adapter_path}")
        sys.exit(1)

    api = HfApi(token=token)

    print(f"Creating repository {repo_id} (private={private})...")
    api.create_repo(repo_id=repo_id, repo_type="model", private=private, exist_ok=True)

    print(f"Uploading adapter files from {adapter_path} to {repo_id}...")
    api.upload_folder(
        folder_path=str(adapter_path),
        repo_id=repo_id,
        repo_type="model",
    )

    # Upload Model Card README
    readme_path = PROJECT_ROOT / "hf_release" / "README.md"
    if readme_path.exists():
        print(f"Uploading model card from {readme_path}...")
        api.upload_file(
            path_or_fileobj=str(readme_path),
            path_in_repo="README.md",
            repo_id=repo_id,
            repo_type="model",
        )

    print(f"[SUCCESS] Successfully pushed adapter to https://huggingface.co/{repo_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/push_to_hf.py <username/repo_name> [--private]")
        sys.exit(1)

    target_repo = sys.argv[1]
    is_private = "--private" in sys.argv
    push_adapter_to_hf(repo_id=target_repo, private=is_private)
