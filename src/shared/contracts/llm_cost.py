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


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _context_window_from_metadata(metadata: dict[str, Any]) -> int | None:
    """Resolve only explicitly configured/discovered model capacity.

    Provider model discovery persists catalog capability metadata under
    ``metadata.catalog`` while manual/API configuration may keep the same values
    at the metadata root. Some providers also retain their original payload in
    ``provider_model_raw``. All of these are immutable ProviderModel evidence;
    none of the fallbacks below invent a context window.
    """

    catalog = _mapping(metadata.get("catalog"))
    raw = _mapping(metadata.get("provider_model_raw"))
    raw_top_provider = _mapping(raw.get("top_provider"))

    return _first_positive_int(
        metadata.get("context_window"),
        metadata.get("context_length"),
        metadata.get("max_context_tokens"),
        metadata.get("max_input_tokens"),
        catalog.get("context_window"),
        catalog.get("context_length"),
        catalog.get("max_context_tokens"),
        catalog.get("max_input_tokens"),
        raw.get("context_window"),
        raw.get("context_length"),
        raw.get("max_context_tokens"),
        raw.get("max_input_tokens"),
        raw_top_provider.get("context_length"),
    )


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

    Context capacity is copied only when ProviderModel metadata or its preserved
    provider catalog payload contains a positive explicit capacity. Unknown model
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
    context_window = _context_window_from_metadata(source)

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
