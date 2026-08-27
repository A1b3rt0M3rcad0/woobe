from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from modules.agent.application.dtos.model_discovery_dtos import AvailableProviderModelOutput
from shared.contracts.errors import ValidationError


OPENAI_MODELS_URL = "https://api.openai.com/v1/models"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class ModelDiscoveryContext:
    provider: str
    api_key: str
    metadata: dict[str, Any]


class ProviderModelDiscoveryError(RuntimeError):
    pass


def _json_get(url: str, api_key: str, *, timeout: int = 20) -> dict[str, Any]:
    headers = {
        "Accept": "application/json",
        "User-Agent": "ProjectRAI/1.0",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = UrlRequest(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ProviderModelDiscoveryError(f"Provider model discovery failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ProviderModelDiscoveryError(f"Provider model discovery failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ProviderModelDiscoveryError("Provider model discovery timed out") from exc
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ProviderModelDiscoveryError("Provider model discovery returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise ProviderModelDiscoveryError("Provider model discovery returned an unsupported response")
    return data


async def _async_json_get(url: str, api_key: str) -> dict[str, Any]:
    return await asyncio.to_thread(_json_get, url, api_key)


def _base_url_with_models_path(base_url: str) -> str:
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValidationError("OpenAI-compatible provider requires base_url in credential metadata")
    return f"{normalized}/models"


def _number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return parsed


def _positive_int_or_none(*values: Any) -> int | None:
    for value in values:
        if isinstance(value, bool) or value is None:
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return None


def _per_token_to_per_1m(value: Any) -> float | None:
    parsed = _number_or_none(value)
    if parsed is None:
        return None
    return parsed * 1_000_000


def _supports_parameter(raw: dict[str, Any], names: set[str]) -> bool | None:
    supported = raw.get("supported_parameters")
    if isinstance(supported, list):
        return any(str(item) in names for item in supported)
    return None


class ModelDiscoveryService:
    async def list_models(self, context: ModelDiscoveryContext) -> list[AvailableProviderModelOutput]:
        provider = context.provider
        if provider == "openai":
            return self._normalize_openai(await _async_json_get(OPENAI_MODELS_URL, context.api_key), provider="openai")
        if provider == "custom":
            base_url = str(context.metadata.get("base_url") or "")
            url = _base_url_with_models_path(base_url)
            return self._normalize_openai(await _async_json_get(url, context.api_key), provider="custom")
        if provider == "openrouter":
            base_url = str(context.metadata.get("base_url") or OPENROUTER_BASE_URL).rstrip("/")
            return self._normalize_openrouter(await _async_json_get(f"{base_url}/models", context.api_key))
        raise ValidationError(f"Provider {provider} does not support model discovery")

    def _normalize_openai(self, payload: dict[str, Any], *, provider: str) -> list[AvailableProviderModelOutput]:
        items = payload.get("data")
        if not isinstance(items, list):
            raise ProviderModelDiscoveryError("OpenAI-compatible model discovery response has no data array")
        models: list[AvailableProviderModelOutput] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            model_id = str(raw.get("id") or "").strip()
            if not model_id:
                continue
            models.append(
                AvailableProviderModelOutput(
                    id=model_id,
                    label=model_id,
                    provider=provider,
                    owned_by=str(raw.get("owned_by")) if raw.get("owned_by") else None,
                    context_window=_positive_int_or_none(
                        raw.get("context_window"),
                        raw.get("context_length"),
                        raw.get("max_context_tokens"),
                        raw.get("max_input_tokens"),
                    ),
                    max_output_tokens=_positive_int_or_none(
                        raw.get("max_output_tokens"),
                        raw.get("max_completion_tokens"),
                    ),
                    supports_tools=_supports_parameter(raw, {"tools", "tool_choice"}),
                    supports_json=_supports_parameter(raw, {"response_format"}),
                    supports_streaming=True if raw.get("supports_streaming") is True else None,
                    raw=raw,
                )
            )
        return sorted(models, key=lambda item: item.id)

    def _normalize_openrouter(self, payload: dict[str, Any]) -> list[AvailableProviderModelOutput]:
        items = payload.get("data")
        if not isinstance(items, list):
            raise ProviderModelDiscoveryError("OpenRouter model discovery response has no data array")
        models: list[AvailableProviderModelOutput] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            model_id = str(raw.get("id") or "").strip()
            if not model_id:
                continue
            pricing = raw.get("pricing") if isinstance(raw.get("pricing"), dict) else {}
            top_provider = raw.get("top_provider") if isinstance(raw.get("top_provider"), dict) else {}
            models.append(
                AvailableProviderModelOutput(
                    id=model_id,
                    label=str(raw.get("name") or model_id),
                    provider="openrouter",
                    context_window=_positive_int_or_none(raw.get("context_length")),
                    max_output_tokens=_positive_int_or_none(
                        top_provider.get("max_completion_tokens"),
                        raw.get("max_output_tokens"),
                    ),
                    input_cost_per_1m_tokens=_per_token_to_per_1m(pricing.get("prompt")),
                    output_cost_per_1m_tokens=_per_token_to_per_1m(pricing.get("completion")),
                    supports_tools=_supports_parameter(raw, {"tools", "tool_choice"}),
                    supports_json=_supports_parameter(raw, {"response_format"}),
                    supports_streaming=True,
                    raw=raw,
                )
            )
        return sorted(models, key=lambda item: item.label.lower())
