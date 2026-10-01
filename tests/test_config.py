"""Test configuration loading."""

from src.t2s.config import AppConfig


def test_config_defaults(sample_config: AppConfig) -> None:
    assert sample_config.seed == 42
    assert sample_config.model.base_model_name == "Qwen/Qwen2.5-Coder-3B-Instruct"
    assert sample_config.split.val_db_ratio == 0.10


def test_config_load_from_yaml() -> None:
    config = AppConfig.load("configs/config.yaml")
    assert config.seed == 42
    assert config.paths.raw_data_dir == "data/raw/spider"
