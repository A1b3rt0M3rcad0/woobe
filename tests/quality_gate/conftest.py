from pathlib import Path
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(autouse=True)
def isolate_synthetic_responsibility_policies(request: pytest.FixtureRequest) -> None:
    """Keep temporary checker fixtures isolated from packaged repository policies."""
    if "tmp_path" not in request.fixturenames:
        return

    tmp_path = request.getfixturevalue("tmp_path")
    responsibility_dir = tmp_path / "quality_gate/architecture/responsibilities"
    responsibility_dir.mkdir(parents=True, exist_ok=True)
    fixture_policy = responsibility_dir / "agent.toml"
    if not fixture_policy.exists():
        fixture_policy.write_text("", encoding="utf-8")
