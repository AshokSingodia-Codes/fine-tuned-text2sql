"""Export merged HuggingFace model to quantized GGUF format using llama.cpp.

Executes llama.cpp convert_hf_to_gguf.py and llama-quantize to build Q4_K_M.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def export_to_gguf(
    merged_model_dir: str = "models/merged_model",
    output_gguf_path: str = "models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf",
    quant_type: str = "Q4_K_M",
    llama_cpp_dir: str = "third_party/llama.cpp",
) -> None:
    print("\n========================================================")
    print("  GGUF CONVERSION & QUANTIZATION PIPELINE")
    print("========================================================")

    merged_path = Path(merged_model_dir)
    out_gguf = Path(output_gguf_path)
    llama_dir = Path(llama_cpp_dir)

    if not merged_path.exists():
        print(f"Error: Merged model directory not found at {merged_model_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Merged model path: {merged_model_dir}")
    print(f"Target GGUF file: {output_gguf_path}")
    print(f"Quantization type: {quant_type}")

    print("\n[Step 1] Commands to convert HF merged weights to FP16 GGUF:")
    print(
        f"  python {llama_dir}/convert_hf_to_gguf.py {merged_model_dir} --outfile models/merged_fp16.gguf"
    )

    print("\n[Step 2] Commands to quantize FP16 GGUF to Q4_K_M:")
    print(f"  {llama_dir}/llama-quantize models/merged_fp16.gguf {output_gguf_path} {quant_type}")

    if llama_dir.exists() and (llama_dir / "convert_hf_to_gguf.py").exists():
        try:
            print("\nExecuting convert_hf_to_gguf.py...")
            subprocess.run(
                [
                    sys.executable,
                    str(llama_dir / "convert_hf_to_gguf.py"),
                    str(merged_path),
                    "--outfile",
                    "models/merged_fp16.gguf",
                ],
                check=True,
            )
            print("\nExecuting llama-quantize...")
            subprocess.run(
                [
                    str(llama_dir / "llama-quantize"),
                    "models/merged_fp16.gguf",
                    str(out_gguf),
                    quant_type,
                ],
                check=True,
            )
            print(f"\nSUCCESS: Created GGUF model binary at {output_gguf_path}")
        except Exception as e:
            print(
                f"\nNotice: Automatic execution halted ({e}). Please run the exact commands printed above."
            )
    else:
        print(
            f"\nNotice: llama.cpp toolchain not found at {llama_cpp_dir}. Please see docs/GGUF.md for full instructions."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert HF merged model to GGUF Q4_K_M format.")
    parser.add_argument("--merged-dir", default="models/merged_model")
    parser.add_argument("--output-gguf", default="models/Qwen2.5-Coder-3B-Instruct-Q4_K_M.gguf")
    parser.add_argument("--quant-type", default="Q4_K_M")
    parser.add_argument("--llama-cpp-dir", default="third_party/llama.cpp")

    args = parser.parse_args()
    export_to_gguf(
        merged_model_dir=args.merged_dir,
        output_gguf_path=args.output_gguf,
        quant_type=args.quant_type,
        llama_cpp_dir=args.llama_cpp_dir,
    )


if __name__ == "__main__":
    main()
