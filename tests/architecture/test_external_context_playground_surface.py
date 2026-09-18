from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "packages" / "woobe-frontend" / "src"
PLAYGROUND_PAGE = FRONTEND / "pages" / "AgentPlaygroundPage.tsx"
PLAYGROUND_HEADER = (
    FRONTEND / "features" / "playground" / "components" / "PlaygroundHeader.tsx"
)
RUNTIME_CONTEXT = (
    FRONTEND / "features" / "contracts" / "RuntimeContextPanel.tsx"
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_external_context_values_are_opened_from_playground_header() -> None:
    page = _source(PLAYGROUND_PAGE)
    header = _source(PLAYGROUND_HEADER)

    assert "onExternalContextClick={() => setShowContextModal(true)}" in page
    assert "externalContextFieldCount={externalContextFieldCount}" in page
    assert 'title="External Context"' in header
    assert 'aria-label="External Context"' in header
    assert "<Braces" in header


def test_external_context_values_use_modal_instead_of_inline_chat_panel() -> None:
    page = _source(PLAYGROUND_PAGE)
    modal = _source(RUNTIME_CONTEXT)

    chat_index = page.index("<ChatCanvas")
    modal_index = page.index("<RuntimeContextPanel")
    assert modal_index > chat_index
    assert "open={showContextModal}" in page
    assert "<Dialog" in modal
    assert 'title="External Context"' in modal
