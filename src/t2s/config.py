"""Configuration loader module."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class PathsConfig:
    raw_data_dir: str = "data/raw/spider"
    processed_data_dir: str = "data/processed"
    reports_dir: str = "reports"
    models_dir: str = "models"


@dataclass
class SplitConfig:
    val_db_ratio: float = 0.10


@dataclass
class ModelConfig:
    base_model_name: str = "Qwen/Qwen2.5-Coder-3B-Instruct"
    fallback_model_name: str = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
    max_seq_len: int = 1024


@dataclass
class GenerationConfig:
    do_sample: bool = False
    temperature: float = 0.0
    max_new_tokens: int = 256
    include_sample_rows: bool = False


@dataclass
class SelfCorrectionConfig:
    enabled: bool = False
    max_retries: int = 2


@dataclass
class VotingConfig:
    enabled: bool = False
    n: int = 5
    temperature: float = 0.7
    per_candidate_timeout_seconds: float = 3.0
    total_budget_seconds: float = 15.0
    max_concurrent: int = 4


@dataclass
class ServingConfig:
    max_concurrent_generations: int = 1
    max_queue_depth: int = 10
    request_timeout_seconds: float = 30.0
    max_tokens_cap: int = 256
    max_request_bytes: int = 65536
    global_rate_limit_per_minute: int = 60
    enable_metrics_auth: bool = False


@dataclass
class AppConfig:
    seed: int = 42
    paths: PathsConfig = field(default_factory=PathsConfig)
    split: SplitConfig = field(default_factory=SplitConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    self_correction: SelfCorrectionConfig = field(default_factory=SelfCorrectionConfig)
    voting: VotingConfig = field(default_factory=VotingConfig)
    serving: ServingConfig = field(default_factory=ServingConfig)

    @classmethod
    def load(cls, config_path: str = "configs/config.yaml") -> "AppConfig":
        path = Path(config_path)
        if not path.exists():
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data: Dict[str, Any] = yaml.safe_load(f) or {}

        paths_data = data.get("paths", {})
        split_data = data.get("split", {})
        model_data = data.get("model", {})
        gen_data = data.get("generation", {})
        sc_data = data.get("self_correction", {})
        voting_data = data.get("voting", {})
        serving_data = data.get("serving", {})

        return cls(
            seed=data.get("seed", 42),
            paths=PathsConfig(**paths_data),
            split=SplitConfig(**split_data),
            model=ModelConfig(**model_data),
            generation=GenerationConfig(**gen_data),
            self_correction=SelfCorrectionConfig(**sc_data),
            voting=VotingConfig(**voting_data),
            serving=ServingConfig(**serving_data),
        )


def get_env_var(name: str, default: str = "") -> str:
    return os.getenv(name, default)
