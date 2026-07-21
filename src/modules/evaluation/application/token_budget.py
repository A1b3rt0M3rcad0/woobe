from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class TokenBudgetReport:
    estimated_input_tokens: int
    maximum_input_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int
    truncation_applied: bool
    truncated_sections: tuple[str, ...]
    preserved_sections: tuple[str, ...]
    estimation_strategy: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimated_input_tokens": self.estimated_input_tokens,
            "maximum_input_tokens": self.maximum_input_tokens,
            "reserved_output_tokens": self.reserved_output_tokens,
            "safety_margin_tokens": self.safety_margin_tokens,
            "truncation_applied": self.truncation_applied,
            "truncated_sections": list(self.truncated_sections),
            "preserved_sections": list(self.preserved_sections),
            "estimation_strategy": self.estimation_strategy,
        }


@dataclass(frozen=True)
class BudgetedPayload:
    payload: dict[str, Any]
    report: TokenBudgetReport


def estimate_tokens(value: Any, *, characters_per_token: float = 3.2) -> int:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return max(1, math.ceil(len(encoded) / max(characters_per_token, 1.0)))


def recommended_generation_output_tokens(case_count: int) -> int:
    return max(1200, min(12_000, 600 + max(case_count, 1) * 220))


def context_window_from_metadata(metadata: dict[str, Any] | None) -> int:
    value = metadata or {}
    for key in ("context_window", "context_length", "max_context_tokens"):
        raw = value.get(key)
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            continue
        if parsed >= 4096:
            return parsed
    capabilities = value.get("capabilities")
    if isinstance(capabilities, dict):
        for key in ("context_window", "context_length"):
            try:
                parsed = int(capabilities.get(key))
            except (TypeError, ValueError):
                continue
            if parsed >= 4096:
                return parsed
    return 32_000


def _truncate_text(value: str, target_tokens: int) -> str:
    maximum_chars = max(200, int(target_tokens * 3.2))
    if len(value) <= maximum_chars:
        return value
    if maximum_chars < 600:
        return value[:maximum_chars]
    head = maximum_chars * 2 // 3
    tail = maximum_chars - head
    return value[:head] + "\n...[TRUNCATED]...\n" + value[-tail:]


def _compact_value(value: Any, target_tokens: int, *, depth: int = 0) -> Any:
    if target_tokens <= 0:
        return "[OMITTED_BY_TOKEN_BUDGET]"
    if depth > 10:
        return "[TRUNCATED_DEPTH]"
    if isinstance(value, str):
        return _truncate_text(value, target_tokens)
    if isinstance(value, list):
        if not value:
            return []
        maximum_items = max(1, min(len(value), target_tokens // 40 or 1))
        per_item = max(20, target_tokens // maximum_items)
        result = [_compact_value(item, per_item, depth=depth + 1) for item in value[:maximum_items]]
        if maximum_items < len(value):
            result.append({"truncated_items": len(value) - maximum_items})
        return result
    if isinstance(value, dict):
        if not value:
            return {}
        keys = list(value.keys())
        per_item = max(20, target_tokens // max(len(keys), 1))
        return {
            str(key): _compact_value(value[key], per_item, depth=depth + 1)
            for key in keys
        }
    return value


def budget_sections(
    sections: Iterable[tuple[str, Any, int, bool]],
    *,
    maximum_input_tokens: int,
    reserved_output_tokens: int,
    safety_margin_tokens: int = 500,
    context_window: int | None = None,
) -> BudgetedPayload:
    window = max(int(context_window or 32_000), 4096)
    hard_input_limit = min(
        max(int(maximum_input_tokens), 1000),
        max(window - max(reserved_output_tokens, 128) - max(safety_margin_tokens, 0), 1000),
    )
    normalized = list(sections)
    total_weight = sum(max(weight, 1) for _, _, weight, _ in normalized)
    payload: dict[str, Any] = {}
    truncated: list[str] = []
    preserved: list[str] = []

    required = [item for item in normalized if item[3]]
    optional = [item for item in normalized if not item[3]]
    required_floor = max(250, hard_input_limit // max(len(required) * 3, 1))
    remaining = hard_input_limit

    for name, value, weight, _ in required:
        desired = max(required_floor, hard_input_limit * max(weight, 1) // max(total_weight, 1))
        desired = min(desired, remaining)
        compacted = _compact_value(value, desired)
        used = estimate_tokens(compacted)
        payload[name] = compacted
        remaining = max(0, remaining - used)
        if estimate_tokens(value) > used:
            truncated.append(name)
        else:
            preserved.append(name)

    optional_weight = sum(max(weight, 1) for _, _, weight, _ in optional)
    for index, (name, value, weight, _) in enumerate(optional):
        slots_left = len(optional) - index
        if remaining <= 100:
            payload[name] = "[OMITTED_BY_TOKEN_BUDGET]"
            truncated.append(name)
            continue
        desired = max(100, remaining * max(weight, 1) // max(optional_weight, 1))
        desired = min(desired, max(100, remaining // max(slots_left, 1) * 2))
        compacted = _compact_value(value, desired)
        used = estimate_tokens(compacted)
        payload[name] = compacted
        remaining = max(0, remaining - used)
        optional_weight -= max(weight, 1)
        if estimate_tokens(value) > used:
            truncated.append(name)
        else:
            preserved.append(name)

    estimated = estimate_tokens(payload)
    if estimated > hard_input_limit:
        payload = _compact_value(payload, hard_input_limit)
        estimated = estimate_tokens(payload)
        truncated = list(dict.fromkeys([*truncated, "payload_guard"]))

    report = TokenBudgetReport(
        estimated_input_tokens=estimated,
        maximum_input_tokens=hard_input_limit,
        reserved_output_tokens=reserved_output_tokens,
        safety_margin_tokens=safety_margin_tokens,
        truncation_applied=bool(truncated),
        truncated_sections=tuple(dict.fromkeys(truncated)),
        preserved_sections=tuple(dict.fromkeys(preserved)),
        estimation_strategy="conservative_char_ratio_3_2",
    )
    return BudgetedPayload(payload=payload, report=report)


__all__ = [
    "BudgetedPayload",
    "TokenBudgetReport",
    "budget_sections",
    "context_window_from_metadata",
    "estimate_tokens",
    "recommended_generation_output_tokens",
]
