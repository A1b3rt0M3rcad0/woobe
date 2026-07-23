from __future__ import annotations

from copy import deepcopy
from typing import Any

CASE_TYPES = ("success", "refusal", "handled_error", "expected_failure")
INTERACTION_MODES = ("single_turn", "session")
SEVERITIES = ("low", "normal", "high", "critical")


def _list_value(value: Any) -> tuple[list[str], bool]:
    if value is None:
        return [], False
    if isinstance(value, str):
        normalized = value.strip()
        return ([normalized] if normalized else []), bool(normalized)
    if isinstance(value, (tuple, set)):
        value = list(value)
    if not isinstance(value, list):
        return [], False
    return [str(item).strip() for item in value if str(item).strip()], False


def suite_generation_json_schema() -> dict[str, Any]:
    string_list = {
        "type": "array",
        "items": {"type": "string", "minLength": 1},
    }
    expected_outcome = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "type",
            "allowed_failure_origins",
            "allowed_failure_stages",
            "allowed_failure_codes",
            "required_behavior",
            "forbidden_behavior",
        ],
        "properties": {
            "type": {"type": "string", "enum": list(CASE_TYPES)},
            "allowed_failure_origins": string_list,
            "allowed_failure_stages": string_list,
            "allowed_failure_codes": string_list,
            "required_behavior": string_list,
            "forbidden_behavior": string_list,
        },
    }
    session_turn = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "message",
            "expected_behavior",
            "forbidden_behavior",
            "expected_contract",
        ],
        "properties": {
            "message": {"type": "string", "minLength": 1},
            "expected_behavior": string_list,
            "forbidden_behavior": string_list,
            "expected_contract": {
                "type": "object",
                "additionalProperties": True,
            },
        },
    }
    test_case = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "name",
            "case_type",
            "interaction_mode",
            "message",
            "turns",
            "initial_context",
            "expected_outcome",
            "expected_contract",
            "severity",
            "weight",
            "blocking",
            "tags",
            "production_frequency",
        ],
        "properties": {
            "name": {"type": "string", "minLength": 1},
            "case_type": {"type": "string", "enum": list(CASE_TYPES)},
            "interaction_mode": {
                "type": "string",
                "enum": list(INTERACTION_MODES),
            },
            # Session cases repeat the first turn here so providers can satisfy one
            # compact schema without oneOf/if/then support.
            "message": {"type": "string", "minLength": 1},
            "turns": {
                "type": "array",
                "items": session_turn,
                "maxItems": 20,
            },
            "initial_context": {"type": ["object", "null"]},
            "expected_outcome": expected_outcome,
            "expected_contract": {
                "type": "object",
                "additionalProperties": False,
                "required": ["semantic_criteria", "tools", "output_contract"],
                "properties": {
                    "semantic_criteria": {
                        "type": "array",
                        "minItems": 1,
                        "items": {"type": "string", "minLength": 1},
                    },
                    "tools": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["required", "forbidden"],
                        "properties": {
                            "required": string_list,
                            "forbidden": string_list,
                        },
                    },
                    "output_contract": {
                        "type": "object",
                        "additionalProperties": True,
                        "required": ["required"],
                        "properties": {"required": {"type": "boolean"}},
                    },
                },
            },
            "severity": {"type": "string", "enum": list(SEVERITIES)},
            "weight": {"type": "number", "exclusiveMinimum": 0, "maximum": 100},
            "blocking": {"type": "boolean"},
            "tags": string_list,
            "production_frequency": {
                "type": ["number", "null"],
                "minimum": 0,
                "maximum": 1,
            },
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["schema_version", "suite", "coverage", "cases"],
        "properties": {
            "schema_version": {"type": "integer", "const": 1},
            "suite": {
                "type": "object",
                "additionalProperties": False,
                "required": ["suggested_name", "description", "objective"],
                "properties": {
                    "suggested_name": {"type": "string"},
                    "description": {"type": "string"},
                    "objective": {"type": "string"},
                },
            },
            "coverage": {
                "type": "object",
                "additionalProperties": {"type": "integer", "minimum": 0},
            },
            "cases": {
                "type": "array",
                "items": test_case,
                "minItems": 1,
                "maxItems": 10,
            },
        },
    }


