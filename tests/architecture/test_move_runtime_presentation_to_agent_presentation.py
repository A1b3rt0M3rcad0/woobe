"""Architecture tests for spec 044 — move runtime presentation to agent presentation."""
import pathlib
import warnings

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = ROOT / "tests" / "architecture" / "legacy_import_allowlist.yaml"


def _load_allowlist():
    with open(ALLOWLIST_PATH) as f:
        data = yaml.safe_load(f)
    return data.get("entries", [])


def test_move_runtime_presentation_to_agent_presentation_success():
    """Verify runtime presentation artifacts exist in agent.presentation."""
    from modules.agent.presentation.routes import runtime_router
    assert runtime_router.prefix == "/runtime"

    from modules.agent.presentation.schemas import (
        AskRequest,
        AskResponse,
        CreateSessionRequest,
        MessageResponse,
        SendMessageRequest,
        SessionResponse,
        SourceResponse,
        ToolCallResponse,
        UsageResponse,
    )
    assert AskRequest is not None
    assert AskResponse is not None
    assert CreateSessionRequest is not None
    assert SessionResponse is not None
    assert MessageResponse is not None
    assert SendMessageRequest is not None
    assert UsageResponse is not None
    assert SourceResponse is not None
    assert ToolCallResponse is not None

    from modules.agent.presentation.controllers.ask_agent_controller import AskAgentController
    from modules.agent.presentation.controllers.ask_agent_stream_controller import handle_ask_stream
    from modules.agent.presentation.controllers.create_ask_job_controller import CreateAskJobController
    from modules.agent.presentation.controllers.create_session_controller import CreateSessionController
    from modules.agent.presentation.controllers.get_ask_job_controller import GetAskJobController
    from modules.agent.presentation.controllers.list_agent_sessions_controller import ListAgentSessionsController
    from modules.agent.presentation.controllers.list_messages_controller import ListMessagesController
    from modules.agent.presentation.controllers.send_message_controller import SendMessageController

    assert AskAgentController is not None
    assert callable(handle_ask_stream)
    assert CreateAskJobController is not None
    assert CreateSessionController is not None
    assert GetAskJobController is not None
    assert ListAgentSessionsController is not None
    assert ListMessagesController is not None
    assert SendMessageController is not None


def test_move_runtime_presentation_to_agent_presentation_keeps_legacy_compatibility():
    """Verify shims at runtime/presentation still export expected symbols."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)

        from modules.runtime.presentation import routes as rt_routes
        assert hasattr(rt_routes, "router")

        from modules.runtime.presentation import schemas as rt_schemas
        assert hasattr(rt_schemas, "AskResponse")
        assert hasattr(rt_schemas, "SessionResponse")
        assert hasattr(rt_schemas, "CreateSessionRequest")

        from modules.runtime.presentation.controllers import ask_agent_controller as rt_ctrl
        assert hasattr(rt_ctrl, "AskAgentController")


def test_move_runtime_presentation_to_agent_presentation_rejects_forbidden_dependency():
    """Verify agent presentation does not import runtime internals."""
    import ast

    allowlist = _load_allowlist()
    allowed_files = {
        entry["file"]
        for entry in allowlist
        if entry.get("target_module") == "runtime"
    }

    agent_pres_dir = ROOT / "src" / "modules" / "agent" / "presentation"
    violations = []

    for py_file in agent_pres_dir.rglob("*.py"):
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

    assert violations == [], f"Forbidden runtime imports in agent/presentation: {violations}"
