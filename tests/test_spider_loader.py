"""Test spider loader and validation."""

from pathlib import Path

from src.t2s.data.spider_loader import load_spider_examples, load_tables_json, validate_dataset


def test_spider_loader_dev_set() -> None:
    dev_path = Path("data/raw/spider/dev.json")
    if not dev_path.exists():
        return

    examples = load_spider_examples(str(dev_path))
    assert len(examples) == 1034
    assert examples[0].question != ""
    assert examples[0].db_id != ""
    assert examples[0].query != ""


def test_tables_json_loader() -> None:
    tables_path = Path("data/raw/spider/tables.json")
    if not tables_path.exists():
        return

    tables = load_tables_json(str(tables_path))
    assert len(tables) > 0
    assert "concert_singer" in tables or len(tables) >= 20


def test_validate_dataset_profile() -> None:
    data_dir = Path("data/raw/spider")
    if not data_dir.exists():
        return

    profile = validate_dataset("data/raw/spider", "reports")
    assert profile["train_spider_questions"] == 7000
    assert profile["dev_questions"] == 1034
    assert profile["db_overlap_count"] == 0
