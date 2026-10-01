"""Generation backends interface and implementations."""

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import requests


class BaseBackend(ABC):
    @abstractmethod
    def generate(self, prompts: List[List[Dict[str, str]]]) -> List[Dict[str, Any]]:
        """Generate completions for a list of prompt message lists.

        Returns list of dicts: {'text': str, 'latency_ms': float, 'tokens': int}
        """
        pass


class MockBackend(BaseBackend):
    def __init__(self, responses: Optional[List[str]] = None) -> None:
        self.responses = responses

    def generate(self, prompts: List[List[Dict[str, str]]]) -> List[Dict[str, Any]]:
        results = []
        for i, _ in enumerate(prompts):
            start = time.perf_counter()
            if self.responses and i < len(self.responses):
                text = self.responses[i]
            else:
                text = "SELECT 1;"
            latency = (time.perf_counter() - start) * 1000.0
            results.append({"text": text, "latency_ms": latency, "tokens": len(text.split())})
        return results


class TransformersBackend(BaseBackend):
    def __init__(
        self,
        model_name: str,
        max_new_tokens: int = 256,
        torch_dtype: str = "float16",
        device_map: str = "auto",
    ) -> None:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch_dtype,
            device_map=device_map,
            trust_remote_code=True,
        )
        self.max_new_tokens = max_new_tokens

    def generate(self, prompts: List[List[Dict[str, str]]]) -> List[Dict[str, Any]]:
        results = []
        for prompt_msgs in prompts:
            start = time.perf_counter()
            prompt_text = self.tokenizer.apply_chat_template(
                prompt_msgs, tokenize=False, add_generation_prompt=True
            )
            inputs = self.tokenizer(prompt_text, return_tensors="pt").to(self.model.device)
            prompt_len = inputs["input_ids"].shape[1]

            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
                temperature=0.0,
            )
            generated_ids = outputs[0][prompt_len:]
            text = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
            latency = (time.perf_counter() - start) * 1000.0
            results.append({"text": text, "latency_ms": latency, "tokens": len(generated_ids)})
        return results


class OpenAICompatBackend(BaseBackend):
    def __init__(
        self,
        api_base: str = "http://localhost:8000/v1",
        api_key: str = "token",
        model: str = "default",
        max_tokens: int = 256,
    ) -> None:
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens

    def generate(self, prompts: List[List[Dict[str, str]]]) -> List[Dict[str, Any]]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        results = []
        for prompt_msgs in prompts:
            payload = {
                "model": self.model,
                "messages": prompt_msgs,
                "temperature": 0.0,
                "max_tokens": self.max_tokens,
            }
            start = time.perf_counter()
            response = requests.post(
                f"{self.api_base}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            latency = (time.perf_counter() - start) * 1000.0
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            tokens = usage.get("completion_tokens", len(text.split()))
            results.append({"text": text, "latency_ms": latency, "tokens": tokens})
        return results


def get_backend(backend_type: str, **kwargs: Any) -> BaseBackend:
    if backend_type == "mock":
        return MockBackend(responses=kwargs.get("responses"))
    elif backend_type == "transformers":
        return TransformersBackend(
            model_name=kwargs.get("model_name", "Qwen/Qwen2.5-Coder-3B-Instruct"),
            max_new_tokens=kwargs.get("max_new_tokens", 256),
        )
    elif backend_type == "openai_compat":
        return OpenAICompatBackend(
            api_base=kwargs.get("api_base", "http://localhost:8000/v1"),
            model=kwargs.get("model", "default"),
        )
    else:
        raise ValueError(f"Unsupported backend_type: {backend_type}")
