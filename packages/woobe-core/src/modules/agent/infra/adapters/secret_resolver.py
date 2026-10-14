from __future__ import annotations

from uuid import UUID
import re
from shared.contracts.project_configuration import ConfigurationError

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
                    if secret is None or secret.project_id != project_id:
                        raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
                    if getattr(secret, "configuration_reference", None) is not None:
                        # A legacy helper has no environment/consumer identity.
                        # It must not resolve central material by name alone.
                        raise ConfigurationError("LEGACY_ENVIRONMENT_REQUIRED")
                    value = await self._cipher.decrypt(secret.encrypted_value)
                    if not isinstance(value, str) or not value or any(character in value for character in "\r\n\x00"):
                        raise ConfigurationError("CONFIG_VALUE_INVALID")
                except ConfigurationError:
                    raise
                except Exception:
                    raise ConfigurationError("CONFIG_STORE_UNAVAILABLE") from None
            resolved[key] = value
        return resolved

    def _extract_secret_name(self, value: str) -> str | None:
        if not isinstance(value, str):
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        match = re.fullmatch(r"\{\{secret:([^{}]+)\}\}", value)
        if match:
            name = match[1].strip()
            if name:
                return name
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        if SECRET_REF_PREFIX in value:
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        return None
