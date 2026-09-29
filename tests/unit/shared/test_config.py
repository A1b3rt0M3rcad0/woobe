from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.infra.config import Settings


def test_core_distribution_rejects_enterprise_edition() -> None:
    with pytest.raises(ValidationError, match="WOOBE_EDITION must be 'core'"):
        Settings(
            edition="enterprise",
            secret_key="s" * 32,
            encryption_key="e" * 16,
        )


def test_core_distribution_accepts_core_edition() -> None:
    settings = Settings(
        edition="core",
        secret_key="s" * 32,
        encryption_key="e" * 16,
    )

    assert settings.edition == "core"


def test_chat_surface_insecure_origins_are_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_settings = Settings(
        edition="core",
        secret_key="s" * 32,
        encryption_key="e" * 16,
    )
    assert default_settings.chat_surface_allow_insecure_origins is False

    monkeypatch.setenv("WOOBE_CHAT_SURFACE_ALLOW_INSECURE_ORIGINS", "true")
    enabled_settings = Settings(
        edition="core",
        secret_key="s" * 32,
        encryption_key="e" * 16,
    )

    assert enabled_settings.chat_surface_allow_insecure_origins is True


def test_default_context_manager_is_programmable_v3() -> None:
    settings = Settings(
        edition="core",
        secret_key="s" * 32,
        encryption_key="e" * 16,
    )

    assert settings.default_context_manager == "stdcm"


def test_default_context_manager_is_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WOOBE_DEFAULT_CONTEXT_MANAGER", "  adaptive  ")

    settings = Settings(
        edition="core",
        secret_key="s" * 32,
        encryption_key="e" * 16,
    )

    assert settings.default_context_manager == "adaptive"


@pytest.mark.parametrize(
    "value",
    [
        "stdcm:legacy",
        "adaptive:legacy",
        "adaptive:v2",
        ":",
    ],
)
def test_default_context_manager_rejects_invalid_or_alias_values(
    value: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WOOBE_DEFAULT_CONTEXT_MANAGER", value)

    with pytest.raises(
        ValidationError,
        match="WOOBE_DEFAULT_CONTEXT_MANAGER must be a plain registered manager name",
    ):
        Settings(
            edition="core",
            secret_key="s" * 32,
            encryption_key="e" * 16,
        )
