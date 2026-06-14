"""Architecture tests for spec 043 — move runtime infra to agent infra."""
import pathlib
import warnings

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = ROOT / "tests" / "architecture" / "legacy_import_allowlist.yaml"


def _load_allowlist():
    with open(ALLOWLIST_PATH) as f:
        data = yaml.safe_load(f)
    return data.get("entries", [])


def test_move_runtime_infra_to_agent_infra_success():
    """Verify runtime infra artifacts exist in agent.infra.database and agent.infra.workers."""
    from modules.agent.infra.database.models import (
        AskJobModel,
        MessageModel,
        RuntimeInboxEventModel,
        RuntimeOutboxEventModel,
        SessionModel,
    )
    assert SessionModel.__tablename__ == "sessions"
    assert SessionModel.__table_args__[-1]["schema"] == "runtime"
    assert MessageModel.__tablename__ == "messages"
    assert AskJobModel.__tablename__ == "ask_jobs"
    assert RuntimeOutboxEventModel.__tablename__ == "outbox_events"
    assert RuntimeInboxEventModel.__tablename__ == "inbox_events"

    from modules.agent.infra.database.mappers import (
        ask_job_to_model,
        message_to_model,
        model_to_ask_job,
        model_to_message,
        model_to_session,
        session_to_model,
    )
    assert callable(session_to_model)
    assert callable(model_to_session)
    assert callable(message_to_model)
    assert callable(model_to_message)
    assert callable(ask_job_to_model)
    assert callable(model_to_ask_job)

    from modules.agent.infra.database.repositories import (
        SQLAlchemyAskJobRepository,
        SQLAlchemyMessageRepository,
        SQLAlchemyRuntimeOutboxEventWriter,
        SQLAlchemySessionRepository,
    )
    assert SQLAlchemySessionRepository is not None
    assert SQLAlchemyMessageRepository is not None
    assert SQLAlchemyAskJobRepository is not None
    assert SQLAlchemyRuntimeOutboxEventWriter is not None

    from modules.agent.infra.workers.ask_job_worker import AskJobWorker
    assert AskJobWorker is not None


def test_move_runtime_infra_to_agent_infra_keeps_legacy_compatibility():
    """Verify shims at runtime/infra still export expected symbols with deprecation."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)

        from modules.runtime.infra import models as rt_models
        assert hasattr(rt_models, "SessionModel")
        assert hasattr(rt_models, "MessageModel")
        assert hasattr(rt_models, "AskJobModel")
        assert hasattr(rt_models, "OutboxEventModel")
        assert hasattr(rt_models, "InboxEventModel")

        from modules.runtime.infra import mappers as rt_mappers
        assert hasattr(rt_mappers, "session_to_model")
        assert hasattr(rt_mappers, "model_to_session")
        assert hasattr(rt_mappers, "message_to_model")
        assert hasattr(rt_mappers, "model_to_message")
        assert hasattr(rt_mappers, "ask_job_to_model")
        assert hasattr(rt_mappers, "model_to_ask_job")

        from modules.runtime.infra import repositories as rt_repos
        assert hasattr(rt_repos, "SQLAlchemySessionRepository")
        assert hasattr(rt_repos, "SQLAlchemyMessageRepository")
        assert hasattr(rt_repos, "SQLAlchemyAskJobRepository")
        assert hasattr(rt_repos, "SQLAlchemyOutboxEventWriter")

        from modules.runtime.infra import ask_job_worker as rt_worker_mod
        assert hasattr(rt_worker_mod, "AskJobWorker")


def test_move_runtime_infra_to_agent_infra_rejects_forbidden_dependency():
    """Verify agent infra does not import runtime internals (only allowed via allowlist)."""
    import ast

    allowlist = _load_allowlist()
    allowed_files = {
        entry["file"]
        for entry in allowlist
        if entry.get("target_module") == "runtime"
    }

    agent_infra_dir = ROOT / "src" / "modules" / "agent" / "infra"
    violations = []

    for py_file in agent_infra_dir.rglob("*.py"):
        rel_path = str(py_file.relative_to(ROOT)).replace("\\", "/")
        if rel_path in allowed_files:
            continue

        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "modules.runtime" in node.module:
                    violations.append(f"{rel_path}: {node.module}")

    assert violations == [], f"Forbidden runtime imports in agent/infra: {violations}"
