from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_RUNTIME = ROOT / "packages/woobe-frontend/src/lib/runtime-stream.ts"
FRONTEND_AGENT = ROOT / "packages/woobe-frontend/src/features/playground/stream-client.ts"
FRONTEND_NETWORK = ROOT / "packages/woobe-frontend/src/features/network/stream.ts"
EMBED_RUNTIME = ROOT / "packages/woobe-embed/src/runtime-stream.ts"
EMBED_IFRAME = ROOT / "packages/woobe-embed/src/iframe.ts"

_REQUIRED_RUNTIME_EXPORTS = {
    "RUNTIME_STREAM_MAX_ATTEMPTS",
    "RuntimeStreamGapError",
    "RuntimeStreamProtocolError",
    "parseRuntimeFrame",
    "acceptRuntimeFrameSequence",
    "reconcileRuntimeOutput",
    "runtimeRetryDelayMs",
    "runtimeTerminalStatus",
}


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_frontend_and_embed_expose_the_same_runtime_protocol_primitives() -> None:
    frontend = _source(FRONTEND_RUNTIME)
    embed = _source(EMBED_RUNTIME)

    for name in _REQUIRED_RUNTIME_EXPORTS:
        assert name in frontend
        assert name in embed

    assert "SUPPORTED_RUNTIME_STREAM_PROTOCOL_VERSION = 1" in frontend
    assert "SUPPORTED_RUNTIME_STREAM_PROTOCOL_VERSION = 1" in embed
    assert "RUNTIME_STREAM_RETRY_BASE_MS = 250" in frontend
    assert "RUNTIME_STREAM_RETRY_BASE_MS = 250" in embed
    assert "realtime_available" in frontend
    assert "realtime_available" in embed


def test_frontend_agent_and_network_consume_the_canonical_runtime_protocol() -> None:
    for path in (FRONTEND_AGENT, FRONTEND_NETWORK):
        source = _source(path)
        assert "@/lib/runtime-stream" in source
        assert "parseRuntimeFrame" in source
        assert "acceptRuntimeFrameSequence" in source
        assert "reconcileRuntimeOutput" in source
        assert "runtimeRetryDelayMs" in source
        assert "RUNTIME_STREAM_MAX_ATTEMPTS" in source
        assert "runtimeTerminalStatus" in source
        assert "TERMINAL_RUN_STATUSES" not in source
        assert "Runtime stream sequence gap: expected" not in source
        assert "Network stream sequence gap: expected" not in source
        assert "250 * (attempt + 1)" not in source


def test_embed_consumes_its_canonical_runtime_protocol_module() -> None:
    source = _source(EMBED_IFRAME)
    assert 'from "./runtime-stream"' in source
    assert "acceptRuntimeFrameSequence" in source
    assert "parseRuntimeFrame" in source
    assert "runtimeTerminalStatus" in source


def test_runtime_gap_algorithm_is_owned_only_by_protocol_modules() -> None:
    canonical_gap_fragment = "const expected = state.sequence + 1"
    assert canonical_gap_fragment in _source(FRONTEND_RUNTIME)
    assert canonical_gap_fragment in _source(EMBED_RUNTIME)
    assert canonical_gap_fragment not in _source(FRONTEND_AGENT)
    assert canonical_gap_fragment not in _source(FRONTEND_NETWORK)
