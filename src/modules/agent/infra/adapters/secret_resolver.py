from __future__ import annotations

from uuid import UUID

from modules.agent.application.interfaces.ports import SecretCipherPort, ToolSecretResolverPort
from modules.agent.application.interfaces.repositories import SecretRepository


SECRET_REF_PREFIX = "{{secret:"
SECRET_REF_SUFFIX = "}}"


class ToolSecretResolverAdapter(ToolSecretResolverPort):

    def __init__(
        self,
        secret_repo: SecretRepository,
        cipher: SecretCipherPort,
    ) -> None:
        self._secret_repo = secret_repo
        self._cipher = cipher

    async def resolve_headers(
        self,
        headers: list[dict],
        project_id: UUID,
    ) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for h in headers:
            key = h.get("key", "")
            value = h.get("value", "")
            if not key:
                continue

            secret_name = self._extract_secret_name(value)
            if secret_name is not None:
                try:
                    secret = await self._secret_repo.get_by_name(project_id, secret_name)
                    value = await self._cipher.decrypt(secret.encrypted_value)
                except Exception:
                    value = ""
            resolved[key] = value
        return resolved

    def _extract_secret_name(self, value: str) -> str | None:
        if not value.startswith(SECRET_REF_PREFIX):
            return None
        end = value.find(SECRET_REF_SUFFIX, len(SECRET_REF_PREFIX))
        if end == -1:
            return None
        return value[len(SECRET_REF_PREFIX):end]
