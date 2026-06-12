from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parents[2] / "specs"
ADR_FILE = SPECS_DIR / "000-architecture-decision-record-agent-bounded-context.md"


class TestArchitectureDecisionRecordAgentBoundedContext:
    def test_architecture_decision_record_agent_bounded_context_success(self):
        assert ADR_FILE.exists(), f"ADR file not found: {ADR_FILE}"

        content = ADR_FILE.read_text(encoding="utf-8")

        assert "accepted" in content.lower(), "ADR status must be 'accepted'"

        assert "agent" in content.lower(), "ADR must reference 'agent' bounded context"

        assert (
            "ai" in content and "knowledge" in content and "runtime" in content
        ), "ADR must reference all three legacy modules: ai, knowledge, runtime"

        assert (
            "Outbox" in content or "outbox" in content
        ), "ADR must reference Outbox pattern"

        assert (
            "Inbox" in content or "inbox" in content
        ), "ADR must reference Inbox pattern"

        assert (
            "modular monolith" in content.lower() or "modular-monolith" in content.lower()
        ), "ADR must reference modular monolith architecture"

    def test_architecture_decision_record_agent_bounded_context_rejects_forbidden_dependency(self):
        content = ADR_FILE.read_text(encoding="utf-8")

        rejected_alternatives = [
            "manter três bounded contexts",
            "microservices",
            "EventBus genérico",
            "workers concretos globais",
        ]

        for alternative in rejected_alternatives:
            assert (
                alternative.lower() in content.lower()
            ), f"ADR must explicitly reject alternative: '{alternative}'"

        forbidden_patterns = [
            "comunicação síncrona direta entre módulos",
        ]

        for pattern in forbidden_patterns:
            assert (
                pattern.lower() in content.lower()
            ), f"ADR must explicitly forbid: '{pattern}'"
