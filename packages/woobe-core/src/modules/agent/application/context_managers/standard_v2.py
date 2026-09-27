from __future__ import annotations

from dataclasses import replace
from typing import Any

from modules.agent.application.context_assembly import (
    ContextAssemblyResult,
    ContextBudgetExceeded,
    estimate_input_units,
)
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
    ContextCompactionOutput,
    ContextCompactionRequest,
    ContextInspectionOutput,
    ContextInspectionRequest,
    ContextManagerCapabilities,
)
from modules.agent.application.skill_runtime import skill_contribution_content
from modules.agent.domain.context import ContextPriority, ContextSourceType


def _message_class(messages: list[Any], class_name: str):
    for message in messages:
        if message.__class__.__name__ == class_name:
            return message.__class__
    raise ContextBudgetExceeded(
        f"Standard Context Manager v2 requires a {class_name} template"
    )


class StandardSkillsContextAssembler:
    """Skills-aware wrapper for the Standard Context Manager."""

    __slots__ = ("_base",)

    def __init__(self, base: ContextAssembler) -> None:
        self._base = base

    def _with_skills(self, request):
        candidates = getattr(request.runtime_context, "skill_context", None) or []
        if not candidates:
            return request, False

        messages = list(request.messages)
        policy = request.policy.skills
        if (
            policy is None
            or ContextSourceType.SKILL not in request.policy.allowed_sources
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

        units = sum(
            estimate_input_units(message.content) for message in materialized
        )
        if units > policy.max_units:
            raise ContextBudgetExceeded(
                f"Active Skills exceed the Skills context budget: {units} > {policy.max_units}"
            )

        insertion = 0
        while (
            insertion < len(messages)
            and messages[insertion].__class__.__name__ == "SystemMessage"
        ):
            insertion += 1
        messages[insertion:insertion] = materialized

        effective_policy = request.policy.model_copy(deep=True)
        effective_policy.source_priorities[ContextSourceType.SKILL] = (
            ContextPriority.MANDATORY
        )
        effective_policy.deduplication.sources = [
            source
            for source in effective_policy.deduplication.sources
            if source != ContextSourceType.SKILL
        ]
        replacement_messages = (
            tuple(messages)
            if isinstance(request.messages, tuple)
            else messages
        )
        return (
            replace(
                request,
                messages=replacement_messages,
                policy=effective_policy,
            ),
            True,
        )

    def inspect(
        self,
        request: ContextInspectionRequest,
    ) -> ContextInspectionOutput:
        effective, _ = self._with_skills(request)
        return self._base.inspect(effective)

    async def compact(
        self,
        request: ContextCompactionRequest,
        capabilities: ContextManagerCapabilities,
    ) -> ContextCompactionOutput:
        # Compaction replacement indexes refer to the stable Runtime conversation.
        # Skills are invocation-scoped additions, so they must not shift those indexes.
        return await self._base.compact(request, capabilities)

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        effective, has_candidates = self._with_skills(request)
        assembled = self._base.assemble(effective)
        if not has_candidates:
            return assembled

        candidates = getattr(request.runtime_context, "skill_context", None) or []
        manifest = dict(assembled.snapshot.manifest)
        manifest["skills"] = {
            "retention": "run",
            "instruction_compaction": "protected",
            "installed_catalog": True,
            "active_versions": sorted(
                {
                    item["skill_version_id"]
                    for item in candidates
                    if item.get("skill_version_id")
                }
            ),
        }
        return ContextAssemblyResult(
            messages=assembled.messages,
            snapshot=replace(assembled.snapshot, manifest=manifest),
        )
