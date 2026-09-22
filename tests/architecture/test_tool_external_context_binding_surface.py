from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "packages" / "woobe-frontend" / "src"
API_FORM = FRONTEND / "features" / "tools" / "components" / "ApiFirstToolForm.tsx"
BINDING_EDITOR = FRONTEND / "features" / "tools" / "components" / "ToolInputBindingsEditor.tsx"
MCP_PANEL = FRONTEND / "features" / "tools" / "components" / "McpProviderPanel.tsx"
TOOL_SETTINGS = FRONTEND / "features" / "tools" / "components" / "ToolSettingsModal.tsx"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_http_route_editor_exposes_external_context_bindings() -> None:
    form = _source(API_FORM)
    editor = _source(BINDING_EDITOR)

    assert "<ToolInputBindingsEditor" in form
    assert "Choose whether each value is provided by the Agent or resolved from External Context" in form
    assert "bindings: toolInputBindingsForSchema(preview.inputSchema, route.bindings)" in form
    assert "Agent inputs" not in form

    assert "External Context" in editor
    assert "Model-provided" in editor
    assert "immutable Run snapshot" in editor
    assert "toolInputBindingsForSchema" in editor


def test_mcp_project_tool_can_edit_discovered_tool_bindings() -> None:
    panel = _source(MCP_PANEL)
    settings = _source(TOOL_SETTINGS)

    assert "allowBindingEdit" in panel
    assert "<ToolInputBindingsEditor" in panel
    assert "Save bindings" in panel
    assert "toolInputBindingsForSchema(bindingTool.input_schema" in panel
    assert "allowBindingEdit />" in settings
