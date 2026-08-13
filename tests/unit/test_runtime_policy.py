from types import SimpleNamespace
from typing import Any, cast

import pytest

from shared.security.http_guard import _validate_runtime_security_settings


def _settings(environment: str, protected: bool, site: str = "lax") -> Any:
    values = {
        "environment": environment,
        "access_cookie_secure": protected,
        "access_cookie_same_site": site,
        "refresh_cookie_secure": protected,
        "refresh_cookie_same_site": site,
    }
    return cast(Any, SimpleNamespace(**values))


def test_production_rejects_unprotected_session_state() -> None:
    with pytest.raises(ValueError, match="transport security"):
        _validate_runtime_security_settings(_settings("production", False))


def test_production_accepts_protected_session_state() -> None:
    _validate_runtime_security_settings(_settings("production", True))


def test_cross_site_state_requires_transport_security() -> None:
    with pytest.raises(ValueError, match="transport security"):
        _validate_runtime_security_settings(_settings("test", False, "none"))


def test_invalid_site_policy_is_rejected() -> None:
    with pytest.raises(ValueError, match="same-site"):
        _validate_runtime_security_settings(_settings("test", True, "invalid"))
