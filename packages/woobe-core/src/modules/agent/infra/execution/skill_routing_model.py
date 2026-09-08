from __future__ import annotations

import json
from typing import Any, Callable
from uuid import uuid4

from langchain_core.messages import AIMessage


def _message_content(result: Any) -> str:
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        text = item.get("text") or item.get("content")
        if isinstance(text, str):
            parts.append(text)
    return "\n".join(part for part in parts if part)


def _routing_arguments(
    result: Any,
    *,
    clean_json_answer: Callable[[str], str],
) -> dict[str, Any]:
    content = _message_content(result).strip()
    if not content:
        raise ValueError(
            "Skill applicability routing returned neither a Tool call nor a JSON decision"
        )

    try:
        decision = json.loads(clean_json_answer(content))
    except Exception as exc:
        raise ValueError(
            "Skill applicability routing returned neither a Tool call nor a valid JSON decision"
        ) from exc

    if not isinstance(decision, dict):
        raise ValueError("Skill applicability routing JSON decision must be an object")

    action = decision.get("action")
    if action not in {"activate", "search", "none"}:
        raise ValueError(
            "Skill applicability routing action must be activate, search, or none"
        )

    arguments: dict[str, Any] = {"action": action}
    if action == "activate":
        skill_version_id = decision.get("skill_version_id")
        if not isinstance(skill_version_id, str) or not skill_version_id.strip():
            raise ValueError(
                "Skill applicability routing activation requires skill_version_id"
            )
        arguments["skill_version_id"] = skill_version_id
    elif action == "search":
        query = decision.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Skill applicability routing search requires query")
        arguments["query"] = query
        offset = decision.get("offset", 0)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError(
                "Skill applicability routing search offset must be a nonnegative integer"
            )
        arguments["offset"] = offset

    return arguments


def _with_runtime_tool_call(result: Any, arguments: dict[str, Any]) -> Any:
    tool_call = {
        "name": "skills_resolve",
        "args": arguments,
        "id": f"skill-routing-{uuid4()}",
        "type": "tool_call",
    }
    model_copy = getattr(result, "model_copy", None)
    if callable(model_copy):
        return model_copy(update={"content": "", "tool_calls": [tool_call]})
    return AIMessage(content="", tool_calls=[tool_call])


class SkillRoutingModelAdapter:
    """Normalize Skill routing into the runtime-owned ``skills_resolve`` operation.

    Providers that emit the bound Tool call pass through unchanged. Providers/models that
    choose to answer with text instead can return the routing decision as strict JSON; the
    adapter converts that private routing response into the same runtime Tool call. This
    keeps Skill applicability mandatory without requiring a provider-specific forced
    ``tool_choice``.
    """

    def __init__(
        self,
        model: Any,
        *,
        clean_json_answer: Callable[[str], str],
    ) -> None:
        self._model = model
        self._clean_json_answer = clean_json_answer

    def _normalize(self, result: Any) -> Any:
        if getattr(result, "tool_calls", None):
            return result
        arguments = _routing_arguments(
            result,
            clean_json_answer=self._clean_json_answer,
        )
        return _with_runtime_tool_call(result, arguments)

    async def ainvoke(self, messages: list, **kwargs: Any) -> Any:
        result = await self._model.ainvoke(messages, **kwargs)
        return self._normalize(result)

    async def astream(self, messages: list, **kwargs: Any):
        # Skill routing is private control-plane work. Resolve one complete provider result
        # and normalize it before yielding anything to the runtime stream so routing JSON
        # can never leak as user-visible assistant output.
        yield await self.ainvoke(messages, **kwargs)
