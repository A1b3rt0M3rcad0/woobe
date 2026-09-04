from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_EXECUTION = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "agent"
    / "infra"
    / "execution"
)
_DEFAULT_ASSEMBLER_MODULE = "modules.agent.application.default_context_assembler"
_LEGACY_ASSEMBLY_MODULE = "modules.agent.application.context_assembly"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_agent_execution_depends_on_context_assembler_contract_not_default() -> None:
    violations: list[str] = []

    for path in AGENT_EXECUTION.rglob("*.py"):
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom):
                if node.module == _DEFAULT_ASSEMBLER_MODULE:
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} imports DefaultContextAssembler"
                    )
                if node.module == _LEGACY_ASSEMBLY_MODULE and any(
                    alias.name == "assemble_context" for alias in node.names
                ):
                    violations.append(
                        f"{path.relative_to(ROOT).as_posix()} imports assemble_context directly"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == _DEFAULT_ASSEMBLER_MODULE:
                        violations.append(
                            f"{path.relative_to(ROOT).as_posix()} imports DefaultContextAssembler"
                        )

    assert not violations, "\n".join(violations)
