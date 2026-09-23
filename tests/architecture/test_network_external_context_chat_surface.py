from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "packages" / "woobe-frontend" / "src"
NETWORK_CHAT = (
    FRONTEND / "features" / "network" / "components" / "NetworkChatWorkspace.tsx"
)
CHAT_CANVAS = (
    FRONTEND / "features" / "playground" / "components" / "ChatCanvas.tsx"
)
CHAT_COMPOSER = (
    FRONTEND / "features" / "playground" / "components" / "ChatComposer.tsx"
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_network_external_context_uses_the_same_chat_composer_surface_as_standalone() -> None:
    network = _source(NETWORK_CHAT)
    canvas = _source(CHAT_CANVAS)
    composer = _source(CHAT_COMPOSER)

    assert "RuntimeContextPanel" not in network
    assert "useUpdateNetworkRuntimeEnvironmentContext" not in network
    assert "externalContextContract={effectiveExternalContextContract}" in network
    assert "externalContextValues={externalContextValues}" in network
    assert "onExternalContextValuesChange={handleExternalContextValuesChange}" in network

    assert "externalContextContract={externalContextContract}" in canvas
    assert "externalContextValues={externalContextValues}" in canvas
    assert "onExternalContextValuesChange={onExternalContextValuesChange}" in canvas

    assert "External Context" in composer
    assert "Session fields are set once and reused automatically." in composer
    assert "Run fields may change on each Run." in composer


def test_network_chat_sends_working_external_context_instead_of_environment_state_directly() -> None:
    network = _source(NETWORK_CHAT)

    assert "externalContext: externalContextValues" in network
    assert "externalContext: runtimeExternalContext" not in network
    assert "const [externalContextValues, setExternalContextValues]" in network
    assert "externalContextDirtyRef.current = true" in network


def test_network_session_snapshot_locks_session_scoped_external_context() -> None:
    network = _source(NETWORK_CHAT)

    assert "const lockedExternalContextValues = activeSession?.externalContextSnapshot ?? {}" in network
    assert "session.externalContextSnapshot ?? {}" in network
    assert "filterExternalContextInput(" in network
    assert "lockedExternalContextValues={lockedExternalContextValues}" in network
    assert "external_context_session_values" not in network
    assert "externalContextOwnerRef.current = environment" in network


def test_network_acceptance_conflicts_refresh_persisted_session_locks() -> None:
    network = _source(NETWORK_CHAT)

    assert "toast.error(error instanceof Error ? error.message : 'Network execution failed')" in network
    assert "await refreshPersistedSession(session.id)" in network
    assert "if (executionId) await refreshPersistedSession(session.id)" not in network


def test_network_external_context_presets_are_environment_owned() -> None:
    network = _source(NETWORK_CHAT)

    assert "storedEnvironmentContext" in network
    assert "filterContractValues(" in network
    assert "previousEnvironment !== environment" in network
