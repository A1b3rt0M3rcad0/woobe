from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parents[2] / "specs" / "module-architecture-standardization"
ADR_FILE = SPECS_DIR / "000-architecture-decision-record-canonical-module-architecture.md"

TARGET_MODULES = {
    "agent",
    "identity",
    "core",
    "billing",
    "metering",
    "observability",
    "tools",
}


class TestCanonicalModuleAdr:
    def test_canonical_module_adr_exists(self):
        assert ADR_FILE.exists(), f"ADR file not found: {ADR_FILE}"

        content = ADR_FILE.read_text(encoding="utf-8")

        assert "accepted" in content.lower(), "ADR status must be 'accepted'"

        for module in TARGET_MODULES:
            assert module in content.lower(), f"ADR must reference module '{module}'"

        assert "cross-module" in content.lower(), "ADR must reference cross-module constraints"

        assert (
            "fk" in content.lower() or "foreign key" in content.lower()
        ), "ADR must prohibit cross-module foreign keys"
