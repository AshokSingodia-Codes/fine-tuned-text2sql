"""Test dataset splitting by database."""

from src.t2s.data.spider_loader import SpiderExample
from src.t2s.data.split import split_train_val_by_db


def test_split_by_db_no_overlap() -> None:
    examples = [
        SpiderExample("q1", "db1", "SELECT 1"),
        SpiderExample("q2", "db1", "SELECT 2"),
        SpiderExample("q3", "db2", "SELECT 3"),
        SpiderExample("q4", "db3", "SELECT 4"),
        SpiderExample("q5", "db4", "SELECT 5"),
    ]

    train_exs, val_exs, train_dbs, val_dbs = split_train_val_by_db(
        examples, val_ratio=0.25, seed=42
    )

    assert len(train_dbs.intersection(val_dbs)) == 0
    assert len(train_exs) + len(val_exs) == len(examples)
    for ex in train_exs:
        assert ex.db_id in train_dbs
        assert ex.db_id not in val_dbs
    for ex in val_exs:
        assert ex.db_id in val_dbs
        assert ex.db_id not in train_dbs
