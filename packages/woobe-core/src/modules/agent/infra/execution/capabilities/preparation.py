from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Coroutine

from modules.agent.application.interfaces.context_manager import ContextManager
from modules.agent.application.interfaces.context_policy import resolve_context_policy
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.application.interfaces.knowledge import KnowledgeStrategy
from modules.agent.application.interfaces.model_spec_compatibility import LegacyModelSpecResolver
from modules.agent.domain.model_spec import ModelSpec
from modules.agent.infra.execution.execution_instrumentation import (
    resolve_effective_output_tokens,
)
from modules.agent.infra.execution.runtime_streaming import (
    current_runtime_stream,
    runtime_streaming_enabled,
)

_skill_snapshots_resolver: Callable[[object, Any], list[dict[str, Any]]] | None = None
_skill_runtime_factory: Callable[[list[dict[str, Any]], Any, set[str]], Any] | None = None


@dataclass(frozen=True, slots=True)
class PreparedFallbackModel:
    model_spec: ModelSpec
    model: Any
    provider: str
    model_name: str
    pricing_snapshot: dict[str, Any] | None
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PreparedExecution:
    """Resolved strategy-facing bindings for one Agent execution.

    The Strategy consumes this prepared view instead of repeatedly reaching back into
    Runtime plumbing. Agent Run lifecycle, persistence and terminal Run/Trace finalization
    remain owned by the outer runtime.
    """

    model_spec: ModelSpec
    model: Any
    final_model: Any | None
    final_model_factory: Callable[[], Any] | None
    structured_repair_model_factory: Callable[[], Any] | None
    fallback_model_factory: Callable[[], PreparedFallbackModel] | None
    execute_single_tool: Callable[[dict, str], Coroutine[Any, Any, dict]]
    messages: list
    tool_name_to_id: dict[str, str]
    provider: str
    model_name: str
    final_json_instruction: str | None
    pricing_snapshot: dict[str, Any] | None
    effective_output_tokens: int
    json_enabled: bool
    response_schema: dict[str, Any]
    llm_factory: Any
    api_key: str
    base_url: str | None
    clean_json_answer: Callable[..., Any]
    context_manager: ContextManager | None
    tool_definitions: list[dict]
    knowledge_retrieve: Callable[[str], Awaitable[Any]] | None
    knowledge_strategy: KnowledgeStrategy | None
    knowledge_runtime_config: dict[str, Any]

    @property
    def context_assembler(self) -> ContextManager | None:
        """Legacy compatibility view; internal code uses context_manager."""
        return self.context_manager


def configure_skill_runtime(
    snapshots_resolver: Callable[[object, Any], list[dict[str, Any]]],
    runtime_factory: Callable[[list[dict[str, Any]], Any, set[str]], Any],
) -> None:
    """Bind concrete Skill application services from the composition root."""
    global _skill_snapshots_resolver, _skill_runtime_factory
    _skill_snapshots_resolver = snapshots_resolver
    _skill_runtime_factory = runtime_factory


def _primary_model_spec(
    request: ExecutionStrategyRequest,
    *,
    provider: str,
) -> ModelSpec:
    settings = request.agent.settings or {}
    persisted = settings.get("model_spec")
    if isinstance(persisted, dict):
        return ModelSpec.from_dict(persisted)

    compatibility_model = SimpleNamespace(
        id=getattr(request.agent, "provider_model_id", None),
        provider_credential_id=getattr(
            request.agent,
            "provider_credential_id",
            None,
        ),
        name=request.agent.model,
        model=request.agent.model,
        metadata={},
    )
    return LegacyModelSpecResolver().resolve(
        compatibility_model,
        provider=provider,
    )


def _fallback_model_spec(
    request: ExecutionStrategyRequest,
    *,
    provider: str,
    model_name: str,
) -> ModelSpec:
    settings = request.agent.settings or {}
    persisted = settings.get("fallback_model_spec")
    if isinstance(persisted, dict):
        return ModelSpec.from_dict(persisted)

    compatibility_model = SimpleNamespace(
        id=getattr(request.agent, "fallback_provider_model_id", None),
        provider_credential_id=getattr(
            request.agent,
            "fallback_credential_id",
            None,
        ),
        name=model_name,
        model=model_name,
        metadata={},
    )
    return LegacyModelSpecResolver().resolve(
        compatibility_model,
        provider=provider,
    )


