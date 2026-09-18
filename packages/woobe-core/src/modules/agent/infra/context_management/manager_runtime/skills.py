from __future__ import annotations

from typing import Any

from modules.agent.application.context_assembly import (
    ContextBudgetExceeded,
    estimate_input_units,
)
from modules.agent.application.interfaces.context_assembler import ContextAssemblyRequest
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.application.skill_runtime import skill_contribution_content
from modules.agent.domain.context import ContextPriority, ContextSourceType


def _message_class(messages: list[Any], class_name: str):
    for message in messages:
        if message.__class__.__name__ == class_name:
            return message.__class__
    raise ContextBudgetExceeded(
        f"Active Skills require a {class_name} message template"
    )


def materialize_active_skills(
    *,
    request: ContextAssemblyRequest,
    messages: list[Any],
    policy: ContextPolicyV1,
) -> tuple[list[Any], tuple[str, ...]]:
    """Materialize Run-local Skills for one invocation without owning Manager policy."""

    candidates = getattr(request.runtime_context, "skill_context", None) or []
    if not candidates:
        return messages, ()

    skills_policy = policy.skills
    if (
        skills_policy is None
        or ContextSourceType.SKILL not in policy.allowed_sources
    ):
        raise ContextBudgetExceeded(
            "Active Skills require an allowed SKILL source and a Skills budget"
        )

    system_message = _message_class(messages, "SystemMessage")
    human_message = _message_class(messages, "HumanMessage")
    materialized = []
    seen = set()

    for item in candidates:
        identity = (item["source_ref"], item.get("resource_hash"))
        if identity in seen:
            continue
        seen.add(identity)
        metadata = {
            key: value for key, value in item.items() if key != "content"
        }
        metadata["source_type"] = "SKILL"
        content = skill_contribution_content(item)
        message_type = (
            human_message if item["component"] == "resource" else system_message
        )
        materialized.append(
            message_type(
                content=content,
                additional_kwargs={"woobe_context": metadata},
            )
        )

    units = sum(estimate_input_units(message.content) for message in materialized)
    if units > skills_policy.max_units:
        raise ContextBudgetExceeded(
            f"Active Skills exceed the Skills context budget: {units} > {skills_policy.max_units}"
        )

    insertion = 0
    while (
        insertion < len(messages)
        and messages[insertion].__class__.__name__ == "SystemMessage"
    ):
        insertion += 1
    result = list(messages)
    result[insertion:insertion] = materialized

    policy.source_priorities[ContextSourceType.SKILL] = ContextPriority.MANDATORY
    policy.deduplication.sources = [
        source
        for source in policy.deduplication.sources
        if source != ContextSourceType.SKILL
    ]

    versions = tuple(
        sorted(
            {
                item["skill_version_id"]
                for item in candidates
                if item.get("skill_version_id")
            }
        )
    )
    return result, versions
