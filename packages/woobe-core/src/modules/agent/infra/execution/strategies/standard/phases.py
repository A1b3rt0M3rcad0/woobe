from __future__ import annotations

from enum import StrEnum


class StandardPhase(StrEnum):
    RESPONSE_GENERATION = "response_generation"
    CAPABILITY_RESPONSE_GENERATION = "capability_response_generation"
    TOOL_FOLLOWUP = "tool_followup"
    FINAL_RESPONSE_GENERATION = "final_response_generation"


class StandardCheckpointBoundary(StrEnum):
    PREFLIGHT = "agent_preflight_boundary"
    TOOL = "agent_tool_boundary"


def tool_followup_phase(round_index: int) -> str:
    if round_index <= 0:
        raise ValueError("Standard Tool follow-up round must be positive")
    return f"{StandardPhase.TOOL_FOLLOWUP.value}_{round_index}"


def is_standard_model_phase(value: str) -> bool:
    if value in {
        StandardPhase.RESPONSE_GENERATION.value,
        StandardPhase.CAPABILITY_RESPONSE_GENERATION.value,
        StandardPhase.FINAL_RESPONSE_GENERATION.value,
    }:
        return True
    return value.startswith(f"{StandardPhase.TOOL_FOLLOWUP.value}_")
