"""Integration tests for list_recent_by_session — spec 006.

These tests require a live database connection and are skipped by default.
Run with: pytest tests/modules/agent/integration -k "not placeholder"
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Requires a live database connection")


@pytest.mark.asyncio
async def test_recent_query_has_dual_ordering() -> None:
    """The recent query must use ORDER BY created_at DESC, id DESC."""
    assert True  # placeholder — needs DB


@pytest.mark.asyncio
async def test_recent_returns_most_recent_first_direction() -> None:
    """After reverse, messages must be in chronological order."""
    assert True  # placeholder — needs DB


@pytest.mark.asyncio
async def test_recent_empty_session_returns_empty() -> None:
    """A session with no messages must return an empty list."""
    assert True  # placeholder — needs DB
