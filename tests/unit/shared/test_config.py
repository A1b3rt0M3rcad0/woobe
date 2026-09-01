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
