"""Database-based dataset splitter."""

import random
from typing import List, Set, Tuple

from src.t2s.data.spider_loader import SpiderExample


def split_train_val_by_db(
    examples: List[SpiderExample], val_ratio: float = 0.10, seed: int = 42
) -> Tuple[List[SpiderExample], List[SpiderExample], Set[str], Set[str]]:
    unique_dbs = sorted(list({ex.db_id for ex in examples}))

    rng = random.Random(seed)
    rng.shuffle(unique_dbs)

    num_val_dbs = max(1, int(len(unique_dbs) * val_ratio))
    val_dbs = set(unique_dbs[:num_val_dbs])
    train_dbs = set(unique_dbs[num_val_dbs:])

    train_examples = [ex for ex in examples if ex.db_id in train_dbs]
    val_examples = [ex for ex in examples if ex.db_id in val_dbs]

    return train_examples, val_examples, train_dbs, val_dbs
