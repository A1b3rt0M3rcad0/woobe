from collections.abc import Sequence

from modules.core.application.interfaces.api_key_issuer import (
    ApiKeyIssuer,
    IssuedApiKey,
)
from shared.security.api_keys import (
    format_api_key_prefix,
    issue_chat_surface_api_key,
    issue_project_api_key,
    issue_runtime_api_key,
    normalize_project_api_key_scopes,
)


class SharedApiKeyIssuer(ApiKeyIssuer):
    def issue_project(self) -> IssuedApiKey:
        return issue_project_api_key()

    def issue_runtime(self, environment: str) -> IssuedApiKey:
        return issue_runtime_api_key(environment)

    def issue_chat_surface(self) -> IssuedApiKey:
        return issue_chat_surface_api_key()

    def normalize_project_scopes(self, scopes: Sequence[str]) -> list[str]:
        return normalize_project_api_key_scopes(scopes)

    def format_prefix(
        self,
        value: str,
        *,
        key_version: int,
        kind: str,
        environment: str | None,
    ) -> str:
        return format_api_key_prefix(
            value,
            key_version=key_version,
            kind=kind,
            environment=environment,
        )