def _primary_pricing_snapshot(request: ExecutionStrategyRequest) -> dict[str, Any] | None:
    settings = request.agent.settings or {}
    value = settings.get("model_pricing")
    return value if isinstance(value, dict) else None


def _fallback_pricing_snapshot(request: ExecutionStrategyRequest) -> dict[str, Any] | None:
    settings = request.agent.settings or {}
    value = settings.get("fallback_model_pricing")
    return value if isinstance(value, dict) else None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else None
    return None


def _bind_context_runtime(
    *,
    request: ExecutionStrategyRequest,
    pricing_snapshot: dict[str, Any] | None,
) -> None:
    context = current_execution.get()
    if context is None:
        return
    runtime_config = (request.agent.settings or {}).get("runtime_config")
    policy = resolve_context_policy(runtime_config)
    context.context_policy = policy.model_dump(mode="json")
    context.reserved_output_units = request.agent.max_output_tokens or 1000
    # Tool visibility belongs to one model invocation. Preparation resolves the
    # authorized inventory but does not make every Tool active in Context.
    context.active_tool_definitions = []
    context.model_capacity_units = _positive_int(
        (pricing_snapshot or {}).get("context_window")
    )
    context.context_selection_metadata = {
        "available_message_count": len(request.messages),
        "session_strategy": policy.session.strategy,
        "session_max_messages": policy.session.max_messages,
        "session_max_units": policy.session.max_units,
    }


@dataclass(frozen=True, slots=True)
class _PreparedTools:
    execute_single_tool: Callable[[dict, str], Coroutine[Any, Any, dict]]
    definitions: list[dict[str, Any]]
    name_to_id: dict[str, str]
    has_any: bool


@dataclass(frozen=True, slots=True)
class _PreparedOutputContract:
    schema: dict[str, Any]
    instruction: str | None
    base_response_format: dict[str, str] | None


@dataclass(frozen=True, slots=True)
class _PreparedModels:
    primary: Any
    final: Any | None
    final_factory: Callable[[], Any] | None
    repair_factory: Callable[[], Any] | None


def _prepare_tools(
    request: ExecutionStrategyRequest,
    runtime_config: Any,
) -> _PreparedTools:
    agent = request.agent
    has_skill_config = (
        isinstance(runtime_config, dict)
        and bool(runtime_config.get("skills"))
    )
    if has_skill_config:
        if _skill_snapshots_resolver is None or _skill_runtime_factory is None:
            raise RuntimeError("Skill runtime dependencies were not configured")
        snapshots = _skill_snapshots_resolver(runtime_config, agent.project_id)
    else:
        snapshots = []

    context = current_execution.get()
    if context is not None:
        context.skill_context = None

    definitions = list(request.agent_tools)
    name_to_id = dict(request.tool_name_to_id)
    has_any = request.has_tools
    execute_single_tool = request.execute_single_tool

    if not snapshots:
        return _PreparedTools(
            execute_single_tool=execute_single_tool,
            definitions=definitions,
            name_to_id=name_to_id,
            has_any=has_any,
        )

    policy = resolve_context_policy(runtime_config).skills
    if policy is None or context is None:
        raise RuntimeError("Skills require a prepared execution context and policy")

    skill_runtime = _skill_runtime_factory(snapshots, policy, set(name_to_id))
    collisions = set(name_to_id).intersection(skill_runtime.mapping)
    if collisions:
        raise ValueError(
            "Skill operation name collides with a bound Tool: "
            + ", ".join(sorted(collisions))
        )

    context.skill_context = skill_runtime.contributions()
    definitions = [*definitions, *skill_runtime.definitions]
    name_to_id = {**name_to_id, **skill_runtime.mapping}
    execute_bound_tool = execute_single_tool
    skill_execution_context = context

    async def execute_with_skills(tool_call: dict, resolved_tool_id: str) -> dict:
        name = tool_call.get("name")
        if name in skill_runtime.mapping:
            output = skill_runtime.execute(
                name,
                tool_call.get("args") or {},
                tool_call_id=str(tool_call.get("id") or ""),
            )
            skill_execution_context.skill_context = skill_runtime.contributions()
            return output
        return await execute_bound_tool(tool_call, resolved_tool_id)

    return _PreparedTools(
        execute_single_tool=execute_with_skills,
        definitions=definitions,
        name_to_id=name_to_id,
        has_any=True,
    )


