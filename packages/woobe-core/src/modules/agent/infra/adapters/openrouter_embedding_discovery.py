from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from modules.agent.application.dtos.model_discovery_dtos import AvailableProviderModelOutput
from modules.agent.infra.adapters.model_discovery import OPENROUTER_BASE_URL, ProviderModelDiscoveryError


def _json_get(url: str, api_key: str, *, timeout: int = 20) -> dict[str, Any]:
    request = UrlRequest(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Woobe/0.13.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise ProviderModelDiscoveryError(f"OpenRouter embedding discovery failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise ProviderModelDiscoveryError(f"OpenRouter embedding discovery failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise ProviderModelDiscoveryError("OpenRouter embedding discovery timed out") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ProviderModelDiscoveryError("OpenRouter embedding discovery returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise ProviderModelDiscoveryError("OpenRouter embedding discovery returned an unsupported response")
    return data


class OpenRouterEmbeddingModelDiscoveryService:
    async def list_models(self, *, api_key: str, metadata: dict[str, Any]) -> list[AvailableProviderModelOutput]:
        base_url = str(metadata.get("base_url") or OPENROUTER_BASE_URL).rstrip("/")
        payload = await asyncio.to_thread(_json_get, f"{base_url}/embeddings/models", api_key)
        items = payload.get("data")
        if not isinstance(items, list):
            raise ProviderModelDiscoveryError("OpenRouter embedding discovery response has no data array")

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
                    label=str(raw.get("name") or model_id),
                    provider="openrouter",
                    context_window=int(raw["context_length"]) if isinstance(raw.get("context_length"), int) else None,
                    raw=raw,
                )
            )
        return sorted(models, key=lambda item: item.label.lower())