SUITE_GENERATION_EXAMPLES: list[dict[str, Any]] = [
    {
        "name": "Answer a supported billing question",
        "case_type": "success",
        "interaction_mode": "single_turn",
        "message": "How can I update my billing address?",
        "turns": [],
        "initial_context": {"customer_authenticated": True},
        "expected_outcome": {
            "type": "success",
            "allowed_failure_origins": [],
            "allowed_failure_stages": [],
            "allowed_failure_codes": [],
            "required_behavior": ["Explain the supported billing-address update process."],
            "forbidden_behavior": ["Do not claim the address was changed without an authorized operation."],
        },
        "expected_contract": {
            "semantic_criteria": [
                "The response must directly address changing a billing address.",
                "The response must not invent customer data.",
            ],
            "tools": {"required": [], "forbidden": []},
            "output_contract": {"required": True},
        },
        "severity": "normal",
        "weight": 1,
        "blocking": False,
        "tags": ["billing", "core-behavior"],
        "production_frequency": 0.4,
    },
    {
        "name": "Retain customer context through a follow-up session",
        "case_type": "success",
        "interaction_mode": "session",
        "message": "My name is Alberto and I need help changing my billing address.",
        "turns": [
            {
                "message": "My name is Alberto and I need help changing my billing address.",
                "expected_behavior": ["Acknowledge the request without inventing account data."],
                "forbidden_behavior": [],
                "expected_contract": {},
            },
            {
                "message": "Before we continue, what name did I give you?",
                "expected_behavior": ["Recall that the user said their name is Alberto."],
                "forbidden_behavior": ["Do not claim another name was provided."],
                "expected_contract": {},
            },
        ],
        "initial_context": {"customer_authenticated": True},
        "expected_outcome": {
            "type": "success",
            "allowed_failure_origins": [],
            "allowed_failure_stages": [],
            "allowed_failure_codes": [],
            "required_behavior": ["Maintain conversational context across turns."],
            "forbidden_behavior": ["Do not contradict prior user-provided facts."],
        },
        "expected_contract": {
            "semantic_criteria": [
                "The session must retain relevant user-provided context across turns.",
                "The final response must remain consistent with earlier turns.",
            ],
            "tools": {"required": [], "forbidden": []},
            "output_contract": {"required": True},
        },
        "severity": "high",
        "weight": 2,
        "blocking": False,
        "tags": ["session", "context-retention"],
        "production_frequency": 0.1,
    },
]


