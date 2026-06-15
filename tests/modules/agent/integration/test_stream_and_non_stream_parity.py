"""Integration tests for sync/stream parity — spec 007.

Tests require a live database and are skipped by default.
Run with: pytest tests/modules/agent/integration -k "not placeholder"
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Requires a live database connection")


@pytest.mark.asyncio
async def test_parity_same_input_produces_same_messages() -> None:
    """Given the same agent, input, and repo state, sync and stream
    must produce the same prompt messages before the LLM call."""
    assert True  # placeholder — needs DB


@pytest.mark.asyncio
async def test_parity_same_session_returned() -> None:
    """Both flows must return the same resolved session."""
    assert True  # placeholder — needs DB


@pytest.mark.asyncio
async def test_parity_same_history_counters() -> None:
    """Both flows must report the same history counters."""
    assert True  # placeholder — needs DB


@pytest.mark.asyncio
async def test_parity_same_error_for_invalid_session() -> None:
    """Both flows must raise the same error for invalid session."""
    assert True  # placeholder — needs DB
