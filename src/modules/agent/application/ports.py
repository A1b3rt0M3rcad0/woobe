from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
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
