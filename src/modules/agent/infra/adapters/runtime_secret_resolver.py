from __future__ import annotations

from uuid import UUID

from modules.agent.application.interfaces.ports import ToolSecretResolverPort
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.database.runtime_transaction_runner import (
    AgentRuntimeTransactionRunner,
)


SECRET_REF_PREFIX = "{{secret:"
SECRET_REF_SUFFIX = "}}"


class RuntimeToolSecretResolver(ToolSecretResolverPort):
    """Resolves Tool secrets in a short transaction before external I/O starts."""

    def __init__(
        self,
        transactions: AgentRuntimeTransactionRunner,
        cipher: SecretCipherAdapter,
    ) -> None:
        self._transactions = transactions
        self._cipher = cipher

    async def resolve_headers(
        self,
        headers: list[dict],
        project_id: UUID,
    ) -> dict[str, str]:
        async def resolve(repositories: AgentRuntimeRepositories, _outbox):
            resolved: dict[str, str] = {}
            for header in headers:
                key = header.get("key", "")
                value = header.get("value", "")
                if not key:
                    continue
                secret_name = self._extract_secret_name(value)
                if secret_name is not None:
                    try:
                        secret = await repositories.tool_secrets.get_by_name(
                            project_id,
                            secret_name,
                        )
                        value = await self._cipher.decrypt(secret.encrypted_value)
                    except Exception:
                        value = ""
                resolved[key] = value
            return resolved

        return await self._transactions.run(resolve)

    @staticmethod
    def _extract_secret_name(value: str) -> str | None:
        if not value.startswith(SECRET_REF_PREFIX):
            return None
        end = value.find(SECRET_REF_SUFFIX, len(SECRET_REF_PREFIX))
        if end == -1:
            return None
        return value[len(SECRET_REF_PREFIX):end]
