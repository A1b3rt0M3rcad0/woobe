from __future__ import annotations

import json
import logging
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from modules.agent.application.dtos.runtime_dtos import ToolCallInfo
from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase, _has_tool_calls
from modules.agent.domain.entities import Agent

logger = logging.getLogger(__name__)


class StructuredOutputAskAgentUseCase(AskAgentUseCase):
    async def _execute_llm(
        self,
        agent: Agent,
        api_key: str,
        base_url: str | None,
        response_format: dict,
        json_enabled: bool,
        has_tools: bool,
        agent_tools: list[dict],
        tool_name_to_id: dict[str, str],
        messages: list,
    ) -> tuple[Any, list[ToolCallInfo], bool, int | None]:
        provider = agent.provider.value if hasattr(agent.provider, "value") else agent.provider
        chat_model = self._llm_factory.create_chat_model(
            provider=provider,
            model=agent.model,
            api_key=api_key,
            base_url=base_url,
            temperature=agent.temperature or 0.2,
            max_tokens=agent.max_output_tokens or 1000,
            response_format={"type": "json_object"} if json_enabled and not has_tools else None,
        )

        if has_tools:
            chat_model = chat_model.bind_tools(agent_tools, tool_choice="auto")

        tool_calls_recorded: list[ToolCallInfo] = []
        tool_was_called = False
        json_format_latency_ms: int | None = None
        tool_call_rounds = 0
        result = await chat_model.ainvoke(messages)

        while _has_tool_calls(result) and tool_call_rounds < 5:
            tool_was_called = True
            messages.append(result)
            for tool_call in getattr(result, "tool_calls", None) or []:
                tool_start = time.monotonic()
                resolved_tool_id = tool_name_to_id.get(tool_call["name"], tool_call["name"])
                tool_output = await self._execute_single_tool(tool_call, resolved_tool_id)
                tool_duration = round((time.monotonic() - tool_start) * 1000)
                tool_success = tool_output.get("success", False) if isinstance(tool_output, dict) else True
                tool_error = tool_output.get("error") if isinstance(tool_output, dict) else None
                tool_calls_recorded.append(
                    ToolCallInfo(
                        tool_call_id=tool_call["id"],
                        tool_name=tool_call["name"],
                        input=tool_call.get("args"),
                        output=tool_output,
                        duration_ms=tool_duration,
                        success=tool_success,
                        error=tool_error,
                    )
                )
                messages.append(
                    ToolMessage(
                        content=json.dumps(tool_output) if isinstance(tool_output, dict) else str(tool_output),
                        tool_call_id=tool_call["id"],
                    )
                )

            tool_call_rounds += 1
            try:
                result = await chat_model.ainvoke(messages)
            except Exception as exc:
                logger.warning("Tool call follow-up LLM invoke failed: %s", exc)
                break

        if json_enabled and tool_was_called:
            try:
                answer_text = result.content if hasattr(result, "content") else str(result)
                schema_json = json.dumps(response_format.get("schema", {}), indent=2)
                json_model = self._llm_factory.create_chat_model(
                    provider=provider,
                    model=agent.model,
                    api_key=api_key,
                    base_url=base_url,
                    temperature=0.0,
                    max_tokens=agent.max_output_tokens or 1000,
                    response_format={"type": "json_object"},
                )
                json_start = time.monotonic()
                json_result = await json_model.ainvoke(
                    [
                        SystemMessage(
                            content=(
                                "Return only valid JSON matching the provided schema. "
                                "Do not include markdown or explanatory text.\n"
                                f"<schema>\n{schema_json}\n</schema>"
                            )
                        ),
                        HumanMessage(content=f"Convert this answer to valid JSON:\n\n{answer_text}"),
                    ]
                )
                json_format_latency_ms = round((time.monotonic() - json_start) * 1000)
                result = json_result
            except Exception as exc:
                logger.warning("JSON formatting phase failed: %s", exc)

        return result, tool_calls_recorded, tool_was_called, json_format_latency_ms
