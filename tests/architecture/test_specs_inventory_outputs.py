from pathlib import Path

INVENTORY_DIR = Path(__file__).resolve().parents[2] / "specs" / "execution" / "inventory"
FILES_INVENTORY = INVENTORY_DIR / "files.md"
IMPORTS_INVENTORY = INVENTORY_DIR / "imports.md"
DATABASE_OWNERSHIP_INVENTORY = INVENTORY_DIR / "database-ownership.md"
ROUTES_INVENTORY = INVENTORY_DIR / "routes.md"
EVENTS_INVENTORY = INVENTORY_DIR / "events.md"
WORKERS_INVENTORY = INVENTORY_DIR / "workers.md"


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

    def test_create_current_import_dependency_map_output_exists(self):
        assert IMPORTS_INVENTORY.exists(), (
            f"Inventory file not found: {IMPORTS_INVENTORY}"
        )

    def test_create_current_import_dependency_map_output_has_no_placeholder_only_content(self):
        assert IMPORTS_INVENTORY.exists(), (
            f"Inventory file not found: {IMPORTS_INVENTORY}"
        )

        content = IMPORTS_INVENTORY.read_text(encoding="utf-8")
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
            "modules.ai",
            "modules.knowledge",
            "modules.runtime",
        ]
        found_evidence = any(
            marker in content for marker in evidence_markers
        )
        assert found_evidence, (
            "Inventory file must reference actual import paths as evidence"
        )

    def test_create_current_database_ownership_map_output_exists(self):
        assert DATABASE_OWNERSHIP_INVENTORY.exists(), (
            f"Inventory file not found: {DATABASE_OWNERSHIP_INVENTORY}"
        )

    def test_create_current_database_ownership_map_output_has_no_placeholder_only_content(self):
        assert DATABASE_OWNERSHIP_INVENTORY.exists(), (
            f"Inventory file not found: {DATABASE_OWNERSHIP_INVENTORY}"
        )

        content = DATABASE_OWNERSHIP_INVENTORY.read_text(encoding="utf-8")
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
            "__tablename__",
            "ForeignKey",
            "schema",
            "migrations/",
        ]
        found_evidence = any(
            marker in content for marker in evidence_markers
        )
        assert found_evidence, (
            "Inventory file must reference actual database models/schemas as evidence"
        )

    def test_create_current_api_route_map_output_exists(self):
        assert ROUTES_INVENTORY.exists(), (
            f"Inventory file not found: {ROUTES_INVENTORY}"
        )

    def test_create_current_api_route_map_output_has_no_placeholder_only_content(self):
        assert ROUTES_INVENTORY.exists(), (
            f"Inventory file not found: {ROUTES_INVENTORY}"
        )

        content = ROUTES_INVENTORY.read_text(encoding="utf-8")
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
            "APIRouter",
            "/ai",
            "/knowledge",
            "/runtime",
            "include_router",
        ]
        found_evidence = any(
            marker in content for marker in evidence_markers
        )
        assert found_evidence, (
            "Inventory file must reference actual route definitions as evidence"
        )

    def test_create_current_event_catalog_output_exists(self):
        assert EVENTS_INVENTORY.exists(), (
            f"Inventory file not found: {EVENTS_INVENTORY}"
        )

    def test_create_current_event_catalog_output_has_no_placeholder_only_content(self):
        assert EVENTS_INVENTORY.exists(), (
            f"Inventory file not found: {EVENTS_INVENTORY}"
        )

        content = EVENTS_INVENTORY.read_text(encoding="utf-8")
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
            "event_type",
            "OutboxEvent",
            "InboxEvent",
            "routing_key",
            "src/modules/",
            "src/shared/workers/",
        ]
        found_evidence = any(
            marker in content for marker in evidence_markers
        )
        assert found_evidence, (
            "Inventory file must reference actual event definitions as evidence"
        )

    def test_create_current_worker_inventory_output_exists(self):
        assert WORKERS_INVENTORY.exists(), (
            f"Inventory file not found: {WORKERS_INVENTORY}"
        )

    def test_create_current_worker_inventory_output_has_no_placeholder_only_content(self):
        assert WORKERS_INVENTORY.exists(), (
            f"Inventory file not found: {WORKERS_INVENTORY}"
        )

        content = WORKERS_INVENTORY.read_text(encoding="utf-8")
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
            "src/workers/",
            "src/shared/workers/",
            "src/modules/",
            "BaseWorker",
            "Worker",
            "Dispatcher",
            "Consumer",
        ]
        found_evidence = any(
            marker in content for marker in evidence_markers
        )
        assert found_evidence, (
            "Inventory file must reference actual worker definitions as evidence"
        )
