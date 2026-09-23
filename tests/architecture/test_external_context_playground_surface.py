from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "packages" / "woobe-frontend" / "src"
PLAYGROUND_PAGE = FRONTEND / "pages" / "AgentPlaygroundPage.tsx"
PLAYGROUND_HEADER = (
    FRONTEND / "features" / "playground" / "components" / "PlaygroundHeader.tsx"
)
CHAT_COMPOSER = (
    FRONTEND / "features" / "playground" / "components" / "ChatComposer.tsx"
)
SESSIONS_PANEL = (
    FRONTEND / "features" / "playground" / "components" / "SessionsPanel.tsx"
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_external_context_is_not_a_global_playground_header_action() -> None:
    page = _source(PLAYGROUND_PAGE)
    header = _source(PLAYGROUND_HEADER)

    assert "currentEnvironmentRelease?.external_context_contract ?? null" in page
    assert "onExternalContextClick" not in page
    assert "onExternalContextClick" not in header
    assert 'aria-label="External Context"' not in header


def test_external_context_respects_session_and_run_lifecycle_scopes() -> None:
    page = _source(PLAYGROUND_PAGE)
    composer = _source(CHAT_COMPOSER)
    sessions = _source(SESSIONS_PANEL)

    assert "externalContextContract={activeExternalContextContract}" in page
    assert "filterExternalContextInput(" in page
    assert "lockedExternalContextValues" in page
    assert "external_context_snapshot" in page
    assert "external_context_session_values" not in page
    assert "Session Context" not in sessions

    assert "External Context" in composer
    assert "Session fields are set once and reused automatically." in composer
    assert "Run fields may change on each Run." in composer
    assert "lockedValues={lockedExternalContextValues}" in composer
