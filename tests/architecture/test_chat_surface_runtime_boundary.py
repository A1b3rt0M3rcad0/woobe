from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHAT_ROUTES = ROOT / "packages/woobe-core/src/modules/chat_surface/presentation/routes.py"
API_COMPOSITION = ROOT / "packages/woobe-api/src/chat_runtime_composition.py"


def test_chat_surface_message_route_has_no_target_runtime_imports() -> None:
    source = CHAT_ROUTES.read_text(encoding="utf-8")
    assert "from modules.agent" not in source
    assert "from modules.network" not in source
    assert "ChatRuntimeGateway" in source
    assert "chat_surface_runtime_gateway" in source


def test_api_composition_owns_agent_network_chat_runtime_dispatch() -> None:
    source = API_COMPOSITION.read_text(encoding="utf-8")
    assert "from modules.agent" in source
    assert "from modules.network" in source
    assert "class ApiChatRuntimeGateway" in source
    assert "ChatRuntimeRequest" in source
