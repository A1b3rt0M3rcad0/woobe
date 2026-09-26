from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.interfaces.execution import (
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.capabilities.model_invocation import (
    ModelInvocationCapability,
)
from modules.agent.infra.execution.runtime_streaming import runtime_streaming_enabled


async def repair_json_if_needed(
    *,
    execution: InstrumentedExecution,
    call_index: int,
    llm_factory: Any,
    provider: str,
    model_name: str,
    api_key: str,
    base_url: str | None,
    max_tokens: int,
    schema: dict,
    clean_json_answer,
    pricing_snapshot: dict[str, Any] | None = None,
    context_capability: ContextAssemblyCapability,
) -> InstrumentedExecution:
    result = execution.result
    answer = result.content if hasattr(result, "content") else str(result)
    try:
        json.loads(clean_json_answer(answer))
        return execution
    except Exception:
        pass

    schema_json = json.dumps(schema, indent=2)
    repair_model = llm_factory.create_chat_model(
        provider=provider,
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.0,
        max_tokens=max_tokens,
        streaming=runtime_streaming_enabled(),
        response_format={"type": "json_object"},
    )
    repair_messages = [
        SystemMessage(
            content=(
                "Repair the answer into valid JSON matching the schema. "
                "Return JSON only.\n"
                f"<schema>\n{schema_json}\n</schema>"
            )
        ),
        HumanMessage(content=answer),
    ]
    try:
        repair_context = context_capability.assemble(
            messages=repair_messages,
            phase="json_repair",
            tool_selection_mode="none",
            call_index=call_index + 1,
        )
        repair_capability = ModelInvocationCapability(
            model=repair_model,
            provider=provider,
            model_name=model_name,
            pricing_snapshot=pricing_snapshot,
        )
        result, call = await repair_capability.invoke(
            messages=list(repair_context.messages),
            phase="json_repair",
            call_index=call_index + 1,
            invocation_id=repair_context.invocation_id,
            context_snapshot=repair_context.snapshot,
            context_prepared=True,
        )
    except InstrumentedExecutionError as exc:
        raise InstrumentedExecutionError(
            str(exc),
            llm_calls=execution.llm_calls + exc.llm_calls,
            tool_calls=execution.tool_calls,
            knowledge_calls=list(execution.knowledge_calls),
            sources=list(execution.sources),
            timeline=execution.timeline + exc.timeline,
            tool_wall_latency_ms=execution.tool_wall_latency_ms,
            tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
        ) from exc

    execution.result = result
    execution.llm_calls.append(call)
    execution.timeline.append(
        {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
    )
    return execution
