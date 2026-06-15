from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parents[2] / "specs" / "module-architecture-standardization"
INVENTORY_DIR = SPECS_DIR / "execution" / "inventory"
FILES_INVENTORY = INVENTORY_DIR / "files.md"
STRUCTURE_MATRIX = INVENTORY_DIR / "structure-matrix.md"
IMPORTS_INVENTORY = INVENTORY_DIR / "imports.md"
DATABASE_OWNERSHIP_INVENTORY = INVENTORY_DIR / "database-ownership.md"
ROUTES_INVENTORY = INVENTORY_DIR / "routes.md"


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
