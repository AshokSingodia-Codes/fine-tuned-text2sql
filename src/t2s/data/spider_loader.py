"""Spider dataset loader and validator."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


@dataclass
class SpiderExample:
    question: str
    db_id: str
    query: str
    hardness: Optional[str] = None


@dataclass
class SpiderTableSchema:
    db_id: str
    table_names: List[str]
    column_names: List[Tuple[int, str]]  # list of (table_index, column_name)
    column_types: List[str]
    primary_keys: List[int]
    foreign_keys: List[Tuple[int, int]]


def load_spider_examples(json_path: str) -> List[SpiderExample]:
    path = Path(json_path)
    if not path.exists():
        raise FileNotFoundError(f"Spider json file not found: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    examples: List[SpiderExample] = []
    for item in data:
        ex = SpiderExample(
            question=item["question"],
            db_id=item["db_id"],
            query=item["query"],
            hardness=item.get("hardness"),
        )
        examples.append(ex)

    return examples


def load_tables_json(tables_path: str) -> Dict[str, SpiderTableSchema]:
    path = Path(tables_path)
    if not path.exists():
        raise FileNotFoundError(f"Tables json file not found: {tables_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    tables: Dict[str, SpiderTableSchema] = {}
    for item in data:
        schema = SpiderTableSchema(
            db_id=item["db_id"],
            table_names=item["table_names_original"],
            column_names=[(col[0], col[1]) for col in item["column_names_original"]],
            column_types=item["column_types"],
            primary_keys=item["primary_keys"],
            foreign_keys=[(fk[0], fk[1]) for fk in item["foreign_keys"]],
        )
        tables[schema.db_id] = schema

    return tables


def validate_dataset(
    data_dir: str = "data/raw/spider", reports_dir: str = "reports"
) -> Dict[str, Any]:
    raw_path = Path(data_dir)
    rep_path = Path(reports_dir)
    rep_path.mkdir(parents=True, exist_ok=True)

    spider_train_path = raw_path / "train_spider.json"
    others_train_path = raw_path / "train_others.json"
    dev_path = raw_path / "dev.json"
    db_dir = raw_path / "database"

    # Load train and dev examples
    train_spider_exs = load_spider_examples(str(spider_train_path))
    train_others_exs = (
        load_spider_examples(str(others_train_path)) if others_train_path.exists() else []
    )
    full_train_exs = train_spider_exs + train_others_exs
    dev_exs = load_spider_examples(str(dev_path))

    # Databases in train and dev
    train_dbs: Set[str] = {ex.db_id for ex in full_train_exs}
    dev_dbs: Set[str] = {ex.db_id for ex in dev_exs}
    db_overlap = train_dbs.intersection(dev_dbs)

    # Verify every db_id has a SQLite file
    missing_dbs: List[str] = []
    all_dbs = train_dbs.union(dev_dbs)
    for db_id in all_dbs:
        db_file = db_dir / db_id / f"{db_id}.sqlite"
        if not db_file.exists():
            missing_dbs.append(db_id)

    # Test gold SQL execution
    def test_sql_execution(examples: List[SpiderExample]) -> Tuple[int, int, List[Dict[str, str]]]:
        passed = 0
        failed = 0
        failures: List[Dict[str, str]] = []
        for ex in examples:
            db_file = db_dir / ex.db_id / f"{ex.db_id}.sqlite"
            if not db_file.exists():
                failed += 1
                failures.append(
                    {"db_id": ex.db_id, "query": ex.query, "error": "Database file missing"}
                )
                continue

            try:
                # Read-only connection
                conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True, timeout=5.0)
                cursor = conn.cursor()
                cursor.execute(ex.query)
                _ = cursor.fetchall()
                conn.close()
                passed += 1
            except Exception as e:
                failed += 1
                failures.append({"db_id": ex.db_id, "query": ex.query, "error": str(e)})

        return passed, failed, failures

    train_passed, train_failed, train_failures = test_sql_execution(full_train_exs)
    dev_passed, dev_failed, dev_failures = test_sql_execution(dev_exs)

    # Calculate hardness distribution for dev if available
    dev_hardness: Dict[str, int] = {}
    for ex in dev_exs:
        if ex.hardness:
            dev_hardness[ex.hardness] = dev_hardness.get(ex.hardness, 0) + 1

    profile = {
        "train_spider_questions": len(train_spider_exs),
        "train_others_questions": len(train_others_exs),
        "train_total_questions": len(full_train_exs),
        "dev_questions": len(dev_exs),
        "train_databases_count": len(train_dbs),
        "dev_databases_count": len(dev_dbs),
        "db_overlap_count": len(db_overlap),
        "db_overlap_list": list(db_overlap),
        "missing_database_files": missing_dbs,
        "train_gold_sql_passed": train_passed,
        "train_gold_sql_failed": train_failed,
        "dev_gold_sql_passed": dev_passed,
        "dev_gold_sql_failed": dev_failed,
        "dev_hardness_distribution": dev_hardness,
    }

    output_json = rep_path / "data_profile.json"
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    return profile


if __name__ == "__main__":
    profile = validate_dataset()
    print("Data Profile:")
    print(json.dumps(profile, indent=2))
