from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass
class ExecutionResult:
    success: bool
    status_code: int | None = None
    headers: dict | None = None
    body: str | None = None
    duration_ms: float | None = None
    error: str | None = None
    output: dict | None = None


class ToolExecutionPort(ABC):
    """Low-level HTTP execution port.

    This remains intentionally HTTP-specific. Runtime-level tool dispatch must use
    ToolRuntimePort/ToolRuntimeRegistry instead of depending on URL/method/body.
    """

    @abstractmethod
    async def execute(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        body: str | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        ...


class ToolRuntimePort(ABC):
    """Runtime-agnostic tool protocol port."""

    @abstractmethod
    async def execute(
        self,
        tool: Any,
        input_data: dict[str, Any] | None = None,
    ) -> ExecutionResult:
        ...

    @abstractmethod
    async def test(
        self,
        config: dict[str, Any],
        input_data: dict[str, Any] | None = None,
        timeout_ms: int = 30000,
    ) -> ExecutionResult:
        ...

    @abstractmethod
    def to_openai_definition(self, tool: Any) -> dict[str, Any]:
        ...


class McpSessionStorePort(ABC):
    """Operational cache for remote MCP protocol sessions."""

    @abstractmethod
    async def get(self, key: str) -> str | None:
        ...

    @abstractmethod
    async def set(self, key: str, session_id: str, ttl_seconds: int) -> None:
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        ...


class SecretCipherPort(ABC):

    @abstractmethod
    async def encrypt(self, plaintext: str) -> str:
        ...

    @abstractmethod
    async def decrypt(self, ciphertext: str) -> str:
        ...


class ToolSecretResolverPort(ABC):

    @abstractmethod
    async def resolve_headers(
        self,
        headers: list[dict],
        project_id: UUID,
    ) -> dict[str, str]:
        ...
