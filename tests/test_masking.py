"""Test prompt-completion loss masking (-100 for prompt, token ids for completion)."""

from typing import List, Tuple


def build_masked_labels(
    prompt_tokens: List[int], completion_tokens: List[int]
) -> Tuple[List[int], List[int]]:
    input_ids = prompt_tokens + completion_tokens
    # Mask prompt tokens with -100 so loss is computed ONLY on completion tokens
    labels = [-100] * len(prompt_tokens) + completion_tokens
    return input_ids, labels


def test_token_masking_logic() -> None:
    prompt_toks = [101, 205, 309, 412]
    completion_toks = [500, 600, 700]

    input_ids, labels = build_masked_labels(prompt_toks, completion_toks)

    assert len(input_ids) == len(labels) == 7
    # Prompt positions must be -100
    assert labels[:4] == [-100, -100, -100, -100]
    # Completion positions must match completion_toks
    assert labels[4:] == [500, 600, 700]
    assert input_ids[4:] == labels[4:]


def test_token_masking_with_tokenizer() -> None:
    try:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            "Qwen/Qwen2.5-Coder-3B-Instruct", trust_remote_code=True
        )
    except Exception:
        return

    prompt_text = "System: You are a text-to-SQL bot.\nUser: Select all users."
    completion_text = "SELECT * FROM users;"

    p_ids = tokenizer.encode(prompt_text, add_special_tokens=False)
    c_ids = tokenizer.encode(completion_text, add_special_tokens=False)

    input_ids, labels = build_masked_labels(p_ids, c_ids)

    assert labels[: len(p_ids)] == [-100] * len(p_ids)
    assert labels[len(p_ids) :] == c_ids