def _prepare_output_contract(
    request: ExecutionStrategyRequest,
    *,
    has_tools: bool,
) -> _PreparedOutputContract:
    schema = request.response_format.get("schema", {})
    instruction = None
    if request.json_enabled and has_tools:
        schema_json = json.dumps(schema, indent=2)
        instruction = (
            "When capability calls are complete, return only valid JSON matching this "
            "schema. You may call another bound capability first when still required. "
            "Do not include markdown or explanatory text.\n"
            f"<schema>\n{schema_json}\n</schema>"
        )

    return _PreparedOutputContract(
        schema=schema,
        instruction=instruction,
        base_response_format=(
            {"type": "json_object"}
            if request.json_enabled and not has_tools
            else None
        ),
    )


def _prepare_models(
    request: ExecutionStrategyRequest,
    *,
    provider: str,
    pricing_snapshot: dict[str, Any] | None,
    effective_output_tokens: int,
    has_tools: bool,
    output: _PreparedOutputContract,
    streaming_enabled: bool,
) -> _PreparedModels:
    agent = request.agent
    primary = request.llm_factory.create_chat_model(
        provider=provider,
        model=agent.model,
        api_key=request.api_key,
        base_url=request.base_url,
        temperature=agent.temperature or 0.2,
        max_tokens=effective_output_tokens,
        streaming=streaming_enabled,
        response_format=output.base_response_format,
    )

    context = current_execution.get()
    network_execution = bool(context and context.network_execution_id)
    final = (
        primary
        if has_tools and network_execution and not request.json_enabled
        else None
    )

    final_factory: Callable[[], Any] | None = None
    if has_tools and request.json_enabled:

        def create_structured_final_model() -> Any:
            return request.llm_factory.create_chat_model(
                provider=provider,
                model=agent.model,
                api_key=request.api_key,
                base_url=request.base_url,
                temperature=agent.temperature or 0.2,
                max_tokens=effective_output_tokens,
                streaming=streaming_enabled,
                response_format={"type": "json_object"},
            )

        final_factory = create_structured_final_model

    repair_factory: Callable[[], Any] | None = None
    if request.json_enabled:

        def create_structured_repair_model() -> Any:
            return request.llm_factory.create_chat_model(
                provider=provider,
                model=agent.model,
                api_key=request.api_key,
                base_url=request.base_url,
                temperature=0.0,
                max_tokens=effective_output_tokens,
                streaming=streaming_enabled,
                response_format={"type": "json_object"},
            )

        repair_factory = create_structured_repair_model

    return _PreparedModels(
        primary=primary,
        final=final,
        final_factory=final_factory,
        repair_factory=repair_factory,
    )


def _prepare_fallback_model_factory(
    request: ExecutionStrategyRequest,
    *,
    primary_provider: str,
    streaming_enabled: bool,
) -> Callable[[], PreparedFallbackModel] | None:
    agent = request.agent
    fallback_model_name = getattr(agent, "fallback_model", None)
    fallback_credential_id = getattr(agent, "fallback_credential_id", None)
    fallback_provider_value = getattr(agent, "fallback_provider", None)
    if not (
        fallback_model_name
        and fallback_credential_id
        and fallback_provider_value
    ):
        return None

    fallback_provider = (
        fallback_provider_value.value
        if hasattr(fallback_provider_value, "value")
        else str(fallback_provider_value)
    )
    fallback_pricing = _fallback_pricing_snapshot(request)
    fallback_spec = _fallback_model_spec(
        request,
        provider=fallback_provider,
        model_name=str(fallback_model_name),
    )
    fallback_output_tokens = resolve_effective_output_tokens(
        agent.max_output_tokens,
        fallback_pricing,
    )

    def create_fallback_model() -> PreparedFallbackModel:
        execution_context = current_execution.get()
        prepared_fallback = (
            execution_context.prepared_fallback
            if execution_context is not None
            else None
        )
        prepared_fallback = (
            prepared_fallback if isinstance(prepared_fallback, dict) else {}
        )
        fallback_model = request.llm_factory.create_chat_model(
            provider=fallback_provider,
            model=fallback_model_name,
            api_key=str(prepared_fallback.get("api_key") or ""),
            base_url=prepared_fallback.get("base_url"),
            temperature=agent.temperature or 0.2,
            max_tokens=fallback_output_tokens,
            streaming=streaming_enabled,
            response_format=(
                {"type": "json_object"} if request.json_enabled else None
            ),
        )
        return PreparedFallbackModel(
            model_spec=fallback_spec,
            model=fallback_model,
            provider=fallback_provider,
            model_name=str(fallback_model_name),
            pricing_snapshot=fallback_pricing,
            metadata={
                "primary_model": agent.model,
                "primary_provider": primary_provider,
                "fallback_model": str(fallback_model_name),
                "fallback_provider": fallback_provider,
                "fallback_credential_id": str(fallback_credential_id),
                "fallback_provider_model_id": (
                    str(getattr(agent, "fallback_provider_model_id"))
                    if getattr(agent, "fallback_provider_model_id", None)
                    else None
                ),
            },
        )

    return create_fallback_model


