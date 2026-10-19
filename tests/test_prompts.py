"""Unit tests for prompt template parity across training and evaluation."""

from src.t2s.data.prompts import SYSTEM_PROMPT as DATA_SYS_PROMPT
from src.t2s.data.prompts import build_prompt_messages as data_build_prompts
from src.t2s.prompts import SYSTEM_PROMPT, build_prompt_messages


def test_prompt_template_parity():
    """Verify byte-identical prompt template parity across modules."""
    schema = "CREATE TABLE department (Department_ID INTEGER, Name TEXT);"
    question = "How many departments are there?"

    msgs_canonical = build_prompt_messages(schema, question)
    msgs_data = data_build_prompts(schema, question)

    assert (
        SYSTEM_PROMPT
        == DATA_SYS_PROMPT
        == "You are a text-to-SQL assistant. Return only one SQLite SELECT query. No explanations."
    )
    assert msgs_canonical == msgs_data
    assert msgs_canonical[0]["content"] == SYSTEM_PROMPT
    assert "### SQLite Schema:\nCREATE TABLE department" in msgs_canonical[1]["content"]
    assert "### Question:\nHow many departments are there?" in msgs_canonical[1]["content"]


def test_few_shot_prompt_formatting():
    """Verify few-shot formatting in canonical prompt builder."""
    schema = "CREATE TABLE test (id INT);"
    question = "Count rows"
    few_shots = [
        {
            "schema_ddl": "CREATE TABLE example (id INT);",
            "question": "Show all",
            "query": "SELECT * FROM example;",
        }
    ]

    msgs = build_prompt_messages(schema, question, few_shot_examples=few_shots)
    assert len(msgs) == 4
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert msgs[2]["role"] == "assistant"
    assert msgs[2]["content"] == "SELECT * FROM example;"
    assert msgs[3]["role"] == "user"
