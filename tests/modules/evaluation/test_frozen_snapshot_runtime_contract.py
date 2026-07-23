from pathlib import Path

import pytest

from modules.evaluation.application.target_resolver import EvaluationTargetResolver
from shared.infra.errors import ConflictError


ROOT = Path(__file__).resolve().parents[3]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_evaluation_workers_always_execute_the_persisted_agent_snapshot() -> None:
    run_worker = _source("src/modules/evaluation/infra/workers/run_worker.py")
    session_worker = _source(
        "src/modules/evaluation/infra/workers/run_judge_worker.py"
    )

    for source in (run_worker, session_worker):
        assert "release_id=None" in source
        assert "snapshot_override=target.snapshot" in source
        assert (
            'snapshot_override=target.snapshot if target.source_type == "draft" else None'
            not in source
        )


def test_network_evaluation_acceptance_is_atomic_and_snapshot_driven() -> None:
    gateway = _source("src/modules/evaluation/application/runtime_gateway.py")
    service = _source("src/modules/network/application/service_core.py")
    runtime = _source("src/modules/network/application/runtime.py")

    assert "frozen_snapshot=target.snapshot" in gateway
    assert "execution_metadata=execution_metadata" in gateway
    assert "_attach_evaluation_metadata" not in gateway
    assert "frozen_snapshot: dict[str, Any] | None = None" in service
    assert "execution_metadata: dict[str, Any] | None = None" in service
    assert (
        "if execution.definition_snapshot and execution.resolved_bindings_snapshot:"
        in runtime
    )
    assert '"run_purpose": execution.run_purpose' in runtime


def test_judge_runtime_checks_the_frozen_protocol_binding() -> None:
    protocol = _source("src/modules/evaluation/application/run_judge.py")
    gateway = _source("src/modules/evaluation/infra/runtime_safe_judge.py")

    assert 'selected["judge_model_snapshot"] = dict(snapshot)' in protocol
    assert "await self._validate_frozen_binding(" in gateway
    assert "Live Judge binding drifted from the frozen protocol" in gateway


def test_frozen_evaluation_rejects_live_only_tools() -> None:
    with pytest.raises(ConflictError, match="without immutable snapshots"):
        EvaluationTargetResolver._validate_tool_snapshots(
            {
                "runtime_config": {
                    "tools": {
                        "tool_ids": ["6f7ddbdc-2041-4ca3-a001-946305b902b7"],
                        "snapshots": [],
                    }
                }
            }
        )


def test_frozen_evaluation_accepts_matching_tool_snapshots() -> None:
    EvaluationTargetResolver._validate_tool_snapshots(
        {
            "runtime_config": {
                "tools": {
                    "tool_ids": ["6f7ddbdc-2041-4ca3-a001-946305b902b7"],
                    "snapshots": [
                        {"id": "6f7ddbdc-2041-4ca3-a001-946305b902b7"}
                    ],
                }
            }
        }
    )
