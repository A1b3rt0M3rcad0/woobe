from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.infra.config import Settings


def test_community_distribution_rejects_cloud_edition() -> None:
    with pytest.raises(ValidationError, match="WOOBE_EDITION must be 'community'"):
        Settings(
            edition="cloud",
            secret_key="s" * 32,
            encryption_key="e" * 16,
        )


def test_community_distribution_accepts_community_edition() -> None:
    settings = Settings(
        edition="community",
        secret_key="s" * 32,
        encryption_key="e" * 16,
    )

    assert settings.edition == "community"
    assert settings.is_cloud is False
    assert settings.managed_billing_enabled is False


def test_chat_surface_insecure_origins_are_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    default_settings = Settings(
        edition="community",
        secret_key="s" * 32,
        encryption_key="e" * 16,
    )
    assert default_settings.chat_surface_allow_insecure_origins is False

    monkeypatch.setenv("WOOBE_CHAT_SURFACE_ALLOW_INSECURE_ORIGINS", "true")
    enabled_settings = Settings(
        edition="community",
        secret_key="s" * 32,
        encryption_key="e" * 16,
    )

    assert enabled_settings.chat_surface_allow_insecure_origins is True
