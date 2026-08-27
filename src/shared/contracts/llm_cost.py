from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


_DEFAULT_CURRENCY = "USD"
_COST_QUANT = Decimal("0.0000000001")


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float, str)):
        text = str(value).strip()
        if not text:
            return None
        try:
            return Decimal(text)
        except (InvalidOperation, ValueError):
            return None
    return None


def _first_decimal(*values: Any) -> Decimal | None:
    for value in values:
        parsed = _decimal(value)
        if parsed is not None:
            return parsed
    return None


def _first_text(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_positive_int(*values: Any) -> int | None:
    for value in values:
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit():
            parsed = int(value)
            if parsed > 0:
                return parsed
    return None


def _stringify(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def provider_model_pricing_snapshot(
    *,
    provider_model_id: Any,
    provider_credential_id: Any,
    provider: Any,
    model: str | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build an immutable runtime model/cost snapshot from ProviderModel metadata.

    Supported pricing metadata shapes:
    - {"pricing": {"input_cost_per_1m_tokens": 0.14, "output_cost_per_1m_tokens": 0.28}}
    - {"pricing": {"input": 0.14, "output": 0.28, "currency": "USD"}}
    - {"input_cost_per_1m_tokens": 0.14, "output_cost_per_1m_tokens": 0.28}

    Context capacity is copied only when ProviderModel metadata provides a positive
    integer through context_window/context_length/max_context_tokens. Unknown model
    capacity remains unknown; the runtime never invents a provider context window.
    """
    source = metadata or {}
    pricing = source.get("pricing") if isinstance(source.get("pricing"), dict) else source

    input_per_1m = _first_decimal(
        pricing.get("input_cost_per_1m_tokens"),
        pricing.get("input_cost_usd_per_1m_tokens"),
        pricing.get("prompt_cost_per_1m_tokens"),
        pricing.get("prompt_cost_usd_per_1m_tokens"),
        pricing.get("input"),
        pricing.get("prompt"),
    )
    output_per_1m = _first_decimal(
        pricing.get("output_cost_per_1m_tokens"),
        pricing.get("output_cost_usd_per_1m_tokens"),
        pricing.get("completion_cost_per_1m_tokens"),
        pricing.get("completion_cost_usd_per_1m_tokens"),
        pricing.get("output"),
        pricing.get("completion"),
    )
    currency = _first_text(pricing.get("currency"), source.get("currency")) or _DEFAULT_CURRENCY
    pricing_id = _first_text(pricing.get("pricing_id"), pricing.get("id"), source.get("pricing_id"))
    context_window = _first_positive_int(
        source.get("context_window"),
        source.get("context_length"),
        source.get("max_context_tokens"),
        source.get("max_input_tokens"),
    )

    return {
        "provider_model_id": _stringify(provider_model_id),
        "provider_credential_id": _stringify(provider_credential_id),
        "provider": provider.value if hasattr(provider, "value") else _stringify(provider),
        "model": model,
        "context_window": context_window,
        "pricing_id": pricing_id,
        "currency": currency.upper(),
        "billing_unit": _first_text(pricing.get("billing_unit"), source.get("billing_unit")) or "per_1m_tokens",
        "input_cost_per_1m_tokens": float(input_per_1m) if input_per_1m is not None else None,
        "output_cost_per_1m_tokens": float(output_per_1m) if output_per_1m is not None else None,
        "input_cost_per_token": float(input_per_1m / Decimal(1_000_000)) if input_per_1m is not None else None,
        "output_cost_per_token": float(output_per_1m / Decimal(1_000_000)) if output_per_1m is not None else None,
        "source": _first_text(pricing.get("source"), source.get("pricing_source")) or "provider_model_metadata",
        "configured": input_per_1m is not None and output_per_1m is not None,
    }


def calculate_llm_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    pricing_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    if input_tokens is None or output_tokens is None:
        return {
            "cost_usd": None,
            "cost_status": "unknown_tokens",
            "cost_reason": "LLM provider did not return complete token usage",
        }

    if not pricing_snapshot or not pricing_snapshot.get("configured"):
        return {
            "cost_usd": None,
            "cost_status": "unknown_pricing",
            "cost_reason": "Provider model has no active pricing configured",
        }

    input_rate = _decimal(pricing_snapshot.get("input_cost_per_token"))
    output_rate = _decimal(pricing_snapshot.get("output_cost_per_token"))
    if input_rate is None or output_rate is None:
        return {
            "cost_usd": None,
            "cost_status": "unknown_pricing",
            "cost_reason": "Provider model pricing is incomplete",
        }

    total = (Decimal(input_tokens) * input_rate) + (Decimal(output_tokens) * output_rate)
    return {
        "cost_usd": float(total.quantize(_COST_QUANT, rounding=ROUND_HALF_UP)),
        "cost_status": "known",
        "cost_reason": None,
    }
