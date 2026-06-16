from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TOOLS_SRC = PROJECT_ROOT / "src" / "modules" / "tools"
TOOLS_TEST_FILES = [
    TOOLS_SRC / "application" / "use_cases" / "tools_use_cases.py",
    TOOLS_SRC / "presentation" / "schemas.py",
    TOOLS_SRC / "presentation" / "mappers.py",
]

FORBIDDEN_PATTERNS = [
    'encrypted_value',
    'encrypt_secret',
    'decrypt_secret',
    '"secret"',
    "'secret'",
]

ALLOWED_PATTERNS = [
    "encrypted_value",
    "encrypt_secret",
    "decrypt_secret",
]


class TestSecretSafetyCharacterization:
    def test_secret_encrypted_in_use_case(self):
        """Secrets file must use encryption for the value field."""
        content = (TOOLS_SRC / "application" / "use_cases" / "tools_use_cases.py").read_text(encoding="utf-8")
        assert "encrypt_secret" in content
        assert "decrypt_secret" in content or '_resolve_secret' in content

    def test_secret_value_not_in_response_schema(self):
        """SecretResponse must not expose the secret value."""
        content = (TOOLS_SRC / "presentation" / "schemas.py").read_text(encoding="utf-8")
        assert "value" not in content.split("class SecretResponse")[1].split("class")[0]

    def test_secret_encrypted_value_not_exported(self):
        """Ensure encrypted_value is internal and not exposed in schemas."""
        schemas_content = (TOOLS_SRC / "presentation" / "schemas.py").read_text(encoding="utf-8")
        assert "encrypted_value" not in schemas_content

    def test_secret_model_has_encrypted_value(self):
        """SecretModel must have encrypted_value field, not plaintext value."""
        models_content = (TOOLS_SRC / "infra" / "database" / "models.py").read_text(encoding="utf-8")
        assert "encrypted_value" in models_content

    def test_use_case_uses_encryption(self):
        """CreateSecretUseCase must encrypt the value before storing."""
        use_case_content = (TOOLS_SRC / "application" / "use_cases" / "tools_use_cases.py").read_text(encoding="utf-8")
        assert "encrypt_secret" in use_case_content

    def test_encryption_key_from_env(self):
        """Encryption key must come from environment variable."""
        use_case_content = (TOOLS_SRC / "application" / "use_cases" / "tools_use_cases.py").read_text(encoding="utf-8")
        assert 'SECRETS_ENCRYPTION_KEY' in use_case_content
