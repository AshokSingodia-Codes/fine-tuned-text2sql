"""Merge QLoRA adapter into FP16 base model weights.

Saves merged model to models/merged_model/.
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.t2s.train.merge import merge_adapter_to_base  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge LoRA adapter into FP16 base model.")
    parser.add_argument(
        "--adapter-dir", "--adapter-path", dest="adapter_dir", default="models/qlora_adapter"
    )
    parser.add_argument("--output-dir", default="models/merged_model")
    parser.add_argument("--base-model", default="Qwen/Qwen2.5-Coder-3B-Instruct")

    args = parser.parse_args()

    merge_adapter_to_base(
        adapter_dir=args.adapter_dir,
        merged_output_dir=args.output_dir,
        base_model_name=args.base_model,
    )


if __name__ == "__main__":
    main()
