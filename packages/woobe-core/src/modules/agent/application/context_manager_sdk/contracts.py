from __future__ import annotations

from dataclasses import dataclass

from modules.agent.application.interfaces.context_policy import ContextPolicyV1


@dataclass(frozen=True, slots=True)
class ContextManagerOutcome:
    """Algorithm decisions produced by one concrete Context Manager."""

    policy: ContextPolicyV1
    materialize_skills: bool = False
