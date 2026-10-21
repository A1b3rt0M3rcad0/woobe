from __future__ import annotations

import os

from woobe._transport.http import RuntimeTransport
from woobe.artifacts import ArtifactsClient
from woobe.connect import Connect

DEFAULT_BASE_URL = "https://api.woobe.com.br"


class Woobe:
    """Entry point for the Woobe Python SDK.

    Runtime Keys select remote targets and authorize explicitly scoped data
    access. Configuration, grants, Tools and execution remain server-side.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float = 30.0,
        max_reconnect_attempts: int = 4,
        reconnect_base_delay_seconds: float = 0.25,
    ) -> None:
        resolved_base_url = base_url or os.getenv("WOOBE_BASE_URL") or DEFAULT_BASE_URL
        self._transport = RuntimeTransport(
            base_url=resolved_base_url,
            timeout_seconds=timeout_seconds,
        )
        self._max_reconnect_attempts = max(0, max_reconnect_attempts)
        self._reconnect_base_delay_seconds = max(0.0, reconnect_base_delay_seconds)
        self.connect = Connect(self)

    async def aclose(self) -> None:
        await self._transport.aclose()

    def artifacts(
        self, *, project_id: str, runtime_key: str, environment: str = "production"
    ) -> ArtifactsClient:
        """Create a direct, explicitly scoped Artifacts API client (no Session/Run)."""
        return ArtifactsClient(
            transport=self._transport,
            project_id=project_id,
            runtime_key=runtime_key,
            environment=environment,
        )

    async def __aenter__(self) -> Woobe:
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        await self.aclose()
