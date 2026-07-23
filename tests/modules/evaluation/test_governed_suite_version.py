from __future__ import annotations

from modules.evaluation.application.governed_experience_service import _next_version


def test_judge_model_change_increments_suite_version() -> None:
    assert _next_version("v1") == "v2"
    assert _next_version("v12") == "v13"


def test_invalid_legacy_version_starts_new_governed_sequence() -> None:
    assert _next_version(None) == "v1"
    assert _next_version("legacy") == "v1"
