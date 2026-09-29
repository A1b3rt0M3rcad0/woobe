from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from modules.agent.application.interfaces.embedding_factory import EmbeddingClient
from modules.agent.application.model_runtime import (
    ModelInput,
    ModelOutput,
    ModelRequest,
    ModelResult,
    ModelRuntime,
    ModelToolCall,
    ModelUsage,
)
from modules.agent.domain.model_spec import (
    ModelModalities,
    ModelOperations,
    ModelSpec,
)
from shared.contracts.llm_usage import normalize_llm_usage


class LangChainLanguageModelRuntime(ModelRuntime):
    """Compatibility adapter from generic ModelRequest to the current chat model."""

    def __init__(self, *, model: Any, spec: ModelSpec) -> None:
        self._model = model
        self._spec = spec

    @property
    def spec(self) -> ModelSpec:
        return self._spec

    async def invoke(self, request: ModelRequest) -> ModelResult:
        if request.operation != ModelOperations.LANGUAGE_GENERATE:
            raise ValueError(
                f"LangChain language runtime cannot execute {request.operation}"
            )

        messages = None
        if request.context is not None:
            raw_messages = request.context.get("messages")
            if isinstance(raw_messages, list):
                messages = list(raw_messages)
        if messages is None:
            texts = [
                str(item.value)
                for item in request.inputs
                if item.modality == ModelModalities.TEXT
            ]
            if not texts:
                raise ValueError("Language generation requires text input")
            messages = [HumanMessage(content="\n".join(texts))]

        model = self._model
        if request.tools:
            bind_tools = getattr(model, "bind_tools", None)
            if not callable(bind_tools):
                raise ValueError(
                    "Model runtime does not support Tool binding"
                )
            model = bind_tools(list(request.tools), tool_choice="auto")

        result = await model.ainvoke(messages)
        usage = normalize_llm_usage(result)
        tool_calls = tuple(
            ModelToolCall(
                id=(
                    str(call.get("id"))
                    if call.get("id") is not None
                    else None
                ),
                name=str(call.get("name") or ""),
                arguments=(
                    dict(call.get("args") or {})
                    if isinstance(call.get("args"), dict)
                    else {}
                ),
            )
            for call in (getattr(result, "tool_calls", None) or [])
            if isinstance(call, dict) and call.get("name")
        )
        content = getattr(result, "content", None)
        outputs = (
            (
                ModelOutput(
                    modality=ModelModalities.TEXT,
                    value=content,
                ),
            )
            if content not in (None, "")
            else ()
        )
        response_metadata = getattr(result, "response_metadata", None)
        response_metadata = (
            dict(response_metadata)
            if isinstance(response_metadata, dict)
            else {}
        )
        return ModelResult(
            outputs=outputs,
            tool_calls=tool_calls,
            finish_reason=response_metadata.get("finish_reason"),
            usage=ModelUsage(
                metrics={
                    key: value
                    for key, value in usage.items()
                    if key != "cost_usd"
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                },
                cost_usd=usage.get("cost_usd"),
            ),
            metadata={
                "provider_response_metadata": response_metadata,
            },
        )


class LegacyEmbeddingModelRuntime(ModelRuntime):
    """Generic embedding runtime backed by the existing EmbeddingClient contract."""

    def __init__(
        self,
        *,
        client: EmbeddingClient,
        spec: ModelSpec,
    ) -> None:
        self._client = client
        self._spec = spec

    @property
    def spec(self) -> ModelSpec:
        return self._spec

    async def invoke(self, request: ModelRequest) -> ModelResult:
        if request.operation != ModelOperations.EMBEDDING_CREATE:
            raise ValueError(
                f"Embedding runtime cannot execute {request.operation}"
            )
        texts = [
            str(item.value)
            for item in request.inputs
            if item.modality == ModelModalities.TEXT
        ]
        if len(texts) != len(request.inputs) or not texts:
            raise ValueError("Embedding runtime accepts text inputs only")

        vectors = await self._client.aembed_documents(texts)
        if len(vectors) != len(texts):
            raise RuntimeError(
                "Embedding provider returned a different result count"
            )
        return ModelResult(
            outputs=tuple(
                ModelOutput(
                    modality=ModelModalities.EMBEDDING,
                    value=vector,
                    metadata={"input_index": index},
                )
                for index, vector in enumerate(vectors)
            )
        )


__all__ = [
    "LangChainLanguageModelRuntime",
    "LegacyEmbeddingModelRuntime",
]
