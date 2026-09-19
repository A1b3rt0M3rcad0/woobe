from __future__ import annotations

import pytest

from shared.infra.crypto import encrypt_secret
from shared.infra.errors import ValidationError
from shared.project_environment import (
    PreparedProjectEnvironmentValue,
    ProjectEnvironmentService,
    materialize_project_environment_values,
    normalize_project_environment_key,
    normalize_project_environment_kind,
)


def test_materialize_project_environment_values_decrypts_only_secrets() -> None:
    encryption_key = "test-project-environment-encryption-key"
    encrypted = encrypt_secret("prod-secret", encryption_key)

    resolved = materialize_project_environment_values(
        {
            "API_URL": PreparedProjectEnvironmentValue(
                kind="value",
                stored_value="https://api.example.com",
            ),
            "API_KEY": PreparedProjectEnvironmentValue(
                kind="secret",
                stored_value=encrypted,
            ),
        },
        encryption_key=encryption_key,
    )

    assert resolved == {
        "API_URL": "https://api.example.com",
        "API_KEY": "prod-secret",
    }


@pytest.mark.parametrize(
    "key",
    ["API_KEY", "_PRIVATE", "service_url", "A1"],
)
def test_project_environment_key_accepts_identifier_style_names(key: str) -> None:
    assert normalize_project_environment_key(key) == key


@pytest.mark.parametrize(
    "key",
    ["", "API-KEY", "API.KEY", "1API_KEY", "API KEY"],
)
def test_project_environment_key_rejects_invalid_names(key: str) -> None:
    with pytest.raises(ValidationError):
        normalize_project_environment_key(key)


def test_project_environment_kind_is_explicit() -> None:
    assert normalize_project_environment_kind("value") == "value"
    assert normalize_project_environment_kind("secret") == "secret"

    with pytest.raises(ValidationError):
        normalize_project_environment_kind("credential")



class _ProjectEnvironmentResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _ProjectEnvironmentSession:
    def __init__(self, rows):
        self._rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def execute(self, *_args, **_kwargs):
        return _ProjectEnvironmentResult(self._rows)


@pytest.mark.asyncio
async def test_require_project_environment_keys_accepts_existing_keys() -> None:
    service = ProjectEnvironmentService(
        lambda: _ProjectEnvironmentSession([("API_URL",), ("API_KEY",)]),  # type: ignore[arg-type]
        encryption_key="test-key",
    )

    await service.require_keys(
        project_id=__import__("uuid").uuid4(),
        keys={"API_URL", "API_KEY"},
    )


@pytest.mark.asyncio
async def test_require_project_environment_keys_rejects_missing_keys() -> None:
    service = ProjectEnvironmentService(
        lambda: _ProjectEnvironmentSession([("API_URL",)]),  # type: ignore[arg-type]
        encryption_key="test-key",
    )

    with pytest.raises(ValidationError, match="API_KEY"):
        await service.require_keys(
            project_id=__import__("uuid").uuid4(),
            keys={"API_URL", "API_KEY"},
        )
