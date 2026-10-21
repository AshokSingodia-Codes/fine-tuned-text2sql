"""Prompt builder for Text-to-SQL tasks (delegates to canonical src.t2s.prompts)."""

from src.t2s.prompts import (
    SYSTEM_PROMPT,
    build_prompt_completion_entry,
    build_prompt_messages,
)

__all__ = ["SYSTEM_PROMPT", "build_prompt_messages", "build_prompt_completion_entry"]

