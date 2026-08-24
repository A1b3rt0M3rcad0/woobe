from __future__ import annotations

from pathlib import Path
import re


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"replacement anchor not found in {path}: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def repair_rerun_contract() -> None:
    replace_once(
        "src/modules/agent/application/interfaces/agent_run_rerun.py",
        "class AgentRunExecutor(Protocol):\n    async def execute(self, input_dto: AskInput) -> AskOutput: ...\n",
        "class AgentRunExecutor(Protocol):\n    async def execute(self, input_dto: AskInput) -> AskOutput: ...\n\n\nclass AgentRunRerunExecutor(Protocol):\n    async def execute(self, *, run_id: UUID, project_id: UUID) -> AskOutput: ...\n",
    )
    replace_once(
        "src/modules/agent/presentation/controllers/rerun_agent_run_controller.py",
        "from modules.agent.application.use_cases.rerun_agent_run import RerunAgentRunUseCase\n",
        "from modules.agent.application.interfaces.agent_run_rerun import AgentRunRerunExecutor\n",
    )
    replace_once(
        "src/modules/agent/presentation/controllers/rerun_agent_run_controller.py",
        "    def __init__(self, use_case: RerunAgentRunUseCase) -> None:\n",
        "    def __init__(self, use_case: AgentRunRerunExecutor) -> None:\n",
    )

    path = Path("src/modules/agent/composition/composers/rerun_agent_run_composer.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace("from collections.abc import Awaitable, Callable", "from collections.abc import Callable")
    text = text.replace("from shared.presentation.http.request import Request\n", "")
    text = text.replace("from shared.presentation.http.response import Response\n", "")
    text = text.replace("\n\nRerunAgentRunHandler = Callable[[Request], Awaitable[Response]]\n", "")
    text = text.replace("def rerun_agent_run_composer() -> RerunAgentRunHandler:", "def rerun_agent_run_composer() -> Callable:")
    path.write_text(text, encoding="utf-8")


def repair_runtime_preparation_boundary() -> None:
    path = Path("src/modules/agent/infra/execution/runtime_preparation.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace("import re\n", "import re\nfrom collections.abc import Callable\n", 1)
    text, count = re.subn(
        r"from modules\.agent\.application\.tool_release_snapshots import \(\n(?:    .*\n)+?\)\n",
        "",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("runtime_preparation application snapshot import not found")

    secret_anchor = '_SECRET_PATTERN = re.compile(r"\\{\\{secret:([^}]+)\\}\\}")\n'
    if secret_anchor not in text:
        raise RuntimeError("runtime_preparation secret pattern anchor not found")
    text = text.replace(
        secret_anchor,
        secret_anchor
        + "\nToolFromSnapshot = Callable[[dict[str, Any]], Any]\n"
        + "ToolWithPermissions = Callable[[Any, Any], Any]\n"
        + "ToolToSnapshot = Callable[[Any], dict[str, Any]]\n",
        1,
    )
    old_signature = "async def prepare_tool_state(\n    repositories: AgentRuntimeRepositories,\n    *,\n    agent: Any,\n) -> tuple[list[Any], dict[str, str]]:"
    new_signature = "async def prepare_tool_state(\n    repositories: AgentRuntimeRepositories,\n    *,\n    agent: Any,\n    tool_from_snapshot: ToolFromSnapshot,\n    tool_with_permissions: ToolWithPermissions,\n) -> tuple[list[Any], dict[str, str]]:"
    if old_signature not in text:
        raise RuntimeError("prepare_tool_state signature anchor not found")
    text = text.replace(old_signature, new_signature, 1)
    text = text.replace("tool_from_release_snapshot(snapshot)", "tool_from_snapshot(snapshot)")
    text = text.replace("tool_with_permission_overrides(", "tool_with_permissions(")

    old_snapshot_signature = "    release_version: str | None,\n) -> dict[str, Any]:"
    new_snapshot_signature = "    release_version: str | None,\n    tool_to_snapshot: ToolToSnapshot,\n) -> dict[str, Any]:"
    if old_snapshot_signature not in text:
        raise RuntimeError("build_execution_snapshot signature anchor not found")
    text = text.replace(old_snapshot_signature, new_snapshot_signature, 1)
    text = text.replace(
        '        "tools": [tool_to_release_snapshot(tool) for tool in tools],',
        '        "tools": [tool_to_snapshot(tool) for tool in tools],',
        1,
    )
    if "modules.agent.application.tool_release_snapshots" in text:
        raise RuntimeError("runtime_preparation still imports Application snapshot implementation")
    path.write_text(text, encoding="utf-8")

    path = Path("src/modules/agent/infra/execution/explicit_runtime_persistence.py")
    text = path.read_text(encoding="utf-8")
    anchor = "from modules.agent.application.tool_converter import agent_tools_to_openai_definitions_and_mapping\n"
    snapshot_import = (
        anchor
        + "from modules.agent.application.tool_release_snapshots import (\n"
        + "    tool_from_release_snapshot,\n"
        + "    tool_to_release_snapshot,\n"
        + "    tool_with_permission_overrides,\n"
        + ")\n"
    )
    if "from modules.agent.application.tool_release_snapshots import" not in text:
        if anchor not in text:
            raise RuntimeError("explicit_runtime_persistence snapshot import anchor missing")
        text = text.replace(anchor, snapshot_import, 1)
    old_prepare = "            tools, encrypted_tool_secrets = await prepare_tool_state(\n                repositories,\n                agent=agent,\n            )"
    new_prepare = "            tools, encrypted_tool_secrets = await prepare_tool_state(\n                repositories,\n                agent=agent,\n                tool_from_snapshot=tool_from_release_snapshot,\n                tool_with_permissions=tool_with_permission_overrides,\n            )"
    if old_prepare not in text:
        raise RuntimeError("explicit_runtime_persistence prepare_tool_state call anchor missing")
    text = text.replace(old_prepare, new_prepare, 1)
    old_snapshot_call = "                        release_id=release_id,\n                        release_version=release_version,\n                    ),"
    new_snapshot_call = "                        release_id=release_id,\n                        release_version=release_version,\n                        tool_to_snapshot=tool_to_release_snapshot,\n                    ),"
    if old_snapshot_call not in text:
        raise RuntimeError("explicit_runtime_persistence build_execution_snapshot call anchor missing")
    text = text.replace(old_snapshot_call, new_snapshot_call, 1)
    path.write_text(text, encoding="utf-8")


def repair_vector_read_composition() -> None:
    Path("src/modules/agent/infra/database/runtime_vector_search_reader.py").write_text(
        '''from __future__ import annotations\n\nfrom uuid import UUID\n\nfrom modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner\n\n\nclass AgentRuntimeVectorSearchReader:\n    \"\"\"Short read-only pgvector access behind the runtime persistence boundary.\"\"\"\n\n    def __init__(self, transactions: AgentRuntimeTransactionRunner) -> None:\n        self._transactions = transactions\n\n    async def search(\n        self,\n        *,\n        vector_snapshot_id: UUID,\n        embedding: list[float],\n        limit: int,\n        threshold: float,\n    ):\n        async def read(repositories, _outbox):\n            return await repositories.vector_snapshots.search_similar(\n                vector_snapshot_id=vector_snapshot_id,\n                embedding=embedding,\n                limit=limit,\n                threshold=threshold,\n            )\n\n        return await self._transactions.read(read)\n''',
        encoding="utf-8",
    )

    path = Path("src/modules/agent/composition/factories/ask_agent_runtime_factory.py")
    text = path.read_text(encoding="utf-8")
    anchor = "from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner\n"
    if "runtime_vector_search_reader" not in text:
        if anchor not in text:
            raise RuntimeError("runtime transaction runner import anchor missing")
        text = text.replace(
            anchor,
            anchor + "from modules.agent.infra.database.runtime_vector_search_reader import AgentRuntimeVectorSearchReader\n",
            1,
        )
    pattern = re.compile(
        r"\n    async def search_vector_snapshot\(.*?\n    runtime\.configure_vector_search_reader\(search_vector_snapshot\)",
        re.S,
    )
    text, count = pattern.subn(
        "\n    runtime.configure_vector_search_reader(\n        AgentRuntimeVectorSearchReader(transactions).search\n    )",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("ask_agent_runtime_factory nested vector reader block not found")
    path.write_text(text, encoding="utf-8")


def repair_composer_contract() -> None:
    path = Path("quality_gate/architecture/policy.py")
    text = path.read_text(encoding="utf-8")
    old = "    uow_types: tuple[str, ...]\n    forbidden_parameter_types: tuple[str, ...] = ()\n"
    new = "    uow_types: tuple[str, ...]\n    long_lived_functions: tuple[str, ...] = ()\n    long_lived_handler: str = \"Callable\"\n    uow_factory_functions: tuple[str, ...] = ()\n    forbidden_parameter_types: tuple[str, ...] = ()\n"
    if old not in text:
        raise RuntimeError("ComposerContract field anchor missing")
    text = text.replace(old, new, 1)
    old = "        uow_types=uow_types,\n        forbidden_parameter_types="
    new = "        uow_types=uow_types,\n        long_lived_functions=_string_tuple(value.get(\"long_lived_functions\"), field=\"composer_contract.long_lived_functions\"),\n        long_lived_handler=str(value.get(\"long_lived_handler\") or \"Callable\"),\n        uow_factory_functions=_string_tuple(value.get(\"uow_factory_functions\"), field=\"composer_contract.uow_factory_functions\"),\n        forbidden_parameter_types="
    if old not in text:
        raise RuntimeError("ComposerContract loader anchor missing")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")

    path = Path("quality_gate/architecture/checker.py")
    text = path.read_text(encoding="utf-8")
    old = "def _uow_call(node: ast.AST | None, contract: ComposerContract) -> bool:\n    return _call_target(node) in set(contract.uow_types)\n"
    new = "def _uow_call(node: ast.AST | None, contract: ComposerContract) -> bool:\n    target = _call_target(node)\n    return target in set(contract.uow_types).union(contract.uow_factory_functions)\n"
    if old not in text:
        raise RuntimeError("_uow_call anchor missing")
    text = text.replace(old, new, 1)

    start = text.index("def _composer_violations(")
    end = text.index("\n\ndef _composer_function_names", start)
    current = text[start:end]
    current = current.replace(
        "        is_stream = function.name.endswith(contract.streaming_suffix)\n        expected_handler = contract.streaming_handler if is_stream else contract.regular_handler\n",
        "        is_long_lived = function.name in set(contract.long_lived_functions)\n        is_stream = function.name.endswith(contract.streaming_suffix)\n        expected_handler = (\n            contract.long_lived_handler\n            if is_long_lived\n            else contract.streaming_handler if is_stream else contract.regular_handler\n        )\n",
        1,
    )
    current = current.replace(
        '            rule = "ARCH023" if is_stream else "ARCH021"\n',
        '            rule = "ARCH020" if is_long_lived else "ARCH023" if is_stream else "ARCH021"\n',
        1,
    )
    old_returns = '''        if not inspector.returns:\n            violations.append(("ARCH022", function.lineno, f"{function.name} must return a transactional handler"))\n        else:\n            for return_node in inspector.returns:\n                returned_handler = _call_target(return_node.value)\n                if returned_handler not in contract.allowed_handlers:\n                    violations.append(("ARCH022", return_node.lineno, f"{function.name} cannot return a raw controller, use case or callable"))\n                elif returned_handler != expected_handler:\n                    rule = "ARCH023" if is_stream else "ARCH021"\n                    violations.append((rule, return_node.lineno, f"{function.name} must return {expected_handler}"))\n'''
    new_returns = '''        if not inspector.returns:\n            message = "direct callable" if is_long_lived else "transactional handler"\n            violations.append(("ARCH022", function.lineno, f"{function.name} must return a {message}"))\n        elif is_long_lived:\n            for return_node in inspector.returns:\n                if _call_target(return_node.value) in contract.allowed_handlers:\n                    violations.append(("ARCH020", return_node.lineno, f"{function.name} is long-lived and cannot return a transactional handler"))\n        else:\n            for return_node in inspector.returns:\n                returned_handler = _call_target(return_node.value)\n                if returned_handler not in contract.allowed_handlers:\n                    violations.append(("ARCH022", return_node.lineno, f"{function.name} cannot return a raw controller, use case or callable"))\n                elif returned_handler != expected_handler:\n                    rule = "ARCH023" if is_stream else "ARCH021"\n                    violations.append((rule, return_node.lineno, f"{function.name} must return {expected_handler}"))\n'''
    if old_returns not in current:
        raise RuntimeError("composer return block anchor missing")
    current = current.replace(old_returns, new_returns, 1)
    old_count = '''        if len(uow_assignments) != 1:\n            violations.append(("ARCH025", function.lineno, f"{function.name} must create exactly one configured UnitOfWork"))\n            continue\n\n        uow_name, uow_value, _ = uow_assignments[0]\n'''
    new_count = '''        if is_long_lived:\n            if uow_assignments:\n                violations.append(("ARCH025", function.lineno, f"{function.name} is long-lived and cannot create a global UnitOfWork"))\n            continue\n\n        if len(uow_assignments) != 1:\n            violations.append(("ARCH025", function.lineno, f"{function.name} must create exactly one configured UnitOfWork"))\n            continue\n\n        uow_name, uow_value, _ = uow_assignments[0]\n'''
    if old_count not in current:
        raise RuntimeError("composer UoW count block anchor missing")
    current = current.replace(old_count, new_count, 1)
    current = current.replace(
        "        if contract.uow_resource_names and isinstance(uow_value, ast.Call):\n",
        "        if (\n            contract.uow_resource_names\n            and isinstance(uow_value, ast.Call)\n            and _call_target(uow_value) in set(contract.uow_types)\n        ):\n",
        1,
    )
    text = text[:start] + current + text[end:]
    path.write_text(text, encoding="utf-8")

    path = Path("quality_gate/architecture/policies/agent.toml")
    text = path.read_text(encoding="utf-8")
    old = 'uow_types = ["AgentUnitOfWork"]\n'
    new = '''uow_types = ["AgentUnitOfWork"]\nuow_factory_functions = ["build_agent_uow"]\nlong_lived_handler = "Callable"\nlong_lived_functions = [\n  "ask_agent_composer",\n  "ask_agent_stream_composer",\n  "public_run_composer",\n  "public_stream_composer",\n  "rerun_agent_run_composer",\n]\n'''
    if old not in text:
        raise RuntimeError("agent composer policy anchor missing")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")

    path = Path("tests/quality_gate/architecture/test_strict_composer_contract.py")
    text = path.read_text(encoding="utf-8")
    old = 'uow_types = ["AgentUnitOfWork"]\n'
    new = 'uow_types = ["AgentUnitOfWork"]\nuow_factory_functions = ["build_agent_uow"]\nlong_lived_handler = "Callable"\nlong_lived_functions = ["ask_agent_composer"]\n'
    if old not in text:
        raise RuntimeError("strict composer policy anchor missing")
    text = text.replace(old, new, 1)
    text += '''\n\ndef test_long_lived_composer_returns_direct_callable_without_uow(tmp_path: Path) -> None:\n    checker, policy, root = _checker(tmp_path)\n    (root / "composition/composers/ask_agent.py").write_text(\n        "from collections.abc import Callable\\n"\n        "def ask_agent_composer() -> Callable:\\n"\n        "    return build_ask_agent_handler()\\n",\n        encoding="utf-8",\n    )\n    result = checker.check(policy)\n    assert result.passed, result.violations\n\n\ndef test_long_lived_composer_cannot_create_global_uow(tmp_path: Path) -> None:\n    checker, policy, root = _checker(tmp_path)\n    (root / "composition/composers/ask_agent.py").write_text(\n        "from collections.abc import Callable\\n"\n        "def ask_agent_composer() -> Callable:\\n"\n        "    uow = AgentUnitOfWork(DATABASE_ENGINE)\\n"\n        "    return build_ask_agent_handler()\\n",\n        encoding="utf-8",\n    )\n    result = checker.check(policy)\n    assert any(item.rule_id == "ARCH025" for item in result.violations)\n'''
    path.write_text(text, encoding="utf-8")


def main() -> None:
    repair_rerun_contract()
    repair_runtime_preparation_boundary()
    repair_vector_read_composition()
    repair_composer_contract()


if __name__ == "__main__":
    main()
