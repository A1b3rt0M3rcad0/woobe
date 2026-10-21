from __future__ import annotations

from modules.agent.application.interfaces.llm_factory import LLMFactory
from modules.agent.infra.llm.langchain_factory import create_chat_model
from modules.agent.infra.llm.providers import LegacyChatProviderRegistry


class LangchainLLMFactory(LLMFactory):

    def __init__(
        self,
        provider_registry: LegacyChatProviderRegistry | None = None,
    ) -> None:
        self._provider_registry = provider_registry

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
        max_retries: int | None = None,
    ):
        return create_chat_model(
            provider=provider,
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            response_format=response_format,
            max_retries=max_retries,
            registry=self._provider_registry,
        )

    def supports_vision_input(self, provider: str) -> bool:
        from modules.agent.infra.llm.providers import build_legacy_chat_provider_registry

        registry = self._provider_registry or build_legacy_chat_provider_registry()
        try:
            return registry.supports_vision_input(provider)
        except ValueError:
            return False

    def format_vision_input(self, provider: str, *, content_type: str, content: bytes) -> dict:
        from modules.agent.infra.llm.providers import build_legacy_chat_provider_registry

        registry = self._provider_registry or build_legacy_chat_provider_registry()
        return registry.format_vision_input(provider, content_type=content_type, content=content)
