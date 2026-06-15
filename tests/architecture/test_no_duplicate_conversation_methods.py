"""Architecture test: no duplicate conversation context methods.

After spec 007, private methods for session resolution, history loading,
message saving, prompt building, and history limit must not be duplicated
between sync and stream use cases. They must live in ConversationContextBuilder.
"""

from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parents[2]

FORBIDDEN_METHODS = [
    "_resolve_session",
    "_load_history",
    "_save_user_message",
    "_build_messages",
    "_get_history_limit",
]

USE_CASE_FILES = [
    "src/modules/agent/application/use_cases/ask_use_case.py",
    "src/modules/agent/application/use_cases/ask_agent_stream_service.py",
]


def _find_method_defs(filepath: Path, method_name: str) -> list[str]:
    """Find method definition lines in a file."""
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()
    matches = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"def {method_name}(") or stripped.startswith(f"async def {method_name}("):
            matches.append(f"  {filepath.name}:{i + 1}: {stripped}")
    return matches


@pytest.mark.parametrize("method_name", FORBIDDEN_METHODS)
def test_duplicate_method_removed(method_name: str) -> None:
    """A forbidden method must not appear in any use case file."""
    violations: list[str] = []
    for rel_path in USE_CASE_FILES:
        full_path = BASE / rel_path
        matches = _find_method_defs(full_path, method_name)
        violations.extend(matches)
    assert not violations, (
        f"Method '{method_name}' must not exist in use case files "
        f"(extracted to ConversationContextBuilder). Found:\n" + "\n".join(violations)
    )
