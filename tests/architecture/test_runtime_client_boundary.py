from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME_CLIENT = ROOT / "packages/woobe-runtime-client"
RUNTIME_PROTOCOL = RUNTIME_CLIENT / "src/protocol.ts"
RUNTIME_SSE = RUNTIME_CLIENT / "src/sse.ts"
RUNTIME_OBSERVER = RUNTIME_CLIENT / "src/observer.ts"
RUNTIME_INDEX = RUNTIME_CLIENT / "src/index.ts"
FRONTEND_RUNTIME = ROOT / "packages/woobe-frontend/src/lib/runtime-stream.ts"
FRONTEND_AGENT = ROOT / "packages/woobe-frontend/src/features/playground/stream-client.ts"
FRONTEND_NETWORK = ROOT / "packages/woobe-frontend/src/features/network/stream.ts"
EMBED_RUNTIME = ROOT / "packages/woobe-embed/src/runtime-stream.ts"
EMBED_IFRAME = ROOT / "packages/woobe-embed/src/iframe.ts"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runtime_client_is_a_dedicated_ui_agnostic_package() -> None:
    assert (RUNTIME_CLIENT / "package.json").is_file()
    assert (RUNTIME_CLIENT / "tsconfig.json").is_file()
    for path in (RUNTIME_PROTOCOL, RUNTIME_SSE, RUNTIME_OBSERVER, RUNTIME_INDEX):
        assert path.is_file()

    combined = "\n".join(
        _source(path)
        for path in (RUNTIME_PROTOCOL, RUNTIME_SSE, RUNTIME_OBSERVER, RUNTIME_INDEX)
    )
    for forbidden in ("react", "canvas", "xyflow", "ChatUi", "NetworkRuntimeEvent"):
        assert forbidden not in combined


def test_frontend_and_embed_do_not_own_runtime_protocol_algorithms() -> None:
    expected_reexport = "export * from '@woobe/runtime-client'"
    assert _source(FRONTEND_RUNTIME).strip() == expected_reexport
    assert _source(EMBED_RUNTIME).strip() == expected_reexport

    canonical_gap_fragment = "const expected = state.sequence + 1"
    assert canonical_gap_fragment in _source(RUNTIME_PROTOCOL)
    assert canonical_gap_fragment not in _source(FRONTEND_RUNTIME)
    assert canonical_gap_fragment not in _source(EMBED_RUNTIME)


def test_runtime_client_owns_protocol_sequence_terminal_output_and_retry_policy() -> None:
    combined = "\n".join(
        _source(path) for path in (RUNTIME_PROTOCOL, RUNTIME_SSE, RUNTIME_OBSERVER)
    )
    for required in (
        "RUNTIME_STREAM_PROTOCOL_VERSION = 1",
        "RUNTIME_STREAM_MAX_ATTEMPTS = 4",
        "RUNTIME_STREAM_RETRY_BASE_MS = 250",
        "RuntimeStreamGapError",
        "RuntimeStreamProtocolError",
        "parseRuntimeFrame",
        "acceptRuntimeFrameSequence",
        "reconcileRuntimeOutput",
        "runtimeRetryDelayMs",
        "runtimeTerminalStatus",
        "realtime_available",
    ):
        assert required in combined


def test_frontend_agent_and_network_consume_runtime_through_thin_adapter() -> None:
    for path in (FRONTEND_AGENT, FRONTEND_NETWORK):
        source = _source(path)
        assert "@/lib/runtime-stream" in source
        assert "acceptRuntimeFrameSequence" in source
        assert "reconcileRuntimeOutput" in source
        assert "runtimeRetryDelayMs" in source
        assert "RUNTIME_STREAM_MAX_ATTEMPTS" in source
        assert "runtimeTerminalStatus" in source
        assert "TERMINAL_RUN_STATUSES" not in source
        assert "Runtime stream sequence gap: expected" not in source
        assert "Network stream sequence gap: expected" not in source
        assert "250 * (attempt + 1)" not in source


def test_embed_consumes_runtime_through_thin_adapter() -> None:
    source = _source(EMBED_IFRAME)
    assert 'from "./runtime-stream"' in source
    assert "acceptRuntimeFrameSequence" in source
    assert "parseRuntimeFrame" in source
    assert "runtimeTerminalStatus" in source
