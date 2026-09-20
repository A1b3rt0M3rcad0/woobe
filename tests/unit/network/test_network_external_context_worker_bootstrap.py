from __future__ import annotations

import subprocess
import sys


def test_cold_worker_import_maps_run_external_context_columns_without_api_bootstrap() -> None:
    script = r"""
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkSessionModel,
    NetworkVersionModel,
)

assert hasattr(NetworkExecutionModel, "external_context_snapshot")
assert not hasattr(NetworkSessionModel, "external_context_session_values")
assert hasattr(NetworkVersionModel, "effective_external_context_contract")

assert "external_context_snapshot" in NetworkExecutionModel.__table__.c
assert "external_context_session_values" not in NetworkSessionModel.__table__.c
assert "effective_external_context_contract" in NetworkVersionModel.__table__.c
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_canonical_network_models_keep_external_context_on_execution_not_session() -> None:
    from modules.network.infra.database.models import (
        NetworkExecutionModel,
        NetworkSessionModel,
        NetworkVersionModel,
    )

    assert "external_context_snapshot" in NetworkExecutionModel.__dict__
    assert "external_context_session_values" not in NetworkSessionModel.__dict__
    assert "effective_external_context_contract" in NetworkVersionModel.__dict__
