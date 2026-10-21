"""One owned invocation through the existing semantic model/provider ports."""
import asyncio
import inspect

from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.interfaces.model_runtime import ModelInput, ModelRequest
from modules.agent.domain.model_spec import ModelModalities, ModelOperations, ModelSpec
from modules.agent.infra.adapters.configuration_transport import BoundConfigurationCredential
from modules.agent.infra.adapters.langchain_llm_factory import LangchainLLMFactory
from modules.agent.infra.models.legacy_model_runtime import LangChainLanguageModelRuntime


async def _close_model(model):
    seen, failed = set(), False
    for name in ('http_async_client', 'http_client', 'root_async_client', 'root_client'):
        client = getattr(model, name, None)
        if client is None or id(client) in seen:
            continue
        seen.add(id(client))
        close = getattr(client, 'aclose', None) or getattr(client, 'close', None)
        if close is not None:
            try:
                result = close()
                if inspect.isawaitable(result):
                    await result
            except Exception:
                failed = True
    if failed:
        raise RuntimeError('Model operation client cleanup failed')


async def _drain_cleanup(model):
    cleanup, cancellation = asyncio.create_task(_close_model(model)), None
    while True:
        try:
            await asyncio.shield(cleanup)
            break
        except asyncio.CancelledError as error:
            if cleanup.cancelled():
                raise
            cancellation = error
    if cancellation is not None:
        raise cancellation


class OperationModelRuntime:
    def __init__(self, *, model_factory=None):
        self._models = model_factory or LangchainLLMFactory()

    async def invoke(self, *, definition, credential_resolver, system_instruction,
                     input_json, max_output_tokens, timeout_seconds):
        if not 1 <= max_output_tokens <= 32_768 or not 1 <= timeout_seconds <= 60:
            raise ValueError('Standalone model operation exceeds its token/deadline bounds')
        if len(system_instruction.encode()) + len(input_json.encode()) > 32_768:
            raise ValueError('Standalone model operation exceeds its input byte bound')
        spec = ModelSpec.from_dict(definition['model_spec'])
        model = self._models.create_chat_model(provider=definition['provider'], model=definition['model'],
            api_key=BoundConfigurationCredential(credential_resolver), base_url=definition['destination'],
            temperature=0, max_tokens=max_output_tokens, streaming=False,
            response_format={'type': 'json_object'}, max_retries=0)
        try:
            runtime = LangChainLanguageModelRuntime(model=model, spec=spec)
            request = ModelRequest(operation=ModelOperations.LANGUAGE_GENERATE,
                inputs=(ModelInput(ModelModalities.TEXT, input_json),), context={'messages': [
                    SystemMessage(content=system_instruction), HumanMessage(content=input_json)]})
            async with asyncio.timeout(timeout_seconds):
                return await runtime.invoke(request)
        finally:
            await _drain_cleanup(model)
