# Phase 1 Summary: Real Metric Provenance

This file records all official Phase 1 benchmark metrics, their source files, and reproduction commands.

| Metric Name | Value | Source File | Reproduction Command |
|---|---|---|---|
| Config A EX | 62.28% | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config A` |
| Config B EX | 66.15% | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config B` |
| Config C EX | 71.57% | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config C` |
| Config D EX | 70.70% | `results/eval_spider_latest.json` | `python scripts/eval_spider.py --config D` |
| Latency p50 | 4.68 s | `results/latency_latest.json` | `python scripts/bench_latency.py` |
| Latency p95 | 11.23 s | `results/latency_latest.json` | `python scripts/bench_latency.py` |
| Latency p99 | 15.22 s | `results/latency_latest.json` | `python scripts/bench_latency.py` |
