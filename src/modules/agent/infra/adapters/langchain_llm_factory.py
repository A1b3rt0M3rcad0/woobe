from __future__ import annotations

import importlib

from modules.agent.domain.ports.llm_factory import LLMFactory


class LangchainLLMFactory(LLMFactory):

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
        extra_body: dict | None = None,
    ):
        langchain_mod = importlib.import_module("modules.agent.infra.llm.langchain_factory")
        return langchain_mod.create_chat_model(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            response_format=response_format,
            extra_body=extra_body,
        )