def normalize_authoring_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized = deepcopy(payload)
    warnings: list[dict[str, Any]] = []
    raw_cases = normalized.get("cases")
    if not isinstance(raw_cases, list):
        return normalized, warnings

    cases: list[Any] = []
    for index, source in enumerate(raw_cases):
        if not isinstance(source, dict):
            cases.append(source)
            continue
        case = dict(source)
        case_type = str(
            case.get("case_type")
            or (case.get("expected_outcome") or {}).get("type")
            or "success"
        ).strip().lower()
        case["case_type"] = case_type
        interaction_mode = str(case.get("interaction_mode") or "single_turn").strip().lower()
        raw_turns = case.get("turns")
        if raw_turns is None:
            raw_turns = case.get("session_turns")
            if raw_turns is not None:
                warnings.append(
                    {
                        "path": f"cases[{index}].turns",
                        "code": "normalized_session_turns_alias",
                        "message": "Converted session_turns to turns.",
                    }
                )
        turns: list[dict[str, Any]] = []
        if isinstance(raw_turns, list):
            for turn in raw_turns:
                if not isinstance(turn, dict):
                    continue
                message = str(
                    turn.get("message")
                    or (turn.get("input_payload") or {}).get("message")
                    or turn.get("input")
                    or ""
                ).strip()
                expected_behavior, _ = _list_value(
                    turn.get("expected_behavior") or turn.get("required_behavior")
                )
                forbidden_behavior, _ = _list_value(turn.get("forbidden_behavior"))
                turn_contract = dict(
                    turn.get("expected_contract")
                    or turn.get("deterministic_checks")
                    or {}
                )
                tools = dict(turn_contract.get("tools") or {})
                required_tools, _ = _list_value(
                    tools.get("required")
                    or turn.get("required_tool")
                    or turn.get("required_tools")
                )
                forbidden_tools, _ = _list_value(
                    tools.get("forbidden")
                    or turn.get("forbidden_tool")
                    or turn.get("forbidden_tools")
                )
                if required_tools or forbidden_tools or "tools" in turn_contract:
                    turn_contract["tools"] = {
                        **tools,
                        "required": required_tools,
                        "forbidden": forbidden_tools,
                    }
                turns.append(
                    {
                        "message": message,
                        "expected_behavior": expected_behavior,
                        "forbidden_behavior": forbidden_behavior,
                        "expected_contract": turn_contract,
                    }
                )
        if turns and interaction_mode == "single_turn":
            interaction_mode = "session"
            warnings.append(
                {
                    "path": f"cases[{index}].interaction_mode",
                    "code": "inferred_session_interaction",
                    "message": "Inferred session interaction from turns.",
                }
            )
        case["interaction_mode"] = interaction_mode
        case["turns"] = turns if interaction_mode == "session" else []
        case["message"] = str(
            case.get("message")
            or (case.get("input_payload") or {}).get("message")
            or (case.get("input_payload") or {}).get("input")
            or (case.get("input_payload") or {}).get("prompt")
            or (turns[0].get("message") if turns else "")
            or ""
        )

        contract = dict(case.get("expected_contract") or {})
        outcome = dict(
            case.get("expected_outcome")
            or contract.get("expected_outcome")
            or {}
        )
        outcome["type"] = case_type

        alias_required = case.get("expected_behavior") or case.get("required_behavior")
        if not outcome.get("required_behavior") and alias_required:
            outcome["required_behavior"] = alias_required
            warnings.append(
                {
                    "path": f"cases[{index}].expected_outcome.required_behavior",
                    "code": "normalized_expected_behavior_alias",
                    "message": "Converted expected behavior alias to required_behavior.",
                }
            )
        if not outcome.get("forbidden_behavior") and case.get("forbidden_behavior"):
            outcome["forbidden_behavior"] = case.get("forbidden_behavior")

        for field in (
            "allowed_failure_origins",
            "allowed_failure_stages",
            "allowed_failure_codes",
            "required_behavior",
            "forbidden_behavior",
        ):
            values, converted = _list_value(outcome.get(field))
            outcome[field] = values
            if converted:
                warnings.append(
                    {
                        "path": f"cases[{index}].expected_outcome.{field}",
                        "code": "normalized_string_to_list",
                        "message": f"Converted {field} from text to a list.",
                    }
                )

        semantic_source = contract.get("semantic_criteria")
        if semantic_source is None:
            semantic_source = (
                case.get("semantic_criteria")
                or case.get("expected_criteria")
                or case.get("expected_result")
                or case.get("expected")
            )
            if semantic_source is not None:
                warnings.append(
                    {
                        "path": f"cases[{index}].expected_contract.semantic_criteria",
                        "code": "normalized_semantic_criteria_alias",
                        "message": "Converted expected result alias to semantic_criteria.",
                    }
                )
        semantic, converted = _list_value(semantic_source)
        contract["semantic_criteria"] = semantic
        if converted:
            warnings.append(
                {
                    "path": f"cases[{index}].expected_contract.semantic_criteria",
                    "code": "normalized_string_to_list",
                    "message": "Converted semantic_criteria from text to a list.",
                }
            )

        tools = dict(contract.get("tools") or {})
        for field in ("required", "forbidden"):
            values, converted = _list_value(tools.get(field))
            tools[field] = values
            if converted:
                warnings.append(
                    {
                        "path": f"cases[{index}].expected_contract.tools.{field}",
                        "code": "normalized_string_to_list",
                        "message": f"Converted Tool {field} values from text to a list.",
                    }
                )
        contract["tools"] = tools
        output_contract = dict(contract.get("output_contract") or {})
        output_contract.setdefault("required", case_type != "expected_failure")
        contract["output_contract"] = output_contract
        contract.pop("expected_outcome", None)

        case["expected_outcome"] = outcome
        case["expected_contract"] = contract
        case.setdefault("initial_context", None)
        case.setdefault("severity", "normal")
        case.setdefault("weight", 1)
        case.setdefault("blocking", False)
        tags, converted = _list_value(case.get("tags"))
        case["tags"] = tags
        if converted:
            warnings.append(
                {
                    "path": f"cases[{index}].tags",
                    "code": "normalized_string_to_list",
                    "message": "Converted tags from text to a list.",
                }
            )
        case.setdefault("production_frequency", None)
        cases.append(case)

    normalized["schema_version"] = int(normalized.get("schema_version") or 1)
    normalized["suite"] = (
        normalized.get("suite") if isinstance(normalized.get("suite"), dict) else {}
    )
    normalized["coverage"] = (
        normalized.get("coverage") if isinstance(normalized.get("coverage"), dict) else {}
    )
    normalized["cases"] = cases
    return normalized, warnings


