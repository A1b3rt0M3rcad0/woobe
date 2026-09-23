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
NETWORK_PAGE = FRONTEND / "pages" / "NetworkPage.tsx"
NETWORK_AGENT_WORKSPACE = (
    FRONTEND / "features" / "network" / "components" / "NetworkAgentWorkspace.tsx"
)
NETWORK_HOOKS = FRONTEND / "features" / "network" / "hooks.ts"
AGENT_HOOKS = FRONTEND / "features" / "agents" / "hooks.ts"
NETWORK_OVERVIEW_INSPECTOR = (
    FRONTEND / "features" / "network" / "components" / "NetworkOverviewInspector.tsx"
)
NETWORK_AGENT_CHAT = (
    FRONTEND / "features" / "network" / "components" / "NetworkAgentChat.tsx"
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


def test_network_draft_external_context_tracks_live_agent_editor_state() -> None:
    network = _source(NETWORK_CHAT)
    page = _source(NETWORK_PAGE)
    workspace = _source(NETWORK_AGENT_WORKSPACE)

    assert "previewNetworkDraftExternalContextContract" in network
    assert "definition: draftDefinition" in network
    assert "liveDraftContractsByAgentId" in network
    assert "draftExternalContextContractsByAgentId" in page
    assert "onDraftExternalContextChange={updateSelectedAgentExternalContext}" in page
    assert "liveDraftContractsByAgentId={draftExternalContextContractsByAgentId}" in page
    assert "onDraftExternalContextChange?.(state.externalContextContract)" in workspace


def test_network_effective_external_context_cache_is_invalidated_by_contract_lifecycle_changes() -> None:
    network_hooks = _source(NETWORK_HOOKS)
    agent_hooks = _source(AGENT_HOOKS)

    assert "['network-external-context-contract', projectId, networkId, 'draft']" in network_hooks
    assert "['network-external-context-contract', projectId, networkId, input.environment]" in network_hooks
    assert network_hooks.count(
        "['network-external-context-contract', projectId, networkId, 'production']"
    ) >= 2
    assert "['network-external-context-contract', input.project_id]" in agent_hooks
    assert "['network-external-context-contract', agent.project_id]" in agent_hooks


def test_network_overview_uses_the_same_live_draft_external_context_preview() -> None:
    overview = _source(NETWORK_OVERVIEW_INSPECTOR)
    page = _source(NETWORK_PAGE)

    assert "previewNetworkDraftExternalContextContract" in overview
    assert "liveDraftContractsByAgentId" in overview
    assert "Object.entries(effectiveExternalContextContract)" in overview
    assert "liveDraftContractsByAgentId={draftExternalContextContractsByAgentId}" in page


def test_isolated_network_agent_chat_respects_external_context_and_technical_sessions() -> None:
    chat = _source(NETWORK_AGENT_CHAT)

    assert "filterExternalContextInput(" in chat
    assert "externalContextContract={externalContextContract}" in chat
    assert "lockedExternalContextValues={lockedExternalContextValues}" in chat
    assert "session_id: sessionId" in chat
    assert "session_id: isStateless ? null : sessionId" not in chat
    assert "Stateless Agents keep a technical Session but do not reuse conversation history" in chat
