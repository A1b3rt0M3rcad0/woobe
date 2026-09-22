from __future__ import annotations

import inspect

from modules.core.infra.database.project_runs_reader import SQLProjectRunsReader


def test_project_runs_summary_uses_network_invocations_for_network_agent_runs() -> None:
    source = inspect.getsource(SQLProjectRunsReader._summary)

    assert "network.network_executions" in source
    assert "network.network_invocations" in source
    assert "COUNT(invocation.id) AS agent_run_count" in source
    assert "SELECT COUNT(*)\n                    FROM selected_network_invocations" in source


def test_project_runs_reader_does_not_require_agent_projection_to_show_network_children() -> None:
    source = inspect.getsource(SQLProjectRunsReader._attach_child_runs)

    assert "FROM network.network_invocations AS invocation" in source
    assert "LEFT JOIN agent.agent_runs AS run" in source
    assert "COALESCE(run.id, invocation.id) AS id" in source
    assert "COALESCE(run.trace_id, invocation.trace_id, invocation.id) AS trace_id" in source


def test_project_runs_reader_keeps_network_execution_visible_when_related_read_models_lag() -> None:
    source = inspect.getsource(SQLProjectRunsReader._network_runs)

    assert "FROM network.network_executions AS execution" in source
    assert "LEFT JOIN network.networks AS network" in source
    assert "LEFT JOIN network.network_sessions AS network_session" in source
