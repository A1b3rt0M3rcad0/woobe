from __future__ import annotations

from dataclasses import replace

from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.context_assembly import (
    ContextAssemblyResult,
    ContextBudgetExceeded,
    estimate_input_units,
)
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyOutput,
    ContextAssemblyRequest,
)
from modules.agent.application.skill_runtime import skill_contribution_content
from modules.agent.domain.context import ContextPriority, ContextSourceType


class StandardSkillsContextAssembler:
    """Standard v2: materialize Run-local Skills without modifying the v1 strategy."""

    __slots__ = ("_base",)

    def __init__(self, base: ContextAssembler) -> None:
        self._base = base

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        candidates = getattr(request.runtime_context, "skill_context", None) or []
        messages = list(request.messages)
        if candidates:
            policy = request.policy.skills
            if (
                policy is None
                or ContextSourceType.SKILL not in request.policy.allowed_sources
            ):
                raise ContextBudgetExceeded(
                    "Active Skills require an allowed SKILL source and a Skills budget"
                )
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
                    HumanMessage if item["component"] == "resource" else SystemMessage
                )
                materialized.append(
                    message_type(
                        content=content, additional_kwargs={"woobe_context": metadata}
                    )
                )
            units = sum(
                estimate_input_units(message.content) for message in materialized
            )
            if units > policy.max_units:
                raise ContextBudgetExceeded(
                    f"Active Skills exceed the Skills context budget: {units} > {policy.max_units}"
                )
            # Keep the current user input last and preserve all provider tool pairs.
            insertion = 0
            while insertion < len(messages) and isinstance(
                messages[insertion], SystemMessage
            ):
                insertion += 1
            messages[insertion:insertion] = materialized
        effective_policy = request.policy.model_copy(deep=True)
        if candidates:
            effective_policy.source_priorities[ContextSourceType.SKILL] = (
                ContextPriority.MANDATORY
            )
            # Canonical activation state already deduplicates each package/resource.
            effective_policy.deduplication.sources = [
                source
                for source in effective_policy.deduplication.sources
                if source != ContextSourceType.SKILL
            ]
        assembled = self._base.assemble(
            replace(request, messages=messages, policy=effective_policy)
        )
        if not candidates:
            return assembled
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