def generation_failure_metadata(
    error: str | None,
    validation: dict[str, Any] | None,
) -> dict[str, Any]:
    errors = list((validation or {}).get("errors") or [])
    codes = {str(item.get("code") or "") for item in errors if isinstance(item, dict)}
    lowered = str(error or "").lower()

    if any(
        token in lowered
        for token in (
            "lengthfinishreasonerror",
            "length limit was reached",
            "finish_reason=length",
            "finish reason 'length'",
            "finish reason: length",
            "maximum output length",
        )
    ):
        return {
            "category": "output_length_limit",
            "retryable": True,
            "recommended_action": "retry_with_larger_output_budget",
        }
    if any(
        token in lowered
        for token in (
            "estimated_generation_cost_limit_exceeded",
            "configured cost limit",
            "cost limit exceeded",
            "maximum total cost",
            "maximum_cost_usd",
        )
    ):
        return {
            "category": "cost_limit",
            "retryable": False,
            "recommended_action": "reduce_cases_or_raise_cost_limit",
        }
    if any(token in lowered for token in ("401", "403", "credential", "unauthorized")):
        return {
            "category": "credential_error",
            "retryable": False,
            "recommended_action": "change_model_or_credential",
        }
    if any(token in lowered for token in ("429", "rate limit", "ratelimit")):
        return {
            "category": "provider_rate_limit",
            "retryable": True,
            "recommended_action": "retry_with_backoff",
        }
    if any(
        token in lowered
        for token in ("timeout", "timed out", "502", "503", "504", "unavailable")
    ):
        return {
            "category": "provider_transient",
            "retryable": True,
            "recommended_action": "retry_provider_call",
        }
    if "unknown_tool" in codes:
        return {
            "category": "unknown_tool",
            "retryable": False,
            "recommended_action": "edit_tool_references",
        }
    if "duplicate_across_batches" in codes:
        return {
            "category": "duplicate_cases",
            "retryable": True,
            "recommended_action": "repair_duplicate_cases",
        }
    if errors:
        return {
            "category": "invalid_case_contract",
            "retryable": True,
            "recommended_action": "repair_invalid_cases",
        }
    if error:
        return {
            "category": "generation_failed",
            "retryable": True,
            "recommended_action": "retry_provider_call",
        }
    return {"category": None, "retryable": False, "recommended_action": None}


__all__ = [
    "CASE_TYPES",
    "INTERACTION_MODES",
    "SEVERITIES",
    "SUITE_GENERATION_EXAMPLES",
    "generation_failure_metadata",
    "normalize_authoring_payload",
    "suite_generation_json_schema",
]
