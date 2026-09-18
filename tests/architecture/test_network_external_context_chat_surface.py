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
    assert "run + session" in composer


def test_network_chat_sends_working_external_context_instead_of_environment_state_directly() -> None:
    network = _source(NETWORK_CHAT)

    assert "externalContext: externalContextValues" in network
    assert "externalContext: runtimeExternalContext" not in network
    assert "const [externalContextValues, setExternalContextValues]" in network
    assert "externalContextDirtyRef.current = true" in network


def test_network_session_switching_preserves_run_values_and_hydrates_session_values() -> None:
    network = _source(NETWORK_CHAT)

    assert "contractForScope(effectiveExternalContextContract, 'run')" in network
    assert "contractForScope(effectiveExternalContextContract, 'session')" in network
    assert "activeSession?.externalContextSessionValues ?? {}" in network
    assert "...filterContractValues(runContextContract, currentValues)" in network
    assert "...sessionValues" in network


def test_first_network_session_binding_does_not_clear_values_entered_before_the_run() -> None:
    network = _source(NETWORK_CHAT)

    assert "automaticSessionBinding" in network
    assert "previousOwner === `${environment}:none`" in network
    assert "return contextDirty ? currentValues : baselineValues" in network
    assert "previousOwner !== owner && !automaticSessionBinding" in network
