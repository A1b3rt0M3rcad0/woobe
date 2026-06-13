from pathlib import Path

INVENTORY_DIR = Path(__file__).resolve().parents[2] / "specs" / "execution" / "inventory"
FILES_INVENTORY = INVENTORY_DIR / "files.md"


class TestSpecsInventoryOutputs:
    def test_create_current_repository_inventory_output_exists(self):
        assert FILES_INVENTORY.exists(), (
            f"Inventory file not found: {FILES_INVENTORY}"
        )

    def test_create_current_repository_inventory_output_has_no_placeholder_only_content(self):
        assert FILES_INVENTORY.exists(), (
            f"Inventory file not found: {FILES_INVENTORY}"
        )

        content = FILES_INVENTORY.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        assert len(lines) > 10, (
            "Inventory file must contain real evidence, not just headers. "
            f"Found only {len(lines)} non-header lines."
        )

        evidence_markers = [
            "src/modules/",
            "src/shared/",
            "src/workers/",
            "tests/",
            "migrations/",
        ]
        found_evidence = any(
            marker in content for marker in evidence_markers
        )
        assert found_evidence, (
            "Inventory file must reference actual repository paths as evidence"
        )
