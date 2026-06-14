import sys
import importlib
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_APP = PROJECT_ROOT / "src" / "modules" / "agent" / "application"


class TestMoveRuntimeApplicationToAgentApplication:
    def test_move_runtime_application_to_agent_application_success(self):
        dtos_file = AGENT_APP / "dtos" / "runtime_dtos.py"
        assert dtos_file.exists(), f"Missing: {dtos_file}"
        dtos_content = dtos_file.read_text(encoding="utf-8")
        assert "class CreateSessionInput" in dtos_content
        assert "class AskInput" in dtos_content
        assert "class AskOutput" in dtos_content

        use_cases_file = AGENT_APP / "use_cases" / "runtime_use_cases.py"
        assert use_cases_file.exists(), f"Missing: {use_cases_file}"
        uc_content = use_cases_file.read_text(encoding="utf-8")
        assert "class CreateSessionUseCase" in uc_content
        assert "class SendMessageUseCase" in uc_content
        assert "class ListMessagesUseCase" in uc_content

        ask_file = AGENT_APP / "use_cases" / "ask_use_case.py"
        assert ask_file.exists(), f"Missing: {ask_file}"
        ask_content = ask_file.read_text(encoding="utf-8")
        assert "class AskAgentUseCase" in ask_content

        stream_file = AGENT_APP / "use_cases" / "ask_agent_stream_service.py"
        assert stream_file.exists(), f"Missing: {stream_file}"
        stream_content = stream_file.read_text(encoding="utf-8")
        assert "class AskAgentStreamService" in stream_content

        composers_dir = AGENT_APP / "composers"
        expected_composers = [
            "ask_agent_composer.py",
            "ask_agent_stream_composer.py",
            "create_ask_job_composer.py",
            "create_session_composer.py",
            "get_ask_job_composer.py",
            "list_agent_sessions_composer.py",
            "list_messages_composer.py",
            "send_message_composer.py",
        ]
        for composer in expected_composers:
            assert (composers_dir / composer).exists(), f"Missing composer: {composer}"

    def test_move_runtime_application_to_agent_application_rejects_forbidden_dependency(self):
        dtos_content = (AGENT_APP / "dtos" / "runtime_dtos.py").read_text(encoding="utf-8")
        assert "from modules.runtime.domain" not in dtos_content, (
            "agent DTOs must not import from modules.runtime.domain (should use agent.domain)"
        )

        uc_content = (AGENT_APP / "use_cases" / "runtime_use_cases.py").read_text(encoding="utf-8")
        assert "from modules.runtime.domain" not in uc_content, (
            "agent use_cases must not import from modules.runtime.domain (should use agent.domain)"
        )

    def test_move_runtime_application_to_agent_application_keeps_legacy_compatibility(self):
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("modules.runtime.service"):
                del sys.modules[mod_name]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            import modules.runtime.service.dtos as rt_dtos
            importlib.reload(rt_dtos)
            import modules.runtime.service.use_cases as rt_uc
            importlib.reload(rt_uc)

        deprecation_messages = [str(warning.message) for warning in w
                                if issubclass(warning.category, DeprecationWarning)]

        assert len(deprecation_messages) >= 1, (
            f"Expected deprecation warnings from runtime.service shims, "
            f"got {len(deprecation_messages)}"
        )

        assert hasattr(rt_dtos, "CreateSessionInput")
        assert hasattr(rt_dtos, "AskInput")
        assert hasattr(rt_uc, "CreateSessionUseCase")
        assert hasattr(rt_uc, "SendMessageUseCase")
