from collections.abc import Sequence
from typing import Protocol


class IssuedApiKey(Protocol):
    value: str
    public_prefix: str
    digest: bytes
    key_version: int
    kind: str
    environment: str | None

    @property
    def display_prefix(self) -> str: ...


class ApiKeyIssuer(Protocol):
    def issue_project(self) -> IssuedApiKey: ...

    def issue_runtime(self, environment: str) -> IssuedApiKey: ...

    def issue_chat_surface(self) -> IssuedApiKey: ...

    def normalize_project_scopes(self, scopes: Sequence[str]) -> list[str]: ...

    def format_prefix(
        self,
        value: str,
        *,
        key_version: int,
        kind: str,
        environment: str | None,
    ) -> str: ...
