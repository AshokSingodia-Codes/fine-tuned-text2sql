"""Canonical Prompt Builder and Templates for Text-to-SQL tasks.

Ensures strict prompt template parity across training, evaluation, and serving.
"""

from typing import Any, Dict, List, Optional

SYSTEM_PROMPT = (
    "You are a text-to-SQL assistant. Return only one SQLite SELECT query. No explanations."
)


def build_prompt_messages(
    schema_ddl: str,
    question: str,
    few_shot_examples: Optional[List[Dict[str, str]]] = None,
) -> List[Dict[str, str]]:
    """Build standardized prompt messages for LLM completion.

    Args:
        schema_ddl: SQLite schema DDL string.
        question: User natural language question.
        few_shot_examples: Optional list of few-shot example dicts.

    Returns:
        List of message dicts formatted for chat completion.
    """
    messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    if few_shot_examples:
        for example in few_shot_examples:
            user_content = (
                f"### SQLite Schema:\n{example['schema_ddl']}\n\n"
                f"### Question:\n{example['question']}"
            )
            messages.append({"role": "user", "content": user_content})
            messages.append({"role": "assistant", "content": example["query"]})

    user_content = f"### SQLite Schema:\n{schema_ddl}\n\n### Question:\n{question}"
    messages.append({"role": "user", "content": user_content})
    return messages


def build_prompt_completion_entry(
    schema_ddl: str,
    question: str,
    gold_sql: str,
    db_id: str,
    few_shot_examples: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Build prompt-completion dataset entry for training."""
    prompt_msgs = build_prompt_messages(schema_ddl, question, few_shot_examples)
    completion_msgs = [{"role": "assistant", "content": gold_sql}]

    return {
        "db_id": db_id,
        "question": question,
        "gold_sql": gold_sql,
        "prompt": prompt_msgs,
        "completion": completion_msgs,
    }
