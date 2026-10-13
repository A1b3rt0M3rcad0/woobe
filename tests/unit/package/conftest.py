"""Owner-only Package tests do not inherit a process host's Core SQL adapter."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from modules.package.application import configuration_barrier


@pytest.fixture(autouse=True)
def package_configuration_barrier(monkeypatch):
    # Some API tests initialize the process composition earlier in the suite.
    # These Package unit repositories intentionally have only Package SQLite
    # tables. The real cross-owner barrier is exercised against PostgreSQL.
    port = SimpleNamespace(lock_project=AsyncMock())
    monkeypatch.setattr(configuration_barrier, '_factory', lambda session: port)
    return port
