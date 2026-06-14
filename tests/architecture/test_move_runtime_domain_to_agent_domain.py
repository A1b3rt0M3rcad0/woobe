import sys
import importlib
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_DOMAIN = PROJECT_ROOT / "src" / "modules" / "agent" / "domain"


class TestMoveRuntimeDomainToAgentDomain:
    def test_move_runtime_domain_to_agent_domain_success(self):
        entities_content = (AGENT_DOMAIN / "entities.py").read_text(encoding="utf-8")
        assert "class Session" in entities_content
        assert "class Message" in entities_content
        assert "class AskJob" in entities_content

        enums_content = (AGENT_DOMAIN / "enums.py").read_text(encoding="utf-8")
        assert "class SessionStatus" in enums_content
        assert "class MessageRole" in enums_content
        assert "class RuntimeSessionMode" in enums_content

        errors_content = (AGENT_DOMAIN / "errors.py").read_text(encoding="utf-8")
        assert "class SessionNotFoundError" in errors_content
        assert "class MessageNotFoundError" in errors_content
        assert "class AskJobNotFoundError" in errors_content

        repos_content = (AGENT_DOMAIN / "repositories.py").read_text(encoding="utf-8")
        assert "class SessionRepository" in repos_content
        assert "class MessageRepository" in repos_content
        assert "class AskJobRepository" in repos_content

    def test_move_runtime_domain_to_agent_domain_rejects_forbidden_dependency(self):
        entities_content = (AGENT_DOMAIN / "entities.py").read_text(encoding="utf-8")
        assert "from modules.runtime" not in entities_content, (
            "agent/domain/entities.py must not import from modules.runtime"
        )

        enums_content = (AGENT_DOMAIN / "enums.py").read_text(encoding="utf-8")
        assert "from modules.runtime" not in enums_content, (
            "agent/domain/enums.py must not import from modules.runtime"
        )

        errors_content = (AGENT_DOMAIN / "errors.py").read_text(encoding="utf-8")
        assert "from modules.runtime" not in errors_content, (
            "agent/domain/errors.py must not import from modules.runtime"
        )

        repos_content = (AGENT_DOMAIN / "repositories.py").read_text(encoding="utf-8")
        assert "from modules.runtime" not in repos_content, (
            "agent/domain/repositories.py must not import from modules.runtime"
        )

    def test_move_runtime_domain_to_agent_domain_keeps_legacy_compatibility(self):
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("modules.runtime.domain"):
                del sys.modules[mod_name]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            import modules.runtime.domain.entities as rt_entities
            importlib.reload(rt_entities)
            import modules.runtime.domain.enums as rt_enums
            importlib.reload(rt_enums)
            import modules.runtime.domain.errors as rt_errors
            importlib.reload(rt_errors)
            import modules.runtime.domain.repositories as rt_repos
            importlib.reload(rt_repos)

        deprecation_messages = [str(warning.message) for warning in w
                                if issubclass(warning.category, DeprecationWarning)]

        assert len(deprecation_messages) >= 1, (
            f"Expected at least 1 deprecation warning from runtime.domain shims, "
            f"got {len(deprecation_messages)}: {deprecation_messages}"
        )

        assert hasattr(rt_entities, "Session")
        assert hasattr(rt_entities, "Message")
        assert hasattr(rt_entities, "AskJob")
        assert hasattr(rt_enums, "SessionStatus")
        assert hasattr(rt_enums, "MessageRole")
        assert hasattr(rt_enums, "SessionMode")
        assert hasattr(rt_errors, "SessionNotFoundError")
        assert hasattr(rt_errors, "MessageNotFoundError")
        assert hasattr(rt_errors, "AskJobNotFoundError")
        assert hasattr(rt_repos, "SessionRepository")
        assert hasattr(rt_repos, "MessageRepository")
        assert hasattr(rt_repos, "AskJobRepository")
