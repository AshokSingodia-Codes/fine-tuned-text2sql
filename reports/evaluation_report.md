# Evaluation Report

## Execution Accuracy Summary (Spider Dev Split, n=1,034)
- Config A (Base Zero-Shot): 62.28% (Valid SQL Rate: 85.78%)
- Config B (Base 3-Shot): 66.15% (Valid SQL Rate: 89.07%)
- Config C (Fine-Tuned FP16): 71.57% (Valid SQL Rate: 93.13%)
- Config D (Quantized GGUF Q4_K_M): 70.70% (Valid SQL Rate: 94.68%)

## Latency Summary (Q4_K_M on Serving Hardware)
- Median Latency (p50): 4.68 s
- 95th Percentile Latency (p95): 11.23 s
- Hardware: Linux (x86_64, 2 physical cores, 31.35 GB RAM, CUDA)

## Safety Suite Summary
- Path A Attack Block Rate: 97.25% (106 / 109)
- Path C Sandbox Defense Rate: 92.66%
- Path D Full Pipeline Attack Success Rate: 0.00%
- Spider Dev False-Positive Rate: 0.19% (2 / 1034)
- Legitimate Query Pass Rate: 99.37% (1103 / 1110)
