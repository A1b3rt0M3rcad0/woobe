from quality_gate.architecture.graph import strongly_connected_components


def test_strongly_connected_components_reports_only_cycles() -> None:
    graph = {
        "a.py": {"b.py"},
        "b.py": {"c.py"},
        "c.py": {"a.py"},
        "d.py": {"e.py"},
        "e.py": set(),
    }

    assert strongly_connected_components(graph) == (("a.py", "b.py", "c.py"),)


def test_self_cycle_is_reported() -> None:
    assert strongly_connected_components({"a.py": {"a.py"}}) == (("a.py",),)
