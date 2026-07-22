from __future__ import annotations

from copy import deepcopy
from typing import Any


_BEHAVIORAL_TOOL_ALIASES = {
    "ask_question": "Ask the user a clarifying question when required information is missing.",
    "request_information": "Request the missing information before proceeding.",
    "clarify_input": "Ask for clarification when the request is ambiguous.",
    "respond_to_user": "Respond directly to the user.",
    "refuse_request": "Refuse the request when it violates the applicable policy.",
    "explain_error": "Explain the error in clear user-facing language.",
}


def repair_generated_tool_references(
    payload: dict[str, Any],
    *,
    allowed_names: list[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    repaired = deepcopy(payload)
    warnings: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    canonical = {name.casefold(): name for name in allowed_names}

    for index, case in enumerate(repaired.get("cases") or []):
        if not isinstance(case, dict):
            continue
        contract = case.get("expected_contract")
        outcome = case.get("expected_outcome")
        if not isinstance(contract, dict) or not isinstance(outcome, dict):
            continue
        tools = contract.get("tools")
        if not isinstance(tools, dict):
            continue

        for field in ("required", "forbidden"):
            source = tools.get(field)
            if not isinstance(source, list):
                continue
            accepted: list[str] = []
            for raw_name in source:
                name = str(raw_name).strip()
                if not name:
                    continue
                exact = canonical.get(name.casefold())
                if exact:
                    accepted.append(exact)
                    if exact != name:
                        warnings.append(
                            {
                                "path": f"cases[{index}].expected_contract.tools.{field}",
                                "code": "normalized_tool_name_case",
                                "message": f"Normalized Tool name '{name}' to '{exact}'.",
                            }
                        )
                    continue

                behavior = _BEHAVIORAL_TOOL_ALIASES.get(name.casefold())
                if behavior:
                    behavior_field = (
                        "required_behavior" if field == "required" else "forbidden_behavior"
                    )
                    values = outcome.get(behavior_field)
                    if not isinstance(values, list):
                        values = []
                    if behavior not in values:
                        values.append(behavior)
                    outcome[behavior_field] = values
                    warnings.append(
                        {
                            "path": f"cases[{index}].expected_contract.tools.{field}",
                            "code": "converted_behavioral_tool_reference",
                            "message": (
                                f"Converted '{name}' from a Tool reference to "
                                f"{behavior_field}."
                            ),
                        }
                    )
                    continue

                errors.append(
                    {
                        "path": f"cases[{index}].expected_contract.tools.{field}",
                        "code": "unknown_tool",
                        "tool_name": name,
                        "message": (
                            f"Tool '{name}' is not available in the selected snapshot."
                        ),
                    }
                )
            tools[field] = accepted
        contract["tools"] = tools
        case["expected_contract"] = contract
        case["expected_outcome"] = outcome

    return repaired, warnings, errors


def grouped_unknown_tools(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = {}
    for issue in errors:
        if issue.get("code") != "unknown_tool":
            continue
        name = str(issue.get("tool_name") or "unknown")
        grouped.setdefault(name, []).append(str(issue.get("path") or "cases"))
    return [
        {
            "tool_name": name,
            "reference_count": len(paths),
            "paths": paths,
            "message": (
                f"Tool '{name}' is referenced by {len(paths)} Test Case(s) but is "
                "not present in the selected snapshot."
            ),
        }
        for name, paths in sorted(grouped.items())
    ]


__all__ = [
    "grouped_unknown_tools",
    "repair_generated_tool_references",
]