def _initialize_runtime_state(
    request: ExecutionStrategyRequest,
    *,
    pricing_snapshot: dict[str, Any] | None,
) -> None:
    _bind_context_runtime(
        request=request,
        pricing_snapshot=pricing_snapshot,
    )
    context = current_execution.get()
    if context is None:
        return
    context.execution = InstrumentedExecution(result=None)
    stream = current_runtime_stream.get()
    if stream is not None:
        setattr(stream, "execution_context", context)


def prepare_execution(request: ExecutionStrategyRequest) -> PreparedExecution:
    """Compose execution bindings without implementing the execution algorithm."""

    agent = request.agent
    provider = (
        agent.provider.value
        if hasattr(agent.provider, "value")
        else str(agent.provider)
    )
    model_spec = _primary_model_spec(
        request,
        provider=provider,
    )
    raw_runtime_config = (agent.settings or {}).get("runtime_config")
    runtime_config = (
        dict(raw_runtime_config)
        if isinstance(raw_runtime_config, dict)
        else {}
    )
    tools = _prepare_tools(request, runtime_config)
    pricing_snapshot = _primary_pricing_snapshot(request)
    effective_output_tokens = resolve_effective_output_tokens(
        agent.max_output_tokens,
        pricing_snapshot,
    )
    _initialize_runtime_state(
        request,
        pricing_snapshot=pricing_snapshot,
    )

    streaming_enabled = runtime_streaming_enabled()
    output = _prepare_output_contract(
        request,
        has_tools=tools.has_any,
    )
    models = _prepare_models(
        request,
        provider=provider,
        pricing_snapshot=pricing_snapshot,
        effective_output_tokens=effective_output_tokens,
        has_tools=tools.has_any,
        output=output,
        streaming_enabled=streaming_enabled,
    )
    fallback_model_factory = _prepare_fallback_model_factory(
        request,
        primary_provider=provider,
        streaming_enabled=streaming_enabled,
    )

    return PreparedExecution(
        model_spec=model_spec,
        model=models.primary,
        final_model=models.final,
        final_model_factory=models.final_factory,
        structured_repair_model_factory=models.repair_factory,
        fallback_model_factory=fallback_model_factory,
        execute_single_tool=tools.execute_single_tool,
        messages=list(request.messages),
        tool_name_to_id=tools.name_to_id,
        provider=provider,
        model_name=agent.model,
        final_json_instruction=output.instruction,
        pricing_snapshot=pricing_snapshot,
        effective_output_tokens=effective_output_tokens,
        json_enabled=request.json_enabled,
        response_schema=output.schema,
        llm_factory=request.llm_factory,
        api_key=request.api_key,
        base_url=request.base_url,
        clean_json_answer=request.clean_json_answer,
        context_manager=request.context_manager,
        tool_definitions=tools.definitions,
        knowledge_retrieve=request.knowledge_retrieve,
        knowledge_strategy=request.knowledge_strategy,
        knowledge_runtime_config=runtime_config,
    )
