"""Test prompt formatting and determinism."""

from src.t2s.data.prompts import (
    SYSTEM_PROMPT,
    build_prompt_completion_entry,
    build_prompt_messages,
)


def test_build_prompt_messages_determinism() -> None:
    schema_ddl = "CREATE TABLE test (id INT);"
    question = "How many items are there?"

    msgs1 = build_prompt_messages(schema_ddl, question)
    msgs2 = build_prompt_messages(schema_ddl, question)

    assert msgs1 == msgs2
    assert msgs1[0]["role"] == "system"
    assert msgs1[0]["content"] == SYSTEM_PROMPT
    assert msgs1[1]["role"] == "user"
    assert "CREATE TABLE test" in msgs1[1]["content"]
    assert "How many items are there?" in msgs1[1]["content"]


def test_build_prompt_completion_entry() -> None:
    entry = build_prompt_completion_entry(
        schema_ddl="CREATE TABLE test (id INT);",
        question="How many items?",
        gold_sql="SELECT COUNT(*) FROM test;",
        db_id="test_db",
    )

    assert entry["db_id"] == "test_db"
    assert entry["gold_sql"] == "SELECT COUNT(*) FROM test;"
    assert entry["completion"][0]["content"] == "SELECT COUNT(*) FROM test;"
