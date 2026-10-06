from copy import deepcopy

import pytest

from modules.network.application.portable_definition import (
    inspect_portable_network_definition,
)


def test_portable_network_uses_native_graph_bounds_before_materialization():
    spec = {
        "root": "coordinator",
        "nodes": [
            {"key": "coordinator", "agent_ref": "coordinator", "label": "Coordinator"},
            {
                "key": "billing",
                "agent_ref": "billing",
                "label": "Billing",
                "binding": {"source": "release"},
            },
        ],
        "edges": [{"from": "coordinator", "to": "billing"}],
        "settings": {"max_depth": 4, "max_invocations": 16, "timeout_seconds": 90},
    }
    limits = {
        "hard_max_depth": 8,
        "hard_max_invocations": 64,
        "hard_timeout_seconds": 300,
    }
    report = inspect_portable_network_definition(spec, **limits)
    assert report["node_count"] == 2 and report["edge_count"] == 1
    changed = deepcopy(spec)
    changed["settings"]["max_invocations"] = 65
    with pytest.raises(ValueError):
        inspect_portable_network_definition(changed, **limits)
    cyclic = deepcopy(spec)
    cyclic["edges"].append({"from": "billing", "to": "coordinator"})
    with pytest.raises(ValueError):
        inspect_portable_network_definition(cyclic, **limits)
