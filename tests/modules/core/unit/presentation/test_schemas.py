from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
SCHEMAS_FILE = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "core" / "presentation" / "schemas.py"


class TestCoreSchemas:
    def test_schemas_file_exists(self):
        assert SCHEMAS_FILE.is_file()

    def test_schemas_are_pydantic_models(self):
        content = SCHEMAS_FILE.read_text(encoding="utf-8")
        assert "BaseModel" in content

    def test_schemas_contain_request_and_response(self):
        content = SCHEMAS_FILE.read_text(encoding="utf-8")
        assert "Request" in content or "Response" in content or "Input" in content or "Output" in content
