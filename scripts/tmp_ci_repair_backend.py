from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"replacement anchor not found in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def repair_deferred_tool_preparation() -> None:
    path = Path("src/modules/agent/infra/execution/transaction_bounded_structured_output.py")
    text = path.read_text(encoding="utf-8")
    import_anchor = (
        "from modules.agent.application.tool_converter import "
        "agent_tools_to_openai_definitions_and_mapping\n"
    )
    snapshot_import = (
        import_anchor
        + "from modules.agent.application.tool_release_snapshots import (\n"
        + "    tool_from_release_snapshot,\n"
        + "    tool_with_permission_overrides,\n"
        + ")\n"
    )
    if "from modules.agent.application.tool_release_snapshots import" not in text:
        if import_anchor not in text:
            raise RuntimeError("transaction runtime Tool snapshot import anchor missing")
        text = text.replace(import_anchor, snapshot_import, 1)

    old_call = (
        "            tools, encrypted_tool_secrets = await prepare_tool_state("
        "repositories, agent=agent)"
    )
    new_call = (
        "            tools, encrypted_tool_secrets = await prepare_tool_state(\n"
        "                repositories,\n"
        "                agent=agent,\n"
        "                tool_from_snapshot=tool_from_release_snapshot,\n"
        "                tool_with_permissions=tool_with_permission_overrides,\n"
        "            )"
    )
    if old_call not in text:
        raise RuntimeError("deferred prepare_tool_state call anchor missing")
    path.write_text(text.replace(old_call, new_call, 1), encoding="utf-8")


def repair_runtime_failure_exception() -> None:
    replace_once(
        "src/modules/network/application/runtime_failures.py",
        "@dataclass(frozen=True)\nclass NetworkRuntimeFailure(RuntimeError):",
        "@dataclass\nclass NetworkRuntimeFailure(RuntimeError):",
    )


def repair_network_test_bindings() -> None:
    path = Path("tests/unit/network/test_network_stream_visibility.py")
    text = path.read_text(encoding="utf-8")
    old = (
        '            str(root_node_id): {"release_id": str(uuid4())},\n'
        '            str(child_node_id): {"release_id": str(uuid4())},\n'
    )
    new = (
        '            str(root_node_id): {\n'
        '                "release_id": str(uuid4()),\n'
        '                "session_mode": "stateless",\n'
        '            },\n'
        '            str(child_node_id): {\n'
        '                "release_id": str(uuid4()),\n'
        '                "session_mode": "stateless",\n'
        '            },\n'
    )
    if old not in text:
        raise RuntimeError("network stream resolved binding anchor missing")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

    path = Path("tests/unit/network/test_structured_delegation.py")
    text = path.read_text(encoding="utf-8")
    first = (
        '                "release_id": str(root_release_id),\n'
        '                "release_version": "v1.0.20260715.01",\n'
    )
    first_new = first + '                "session_mode": "stateless",\n'
    second = (
        '                "release_id": str(specialist_release_id),\n'
        '                "release_version": "v1.0.20260715.01",\n'
    )
    second_new = second + '                "session_mode": "stateless",\n'
    if first not in text or second not in text:
        raise RuntimeError("structured delegation resolved binding anchor missing")
    text = text.replace(first, first_new, 1).replace(second, second_new, 1)
    path.write_text(text, encoding="utf-8")


def main() -> None:
    repair_deferred_tool_preparation()
    repair_runtime_failure_exception()
    repair_network_test_bindings()


if __name__ == "__main__":
    main()
