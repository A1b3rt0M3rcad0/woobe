from pathlib import Path

import pytest

from quality_gate.architecture.policy import PolicyError, load_policy


def test_load_policy_preserves_rule_order(tmp_path: Path) -> None:
    policy_file = tmp_path / "agent.toml"
    policy_file.write_text(
        """
[module]
name = "agent"
root = "src/modules/agent"
package = "modules.agent"
required_layers = ["domain", "application", "infra", "presentation", "composition"]

[[rules]]
id = "ARCH006"
description = "routes"
source = ["presentation/routes.py"]
allow = ["modules.agent.composition"]

[[rules]]
id = "ARCH010"
description = "presentation"
source = ["presentation/**"]
allow = ["modules.agent.presentation"]
""".strip(),
        encoding="utf-8",
    )

    policy = load_policy(policy_file, project_root=tmp_path)

    assert policy.name == "agent"
    assert policy.rule_for("presentation/routes.py").rule_id == "ARCH006"
    assert policy.rule_for("presentation/controllers/create.py").rule_id == "ARCH010"


def test_load_policy_rejects_duplicate_rule_ids(tmp_path: Path) -> None:
    policy_file = tmp_path / "broken.toml"
    policy_file.write_text(
        """
[module]
name = "agent"
root = "src/modules/agent"
package = "modules.agent"
required_layers = ["domain"]

[[rules]]
id = "ARCH001"
description = "one"
source = ["domain/**"]

[[rules]]
id = "ARCH001"
description = "two"
source = ["application/**"]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(PolicyError, match="duplicate rule id"):
        load_policy(policy_file)
