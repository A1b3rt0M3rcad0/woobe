from __future__ import annotations


def _first_not_none(*values) -> int | None:
    for v in values:
        if v is not None:
            return v
    return None


def normalize_llm_usage(
    result,
    cost_per_input_token: float | None = None,
    cost_per_output_token: float | None = None,
) -> dict:
    usage_metadata = getattr(result, "usage_metadata", None) or {}
    response_metadata = getattr(result, "response_metadata", None) or {}

    token_usage = response_metadata.get("token_usage")
    if token_usage is None:
        token_usage = response_metadata.get("usage", {})

    input_tokens = _first_not_none(
        usage_metadata.get("input_tokens"),
        usage_metadata.get("prompt_tokens"),
        token_usage.get("input_tokens"),
        token_usage.get("prompt_tokens"),
    )

    output_tokens = _first_not_none(
        usage_metadata.get("output_tokens"),
        usage_metadata.get("completion_tokens"),
        token_usage.get("output_tokens"),
        token_usage.get("completion_tokens"),
    )

    total_tokens = _first_not_none(
        usage_metadata.get("total_tokens"),
        token_usage.get("total_tokens"),
    )

    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    cost_usd = None
    if input_tokens is not None and output_tokens is not None:
        input_cost = (input_tokens * cost_per_input_token) if cost_per_input_token else 0
        output_cost = (output_tokens * cost_per_output_token) if cost_per_output_token else 0
        if input_cost or output_cost:
            cost_usd = round(input_cost + output_cost, 10)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cost_usd": cost_usd,
    }
