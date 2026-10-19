"""Regression test for Phase 3 scoring: verifies the SCORED SQL is the repaired or voted query, not the initial greedy attempt."""

import sqlite3
import tempfile
from pathlib import Path

from src.t2s.safety.executor import SafeSQLExecutor
from src.t2s.safety.validator import SQLValidator
from src.t2s.service.self_correct import SelfCorrectionRunner
from src.t2s.service.voting import ConsensusVoter


def test_self_correction_scored_sql_is_repaired():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.sqlite"
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE users (id INT, full_name TEXT);")
        cur.execute("INSERT INTO users VALUES (1, 'Alice'), (2, 'Bob');")
        conn.commit()
        conn.close()

        validator = SQLValidator()
        executor = SafeSQLExecutor()
        corrector = SelfCorrectionRunner(validator=validator, executor=executor, max_retries=2)

        # Initial attempt is wrong (references non-existent column 'name')
        initial_sql = "SELECT name FROM users;"
        # Repair attempt produces valid query
        repaired_sql = "SELECT full_name FROM users;"

        call_count = 0

        def mocked_generate(msgs):
            nonlocal call_count
            call_count += 1
            return repaired_sql

        res = corrector.run(
            db_path=str(db_path),
            initial_sql=initial_sql,
            generate_fn=mocked_generate,
            base_prompt_messages=[{"role": "user", "content": "Get user names"}],
        )

        # Assert final_sql is the repaired SQL, NOT initial_sql
        assert res.final_sql == repaired_sql
        assert res.allowed is True
        assert res.exec_res.success is True
        assert len(res.exec_res.rows) == 2


def test_voting_scored_sql_is_voted_winner():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.sqlite"
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("CREATE TABLE items (id INT, category TEXT);")
        cur.execute("INSERT INTO items VALUES (1, 'A'), (2, 'B'), (3, 'A');")
        conn.commit()
        conn.close()

        validator = SQLValidator()
        executor = SafeSQLExecutor()
        voter = ConsensusVoter(validator=validator, executor=executor)

        # Greedy first candidate is wrong (executes to 0 rows or syntax error)
        # 3 out of 5 candidates agree on the correct query
        candidates = [
            "SELECT count(*) FROM items WHERE category = 'Nonexistent';",  # Candidate 0 (Greedy wrong)
            "SELECT count(*) FROM items WHERE category = 'A';",  # Candidate 1 (Correct)
            "SELECT count(*) FROM items WHERE category = 'A';",  # Candidate 2 (Correct)
            "SELECT count(*) FROM items WHERE category = 'A';",  # Candidate 3 (Correct)
            "SELECT id FROM items WHERE id = 999;",  # Candidate 4 (Wrong)
        ]

        res = voter.select_best_candidate(
            db_path=str(db_path),
            candidate_sqls=candidates,
        )

        # Scored winner MUST be the agreed candidate, NOT the greedy candidate 0
        assert res.winner_sql == "SELECT count(*) FROM items WHERE category = 'A';"
        assert res.winner_exec_res.rows == [(2,)]
        assert res.consensus_score == "3/5"
