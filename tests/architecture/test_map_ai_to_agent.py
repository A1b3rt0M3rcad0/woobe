from pathlib import Path

INVENTORY_DIR = Path(__file__).resolve().parents[2] / "specs" / "execution" / "inventory"
AI_TO_AGENT_MAP = INVENTORY_DIR / "ai-to-agent-map.md"

FORBIDDEN_DESTINATIONS = [
    "src/shared/domain/",
    "src/shared/application/",
    "src/workers/",
]

REQUIRED_SECTIONS = [
    "Domain Layer",
    "Application Layer",
    "Service Layer",
    "Infra Layer",
    "Presentation Layer",
    "Database Tables",
    "Events Produced",
    "External Consumers",
    "Risk Summary",
    "Migration Order",
]

REQUIRED_EVIDENCE_MARKERS = [
    "src/modules/ai/",
    "src/modules/agent/",
    "entities.py",
    "repositories.py",
    "use_cases.py",
    "models.py",
    "routes.py",
    "langchain_factory.py",
]


class TestMapAiToAgent:
    def test_map_ai_to_agent_success(self):
        assert AI_TO_AGENT_MAP.exists(), (
            f"AI-to-agent map file not found: {AI_TO_AGENT_MAP}"
        )

        content = AI_TO_AGENT_MAP.read_text(encoding="utf-8")

        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 50, (
            "AI-to-agent map must contain comprehensive mapping entries. "
            f"Found only {len(lines)} non-header lines."
        )

        for section in REQUIRED_SECTIONS:
            assert section in content, (
                f"AI-to-agent map must contain section: '{section}'"
            )

        for marker in REQUIRED_EVIDENCE_MARKERS:
            assert marker in content, (
                f"AI-to-agent map must reference: '{marker}'"
            )

        assert "modules.ai.domain" in content or "src/modules/ai/domain" in content, (
            "Map must reference ai domain layer origin"
        )
        assert "modules.agent.domain" in content or "src/modules/agent/domain" in content, (
            "Map must reference agent domain layer destination"
        )

    def test_map_ai_to_agent_rejects_forbidden_dependency(self):
        assert AI_TO_AGENT_MAP.exists(), (
            f"AI-to-agent map file not found: {AI_TO_AGENT_MAP}"
        )

        content = AI_TO_AGENT_MAP.read_text(encoding="utf-8")

        for line in content.splitlines():
            if "|" not in line:
                continue
            if "Destination" in line or "Origin" in line:
                continue
            columns = [col.strip() for col in line.split("|")]
            if len(columns) > 3:
                dest_col = columns[2]
                for destination in FORBIDDEN_DESTINATIONS:
                    assert destination not in dest_col, (
                        f"Forbidden destination '{destination}' found in map: {line.strip()}"
                    )

        assert "No physical file" in content or "não deve ser movido" in content, (
            "Map must explicitly state that no physical files are moved in this spec"
        )

    def test_map_ai_to_agent_keeps_legacy_compatibility(self):
        assert AI_TO_AGENT_MAP.exists(), (
            f"AI-to-agent map file not found: {AI_TO_AGENT_MAP}"
        )

        content = AI_TO_AGENT_MAP.read_text(encoding="utf-8")

        assert "shim" in content.lower() or "compatibility" in content.lower(), (
            "Map must reference shim/compatibility strategy for legacy routes"
        )

        assert "140" in content or "141" in content, (
            "Map must reference deprecation/removal specs (140+) for legacy cleanup"
        )

        forbidden_removal_phrases = [
            "remove src/modules/ai",
            "delete src/modules/ai",
            "rm -rf src/modules/ai",
        ]
        for phrase in forbidden_removal_phrases:
            assert phrase not in content.lower(), (
                f"Map must NOT recommend removing legacy ai module. Found: '{phrase}'"
            )
