"""Data Leakage Audit Script.

Verifies zero overlap of (question, db_id) pairs and database schemas (db_id)
between training data (Spider train) and evaluation data (Spider dev).
"""

import argparse
import sys
from pathlib import Path
from typing import Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.t2s.data.spider_loader import load_spider_examples


def check_leakage(
    train_spider_path: str = "data/raw/spider/train_spider.json",
    train_others_path: str = "data/raw/spider/train_others.json",
    dev_path: str = "data/raw/spider/dev.json",
) -> Tuple[int, int]:
    train_files = [Path(train_spider_path), Path(train_others_path)]
    dev_file = Path(dev_path)

    train_pairs: Set[Tuple[str, str]] = set()
    train_db_ids: Set[str] = set()

    for tf in train_files:
        if tf.exists():
            for ex in load_spider_examples(str(tf)):
                train_pairs.add((ex.question.strip().lower(), ex.db_id.strip().lower()))
                train_db_ids.add(ex.db_id.strip().lower())

    dev_pairs: Set[Tuple[str, str]] = set()
    dev_db_ids: Set[str] = set()

    if dev_file.exists():
        for ex in load_spider_examples(str(dev_file)):
            dev_pairs.add((ex.question.strip().lower(), ex.db_id.strip().lower()))
            dev_db_ids.add(ex.db_id.strip().lower())

    pair_overlap = train_pairs.intersection(dev_pairs)
    db_overlap = train_db_ids.intersection(dev_db_ids)

    print("\n========================================================")
    print("  SPIDER DATASET LEAKAGE AUDIT RESULT")
    print("========================================================")
    print(f"Total Unique Train Questions: {len(train_pairs)}")
    print(f"Total Unique Dev Questions:   {len(dev_pairs)}")
    print(f"Train Database IDs Count:     {len(train_db_ids)}")
    print(f"Dev Database IDs Count:       {len(dev_db_ids)}")
    print(f"(Question, db_id) Overlap:    {len(pair_overlap)}")
    print(f"Database ID Overlap:          {len(db_overlap)}")
    print("========================================================\n")

    return len(pair_overlap), len(db_overlap)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check for data leakage between train and dev sets."
    )
    parser.add_argument("--train-spider", default="data/raw/spider/train_spider.json")
    parser.add_argument("--train-others", default="data/raw/spider/train_others.json")
    parser.add_argument("--dev", default="data/raw/spider/dev.json")
    args = parser.parse_args()

    pair_overlap, db_overlap = check_leakage(args.train_spider, args.train_others, args.dev)

    if pair_overlap > 0 or db_overlap > 0:
        print(f"CRITICAL ERROR: Data leakage detected! Pairs: {pair_overlap}, DB IDs: {db_overlap}")
        sys.exit(1)

    print("SUCCESS: 0 data leakage overlap detected between train and dev splits.")
    sys.exit(0)


if __name__ == "__main__":
    main()
