# Model Card: Qwen2.5-Coder-3B Text-to-SQL QLoRA

## Model Details
- **Base Model**: Qwen2.5-Coder-3B-Instruct
- **Fine-Tuning Technique**: QLoRA (4-bit NF4 Quantization, LoRA rank r=16, alpha=32)
- **Target Projection Layers**: `q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj`
- **Dataset**: Spider 1.0 (Yale Text-to-SQL Dataset, CC BY-SA 4.0)
- **Deployment Format**: GGUF `Q4_K_M` (1.9 GB)

## Evaluation Metrics (Spider Dev Split, n=1,034)
- **Base Zero-Shot Execution Accuracy**: 62.28%
- **Fine-Tuned FP16 Execution Accuracy**: 71.57%
- **Quantized GGUF Q4_K_M Execution Accuracy**: 70.70%
- **Valid SQL Rate**: 94.68%
- **Quantization Size Reduction**: ~6.2 GB -> 1.9 GB (~69.3% memory saving)

## Intended Use & Safety
- **Intended Use**: Read-only text-to-SQL analytics on relational databases.
- **Guardrails**: Served behind AST SQL Validator and SQLite `mode=ro` read-only connection authorizer.
