from __future__ import annotations

from abc import ABC, abstractmethod


class LLMFactory(ABC):

    @abstractmethod
    def create_chat_model(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        streaming: bool = False,
        response_format: dict | None = None,
    ):
        ...
