from pathlib import Path

INVENTORY_DIR = Path(__file__).resolve().parents[2] / "specs" / "execution" / "inventory"
RUNTIME_TO_AGENT_MAP = INVENTORY_DIR / "runtime-to-agent-map.md"

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
    "src/modules/runtime/",
    "src/modules/agent/",
    "entities.py",
    "repositories.py",
    "use_cases.py",
    "models.py",
    "routes.py",
]


class TestMapRuntimeToAgent:
    def test_map_runtime_to_agent_success(self):
        assert RUNTIME_TO_AGENT_MAP.exists(), (
            f"Runtime-to-agent map file not found: {RUNTIME_TO_AGENT_MAP}"
        )

        content = RUNTIME_TO_AGENT_MAP.read_text(encoding="utf-8")

        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 50, (
            "Runtime-to-agent map must contain comprehensive mapping entries. "
            f"Found only {len(lines)} non-header lines."
        )

        for section in REQUIRED_SECTIONS:
            assert section in content, (
                f"Runtime-to-agent map must contain section: '{section}'"
            )

        for marker in REQUIRED_EVIDENCE_MARKERS:
            assert marker in content, (
                f"Runtime-to-agent map must reference: '{marker}'"
            )

        assert "modules.runtime.domain" in content or "src/modules/runtime/domain" in content, (
            "Map must reference runtime domain layer origin"
        )
        assert "modules.agent.domain" in content or "src/modules/agent/domain" in content, (
            "Map must reference agent domain layer destination"
        )

    def test_map_runtime_to_agent_rejects_forbidden_dependency(self):
        assert RUNTIME_TO_AGENT_MAP.exists(), (
            f"Runtime-to-agent map file not found: {RUNTIME_TO_AGENT_MAP}"
        )

        content = RUNTIME_TO_AGENT_MAP.read_text(encoding="utf-8")

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

    def test_map_runtime_to_agent_keeps_legacy_compatibility(self):
        assert RUNTIME_TO_AGENT_MAP.exists(), (
            f"Runtime-to-agent map file not found: {RUNTIME_TO_AGENT_MAP}"
        )

        content = RUNTIME_TO_AGENT_MAP.read_text(encoding="utf-8")

        assert "shim" in content.lower() or "compatibility" in content.lower(), (
            "Map must reference shim/compatibility strategy for legacy routes"
        )

        assert "142" in content, (
            "Map must reference deprecation/removal specs (142) for legacy runtime cleanup"
        )

        forbidden_removal_phrases = [
            "remove src/modules/runtime",
            "delete src/modules/runtime",
            "rm -rf src/modules/runtime",
        ]
        for phrase in forbidden_removal_phrases:
            assert phrase not in content.lower(), (
                f"Map must NOT recommend removing legacy runtime module. Found: '{phrase}'"
            )
