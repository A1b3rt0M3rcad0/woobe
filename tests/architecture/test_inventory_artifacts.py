from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parents[2] / "specs" / "module-architecture-standardization"
INVENTORY_DIR = SPECS_DIR / "execution" / "inventory"
FILES_INVENTORY = INVENTORY_DIR / "files.md"
STRUCTURE_MATRIX = INVENTORY_DIR / "structure-matrix.md"
IMPORTS_INVENTORY = INVENTORY_DIR / "imports.md"
DATABASE_OWNERSHIP_INVENTORY = INVENTORY_DIR / "database-ownership.md"
ROUTES_INVENTORY = INVENTORY_DIR / "routes.md"
TRANSACTIONS_INVENTORY = INVENTORY_DIR / "transactions.md"
EVENTS_INVENTORY = INVENTORY_DIR / "events.md"
WORKERS_INVENTORY = INVENTORY_DIR / "workers.md"
TESTS_BOOTSTRAP_INVENTORY = INVENTORY_DIR / "tests-bootstrap.md"
RISKS_INVENTORY = INVENTORY_DIR / "risks.md"
IDENTITY_MIGRATION_MAP = INVENTORY_DIR / "identity-migration-map.md"


class TestInventoryArtifacts:
    def test_files_md_exists(self):
        assert FILES_INVENTORY.exists(), f"File not found: {FILES_INVENTORY}"

    def test_files_md_has_real_content(self):
        assert FILES_INVENTORY.exists()
        content = FILES_INVENTORY.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 10, f"Only {len(lines)} non-header lines"
        assert "src/modules/" in content, "Must reference module paths"
        assert "76f1f07" in content, "Must contain execution SHA"

    def test_structure_matrix_md_exists(self):
        assert STRUCTURE_MATRIX.exists(), f"File not found: {STRUCTURE_MATRIX}"

    def test_structure_matrix_md_has_real_content(self):
        assert STRUCTURE_MATRIX.exists()
        content = STRUCTURE_MATRIX.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 10, f"Only {len(lines)} non-header lines"
        evidence_markers = ["src/modules/", "->", "canonical"]
        assert any(m in content for m in evidence_markers), "Must reference module paths and canonical targets"

    def test_imports_md_exists(self):
        assert IMPORTS_INVENTORY.exists(), f"File not found: {IMPORTS_INVENTORY}"

    def test_imports_md_has_real_content(self):
        assert IMPORTS_INVENTORY.exists()
        content = IMPORTS_INVENTORY.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 10, f"Only {len(lines)} non-header lines"
        evidence_markers = ["from modules", "import modules", "src/modules/"]
        assert any(m in content for m in evidence_markers), "Must reference import paths"

    def test_database_ownership_md_exists(self):
        assert DATABASE_OWNERSHIP_INVENTORY.exists(), f"File not found: {DATABASE_OWNERSHIP_INVENTORY}"

    def test_database_ownership_md_has_real_content(self):
        assert DATABASE_OWNERSHIP_INVENTORY.exists()
        content = DATABASE_OWNERSHIP_INVENTORY.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 10, f"Only {len(lines)} non-header lines"
        evidence_markers = ["__tablename__", "ForeignKey", "schema"]
        assert any(m in content for m in evidence_markers), "Must reference database model evidence"

    def test_routes_md_exists(self):
        assert ROUTES_INVENTORY.exists(), f"File not found: {ROUTES_INVENTORY}"

    def test_routes_md_has_real_content(self):
        assert ROUTES_INVENTORY.exists()
        content = ROUTES_INVENTORY.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 10, f"Only {len(lines)} non-header lines"
        evidence_markers = ["src/modules/", "APIRouter", "/"]
        assert any(m in content for m in evidence_markers), "Must reference route definitions"

    def test_transactions_md_exists(self):
        assert TRANSACTIONS_INVENTORY.exists(), f"File not found: {TRANSACTIONS_INVENTORY}"

    def test_transactions_md_has_real_content(self):
        assert TRANSACTIONS_INVENTORY.exists()
        content = TRANSACTIONS_INVENTORY.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 10, f"Only {len(lines)} non-header lines"
        evidence_markers = ["UnitOfWork", "commit", "rollback"]
        assert any(m in content for m in evidence_markers), "Must reference UoW/transaction evidence"

    def test_events_md_exists(self):
        assert EVENTS_INVENTORY.exists(), f"File not found: {EVENTS_INVENTORY}"

    def test_events_md_has_real_content(self):
        assert EVENTS_INVENTORY.exists()
        content = EVENTS_INVENTORY.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 10, f"Only {len(lines)} non-header lines"
        evidence_markers = ["event_type", "Outbox", "Inbox"]
        assert any(m in content for m in evidence_markers), "Must reference event/messaging evidence"

    def test_workers_md_exists(self):
        assert WORKERS_INVENTORY.exists(), f"File not found: {WORKERS_INVENTORY}"

    def test_workers_md_has_real_content(self):
        assert WORKERS_INVENTORY.exists()
        content = WORKERS_INVENTORY.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 10, f"Only {len(lines)} non-header lines"
        evidence_markers = ["Worker", "registry", "Runner"]
        assert any(m in content for m in evidence_markers), "Must reference worker/registry evidence"

    def test_tests_bootstrap_md_exists(self):
        assert TESTS_BOOTSTRAP_INVENTORY.exists(), f"File not found: {TESTS_BOOTSTRAP_INVENTORY}"

    def test_tests_bootstrap_md_has_real_content(self):
        assert TESTS_BOOTSTRAP_INVENTORY.exists()
        content = TESTS_BOOTSTRAP_INVENTORY.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 10, f"Only {len(lines)} non-header lines"
        evidence_markers = ["tests", "main.py", "migrations"]
        assert any(m in content for m in evidence_markers), "Must reference tests/bootstrap/config evidence"

    def test_risks_md_exists(self):
        assert RISKS_INVENTORY.exists(), f"File not found: {RISKS_INVENTORY}"

    def test_risks_md_has_real_content(self):
        assert RISKS_INVENTORY.exists()
        content = RISKS_INVENTORY.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 10, f"Only {len(lines)} non-header lines"
        evidence_markers = ["Risco", "Severity", "mitigação"]
        assert any(m in content for m in evidence_markers), "Must reference risk/severity/mitigation evidence"

    def test_identity_migration_map_exists(self):
        assert IDENTITY_MIGRATION_MAP.exists(), f"File not found: {IDENTITY_MIGRATION_MAP}"

    def test_identity_migration_map_has_real_content(self):
        assert IDENTITY_MIGRATION_MAP.exists()
        content = IDENTITY_MIGRATION_MAP.read_text(encoding="utf-8")
        lines = [
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert len(lines) > 10, f"Only {len(lines)} non-header lines"
        evidence_markers = ["src/modules/identity", "Current Path", "action"]
        assert any(m in content for m in evidence_markers), "Must reference identity module paths and actions"
