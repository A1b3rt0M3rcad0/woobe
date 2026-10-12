from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from math import isfinite
from typing import Any


_DEFAULT_CURRENCY = "USD"
_COST_QUANT = Decimal("0.0000000001")


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() and value >= 0 and isfinite(float(value)) else None
    if isinstance(value, (int, float, str)):
        text = str(value).strip()
        if not text:
            return None
        try:
            parsed = Decimal(text)
            return parsed if parsed.is_finite() and parsed >= 0 and isfinite(float(parsed)) else None
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
    """Resolve only explicitly configured/discovered model capacity."""

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


def _max_output_from_metadata(metadata: dict[str, Any]) -> int | None:
    capabilities = _mapping(metadata.get("capabilities"))
    catalog = _mapping(metadata.get("catalog"))
    raw = _mapping(metadata.get("provider_model_raw"))
    raw_top_provider = _mapping(raw.get("top_provider"))
    return _first_positive_int(
        metadata.get("max_output_tokens"),
        capabilities.get("max_output_tokens"),
        catalog.get("max_output_tokens"),
        raw.get("max_output_tokens"),
        raw.get("max_completion_tokens"),
        raw_top_provider.get("max_completion_tokens"),
    )


def _capability_bool(metadata: dict[str, Any], key: str) -> bool | None:
    capabilities = _mapping(metadata.get("capabilities"))
    value = capabilities.get(key)
    return value if isinstance(value, bool) else None


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
    """Build immutable runtime model capability/cost evidence from ProviderModel metadata.

    Context/output limits are copied only from explicit manual or provider-discovered
    metadata. Unknown capabilities remain unknown; the runtime never infers them from
    the model name.
    """
    source = metadata or {}
    pricing = source.get("pricing") if isinstance(source.get("pricing"), dict) else source

    currency = _first_text(pricing.get("currency"), source.get("currency")) or _DEFAULT_CURRENCY
    billing_unit = _first_text(pricing.get("billing_unit"), source.get("billing_unit")) or "per_1m_tokens"
    divisor = {
        "per_1m_tokens": Decimal(1_000_000),
        "per_1k_tokens": Decimal(1_000),
        "per_token": Decimal(1),
    }.get(billing_unit)

    def per_million_rate(canonical_fields: tuple[str, ...], aliases: tuple[str, ...]) -> Decimal | None:
        # Explicit canonical rates declare their unit; malformed canonical values
        # never silently fall back to a different alias. Generic rates use the unit.
        for field in canonical_fields:
            if pricing.get(field) is not None:
                return _decimal(pricing[field])
        rate = _first_decimal(*(pricing.get(field) for field in aliases))
        return rate * Decimal(1_000_000) / divisor if rate is not None and divisor is not None else None

    input_per_1m = per_million_rate((
        "input_cost_per_1m_tokens", "input_cost_usd_per_1m_tokens",
        "prompt_cost_per_1m_tokens", "prompt_cost_usd_per_1m_tokens",
    ), ("input", "prompt"))
    output_per_1m = per_million_rate((
        "output_cost_per_1m_tokens", "output_cost_usd_per_1m_tokens",
        "completion_cost_per_1m_tokens", "completion_cost_usd_per_1m_tokens",
    ), ("output", "completion"))
    pricing_id = _first_text(pricing.get("pricing_id"), pricing.get("id"), source.get("pricing_id"))
    context_window = _context_window_from_metadata(source)
    max_output_tokens = _max_output_from_metadata(source)

    return {
        "provider_model_id": _stringify(provider_model_id),
        "provider_credential_id": _stringify(provider_credential_id),
        "provider": provider.value if hasattr(provider, "value") else _stringify(provider),
        "model": model,
        "context_window": context_window,
        "max_output_tokens": max_output_tokens,
        "supports_tools": _capability_bool(source, "supports_tools"),
        "supports_json": _capability_bool(source, "supports_json"),
        "supports_streaming": _capability_bool(source, "supports_streaming"),
        "capability_source": _first_text(source.get("capability_source"), source.get("source")),
        "pricing_id": pricing_id,
        "currency": currency.upper(),
        "billing_unit": "per_1m_tokens" if divisor is not None else billing_unit,
        "input_cost_per_1m_tokens": float(input_per_1m) if input_per_1m is not None else None,
        "output_cost_per_1m_tokens": float(output_per_1m) if output_per_1m is not None else None,
        "input_cost_per_token": float(input_per_1m / Decimal(1_000_000)) if input_per_1m is not None else None,
        "output_cost_per_token": float(output_per_1m / Decimal(1_000_000)) if output_per_1m is not None else None,
        "source": _first_text(pricing.get("source"), source.get("pricing_source")) or "provider_model_metadata",
        "configured": currency.upper() == "USD" and divisor is not None and input_per_1m is not None and output_per_1m is not None,
    }


def calculate_llm_cost(
    *,
    input_tokens: int | None,
    output_tokens: int | None,
    pricing_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    if any(not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0 for tokens in (input_tokens, output_tokens)):
        return {
            "cost_usd": None,
            "cost_status": "unknown_tokens",
            "cost_reason": "LLM provider did not return complete token usage",
        }

    if not pricing_snapshot:
        return {
            "cost_usd": None,
            "cost_status": "unknown_pricing",
            "cost_reason": "Provider model has no active pricing configured",
        }

    if ((_first_text(pricing_snapshot.get("currency")) or "USD").upper() != "USD"
            or pricing_snapshot.get("billing_unit", "per_1m_tokens") != "per_1m_tokens"):
        return {"cost_usd": None, "cost_status": "unknown_pricing", "cost_reason": "Pricing currency or billing unit is unsupported for USD metering"}

    if not pricing_snapshot.get("configured"):
        return {"cost_usd": None, "cost_status": "unknown_pricing", "cost_reason": "Provider model has no complete valid pricing configured"}

    input_rate = _decimal(pricing_snapshot.get("input_cost_per_token"))
    output_rate = _decimal(pricing_snapshot.get("output_cost_per_token"))
    if input_rate is None or output_rate is None:
        return {
            "cost_usd": None,
            "cost_status": "unknown_pricing",
            "cost_reason": "Provider model pricing is incomplete",
        }

    total = (Decimal(input_tokens) * input_rate) + (Decimal(output_tokens) * output_rate)
    try:
        cost_usd = float(total.quantize(_COST_QUANT, rounding=ROUND_HALF_UP))
    except (InvalidOperation, OverflowError):
        cost_usd = float("nan")
    if not isfinite(cost_usd):
        return {"cost_usd": None, "cost_status": "unknown_pricing", "cost_reason": "Cost exceeds supported USD precision"}
    return {
        "cost_usd": cost_usd,
        "cost_status": "known",
        "cost_reason": None,
    }
