import ast
import warnings
from pathlib import Path

AGENT_LLM_DIR = Path(__file__).resolve().parents[2] / "src" / "modules" / "agent" / "infra" / "llm"

FORBIDDEN_IMPORT_PREFIXES = [
    "modules.ai",
    "modules.runtime",
    "modules.knowledge",
]


class TestMoveAiInfraLlmToAgentInfraLlm:
    def test_move_ai_infra_llm_to_agent_infra_llm_success(self):
        langchain_factory_file = AGENT_LLM_DIR / "langchain_factory.py"
        assert langchain_factory_file.exists(), (
            f"Agent infra LLM langchain_factory.py missing: {langchain_factory_file}"
        )

        from modules.agent.infra.llm.langchain_factory import create_chat_model

        assert callable(create_chat_model), (
            "create_chat_model must be callable"
        )

    def test_move_ai_infra_llm_to_agent_infra_llm_rejects_forbidden_dependency(self):
        llm_files = [
            AGENT_LLM_DIR / "langchain_factory.py",
        ]

        for filepath in llm_files:
            assert filepath.exists(), f"Agent infra LLM file missing: {filepath}"
            source = filepath.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(filepath))

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for prefix in FORBIDDEN_IMPORT_PREFIXES:
                        assert not node.module.startswith(prefix), (
                            f"Forbidden import '{node.module}' in {filepath.name}. "
                            f"Agent infra/llm must not import from legacy modules."
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        for prefix in FORBIDDEN_IMPORT_PREFIXES:
                            assert not alias.name.startswith(prefix), (
                                f"Forbidden import '{alias.name}' in {filepath.name}. "
                                f"Agent infra/llm must not import from legacy modules."
                            )

    def test_move_ai_infra_llm_to_agent_infra_llm_keeps_legacy_compatibility(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            from modules.ai.infra.llm import langchain_factory as ai_llm

        deprecation_messages = [str(warning.message) for warning in w
                                if issubclass(warning.category, DeprecationWarning)]

        assert len(deprecation_messages) >= 1, (
            f"Expected at least 1 deprecation warning from ai.infra.llm shim, "
            f"got {len(deprecation_messages)}: {deprecation_messages}"
        )

        assert hasattr(ai_llm, "create_chat_model"), (
            "Legacy shim ai.infra.llm.langchain_factory must export create_chat_model"
        )

        from modules.agent.infra.llm.langchain_factory import create_chat_model as agent_fn
        assert ai_llm.create_chat_model is agent_fn, (
            "Shim must delegate to agent infra/llm, not duplicate the function"
        )
