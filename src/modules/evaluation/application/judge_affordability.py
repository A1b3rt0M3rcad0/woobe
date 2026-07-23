from __future__ import annotations

import asyncio
import json
import time
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.models import ProviderCredentialModel
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from shared.infra.config import Settings
from shared.infra.crypto import decrypt_secret

_OPENROUTER_KEY_URL = "https://openrouter.ai/api/v1/key"
_CACHE_TTL_SECONDS = 30.0


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _fetch_openrouter_key(api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        _OPENROUTER_KEY_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "Woobe-Evaluation-Preflight/1.0",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=8.0) as response:
        raw = response.read(1_000_000)
    payload = json.loads(raw.decode("utf-8"))
    data = payload.get("data") if isinstance(payload, dict) else None
    return data if isinstance(data, dict) else {}


class JudgeAffordabilityService:
    """Provider-specific, short-lived credit validation without persisting secrets."""

    _cache: dict[UUID, tuple[float, dict[str, Any]]] = {}
    _locks: dict[UUID, asyncio.Lock] = {}

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings()

    async def inspect(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        provider_model_id: UUID,
        estimated_maximum_cost_usd: float | None,
    ) -> dict[str, Any]:
        model = await session.get(ProviderModelModel, provider_model_id)
        if model is None or model.project_id != project_id:
            return {
                "status": "blocked",
                "source": "provider_model",
                "blockers": [
                    {
                        "code": "judge_model_unavailable",
                        "message": "The selected Judge Model is unavailable for this Project",
                    }
                ],
                "warnings": [],
            }
        credential = await session.get(
            ProviderCredentialModel,
            model.provider_credential_id,
        )
        if credential is None or credential.project_id != project_id:
            return {
                "status": "blocked",
                "source": "credential",
                "blockers": [
                    {
                        "code": "judge_credential_invalid",
                        "message": "The Judge Model credential is unavailable for this Project",
                    }
                ],
                "warnings": [],
            }
        if credential.provider != "openrouter":
            return {
                "status": "unknown",
                "source": "provider_not_supported",
                "blockers": [],
                "warnings": [
                    {
                        "code": "judge_affordability_unknown",
                        "message": (
                            f"Live credit validation is not available for provider "
                            f"{credential.provider}; the first Judgment will run as a canary"
                        ),
                    }
                ],
            }

        status = await self._openrouter_status(credential)
        if status.get("error"):
            code = str(status.get("code") or "judge_affordability_unknown")
            terminal = code == "judge_credential_invalid"
            item = {
                "code": code,
                "message": str(status["error"]),
            }
            return {
                "status": "blocked" if terminal else "unknown",
                "source": "openrouter_api_v1_key",
                "blockers": [item] if terminal else [],
                "warnings": [] if terminal else [item],
            }

        remaining = _decimal(status.get("limit_remaining"))
        required = _decimal(estimated_maximum_cost_usd)
        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        if remaining is None:
            warnings.append(
                {
                    "code": "judge_affordability_unknown",
                    "message": (
                        "OpenRouter did not expose a finite remaining key limit; "
                        "the first Judgment will run as a canary"
                    ),
                }
            )
        elif required is not None and remaining < required:
            blockers.append(
                {
                    "code": "judge_insufficient_credits",
                    "message": (
                        f"OpenRouter reports ${remaining:.6f} remaining for this key, below "
                        f"the maximum Judge budget of ${required:.6f}"
                    ),
                }
            )

        return {
            "status": "blocked" if blockers else ("ready" if remaining is not None else "unknown"),
            "source": "openrouter_api_v1_key",
            "blockers": blockers,
            "warnings": warnings,
            "limit_usd": float(status["limit"])
            if _decimal(status.get("limit")) is not None
            else None,
            "limit_remaining_usd": float(remaining) if remaining is not None else None,
            "usage_usd": float(status["usage"])
            if _decimal(status.get("usage")) is not None
            else None,
            "limit_reset": status.get("limit_reset"),
            "is_free_tier": status.get("is_free_tier"),
            "expires_at": status.get("expires_at"),
            "checked_at_monotonic": time.monotonic(),
        }

    async def _openrouter_status(
        self,
        credential: ProviderCredentialModel,
    ) -> dict[str, Any]:
        cached = self._cache.get(credential.id)
        now = time.monotonic()
        if cached and now - cached[0] < _CACHE_TTL_SECONDS:
            return dict(cached[1])

        lock = self._locks.setdefault(credential.id, asyncio.Lock())
        async with lock:
            cached = self._cache.get(credential.id)
            now = time.monotonic()
            if cached and now - cached[0] < _CACHE_TTL_SECONDS:
                return dict(cached[1])
            try:
                api_key = decrypt_secret(
                    credential.encrypted_secret,
                    self._settings.encryption_key,
                )
                data = await asyncio.to_thread(_fetch_openrouter_key, api_key)
                result = {
                    "limit": data.get("limit"),
                    "limit_remaining": data.get("limit_remaining"),
                    "usage": data.get("usage"),
                    "limit_reset": data.get("limit_reset"),
                    "is_free_tier": data.get("is_free_tier"),
                    "expires_at": data.get("expires_at"),
                }
            except urllib.error.HTTPError as exc:
                if exc.code in {401, 403}:
                    result = {
                        "code": "judge_credential_invalid",
                        "error": "OpenRouter rejected the Judge Model credential during preflight",
                    }
                elif exc.code == 429:
                    result = {
                        "code": "judge_affordability_rate_limited",
                        "error": "OpenRouter rate-limited the live credit preflight; canary protection remains enabled",
                    }
                else:
                    result = {
                        "code": "judge_affordability_unknown",
                        "error": f"OpenRouter credit preflight returned HTTP {exc.code}; canary protection remains enabled",
                    }
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                result = {
                    "code": "judge_affordability_unknown",
                    "error": (
                        "OpenRouter credit preflight could not be completed; "
                        f"canary protection remains enabled ({type(exc).__name__})"
                    ),
                }
            self._cache[credential.id] = (time.monotonic(), dict(result))
            return result


__all__ = ["JudgeAffordabilityService"]
