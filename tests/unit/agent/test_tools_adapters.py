import uuid
from uuid import UUID

import pytest

from modules.agent.application.interfaces.ports import SecretCipherPort
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.secret_resolver import ToolSecretResolverAdapter
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor, _is_private_url
from modules.agent.domain.entities import Secret
from modules.agent.application.interfaces.repositories import SecretRepository


# ── Fakes ────────────────────────────────────────────────────────


class FakeSecretRepo(SecretRepository):
    def __init__(self) -> None:
        self._store: dict[str, Secret] = {}

    async def create(self, secret: Secret) -> Secret:
        self._store[f"{secret.project_id}:{secret.name}"] = secret
        return secret

    async def get_by_id(self, secret_id: UUID) -> Secret:
        for s in self._store.values():
            if s.id == secret_id:
                return s
        raise ValueError("not found")

    async def get_by_name(self, project_id: UUID, name: str) -> Secret:
        key = f"{project_id}:{name}"
        if key not in self._store:
            from modules.agent.domain.errors import SecretNotFoundError
            raise SecretNotFoundError(name)
        return self._store[key]

    async def list_by_project(self, project_id: UUID) -> list[Secret]:
        return [s for s in self._store.values() if s.project_id == project_id]

    async def paginate_by_project(self, project_id: UUID, *, limit: int = 50, cursor: str | None = None) -> list[Secret]:
        return []

    async def update(self, secret: Secret) -> Secret:
        self._store[f"{secret.project_id}:{secret.name}"] = secret
        return secret

    async def delete(self, secret_id: UUID) -> None:
        self._store = {k: v for k, v in self._store.items() if v.id != secret_id}


class FakeCipher(SecretCipherPort):
    async def encrypt(self, plaintext: str) -> str:
        return f"enc:{plaintext}"

    async def decrypt(self, ciphertext: str) -> str:
        return ciphertext.replace("enc:", "", 1)


# ── SSRF / URL Safety ────────────────────────────────────────────


class TestSSRFProtection:
    def test_private_ip_10_dot(self):
        assert _is_private_url("http://10.0.0.1:8080/test") is True

    def test_private_ip_192_dot(self):
        assert _is_private_url("http://192.168.1.1/admin") is True

    def test_private_ip_172_dot(self):
        assert _is_private_url("http://172.16.0.1:3000") is True

    def test_localhost(self):
        assert _is_private_url("http://localhost:5000") is True

    def test_loopback(self):
        assert _is_private_url("http://127.0.0.1") is True

    def test_public_url_passes(self):
        assert _is_private_url("https://8.8.8.8/health") is False


# ── HttpToolExecutor ─────────────────────────────────────────────


class TestHttpToolExecutor:
    @pytest.mark.asyncio
    async def test_ssrf_blocks_private_ip(self):
        executor = HttpToolExecutor()
        result = await executor.execute(
            method="GET",
            url="http://192.168.1.1/admin",
        )
        assert result.success is False
        assert "SSRF blocked" in (result.error or "")

    @pytest.mark.asyncio
    async def test_timeout_returns_error(self):
        executor = HttpToolExecutor()
        result = await executor.execute(
            method="GET",
            url="https://api.example.com/slow",
            timeout_ms=1,
        )
        assert result.success is False
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_request_error_returns_error(self):
        executor = HttpToolExecutor()
        result = await executor.execute(
            method="GET",
            url="https://nonexistent.invalid.example.com/test",
        )
        assert result.success is False
        assert result.error is not None


# ── SecretCipherAdapter ──────────────────────────────────────────


class TestSecretCipherAdapter:
    @pytest.mark.asyncio
    async def test_encrypt_decrypt_roundtrip(self):
        cipher = SecretCipherAdapter(encryption_key="test-key-32-chars-long-for-testing!")
        encrypted = await cipher.encrypt("my-secret-value")
        assert encrypted != "my-secret-value"

        decrypted = await cipher.decrypt(encrypted)
        assert decrypted == "my-secret-value"

    @pytest.mark.asyncio
    async def test_encrypt_different_keys_produce_different_output(self):
        cipher1 = SecretCipherAdapter(encryption_key="key-1-123456789012345678901234567")
        cipher2 = SecretCipherAdapter(encryption_key="key-2-123456789012345678901234567")
        e1 = await cipher1.encrypt("same-value")
        e2 = await cipher2.encrypt("same-value")
        assert e1 != e2


# ── ToolSecretResolverAdapter ────────────────────────────────────


class TestToolSecretResolverAdapter:
    @pytest.mark.asyncio
    async def test_resolves_secret_headers(self):
        repo = FakeSecretRepo()
        cipher = FakeCipher()
        adapter = ToolSecretResolverAdapter(repo, cipher)

        pid = uuid.uuid4()
        secret = Secret(
            project_id=pid,
            name="my-api-key",
            encrypted_value="enc:real-api-key-123",
        )
        await repo.create(secret)

        headers = [
            {"key": "Authorization", "value": "{{secret:my-api-key}}"},
            {"key": "X-Static", "value": "hello"},
        ]
        resolved = await adapter.resolve_headers(headers, pid)

        assert resolved["Authorization"] == "real-api-key-123"
        assert resolved["X-Static"] == "hello"

    @pytest.mark.asyncio
    async def test_missing_secret_returns_empty(self):
        repo = FakeSecretRepo()
        cipher = FakeCipher()
        adapter = ToolSecretResolverAdapter(repo, cipher)

        pid = uuid.uuid4()
        headers = [
            {"key": "Authorization", "value": "{{secret:nonexistent}}"},
        ]
        resolved = await adapter.resolve_headers(headers, pid)

        assert resolved["Authorization"] == ""

    @pytest.mark.asyncio
    async def test_non_secret_headers_pass_through(self):
        repo = FakeSecretRepo()
        cipher = FakeCipher()
        adapter = ToolSecretResolverAdapter(repo, cipher)

        pid = uuid.uuid4()
        headers = [
            {"key": "Content-Type", "value": "application/json"},
            {"key": "Accept", "value": "text/plain"},
        ]
        resolved = await adapter.resolve_headers(headers, pid)

        assert resolved["Content-Type"] == "application/json"
        assert resolved["Accept"] == "text/plain"

    @pytest.mark.asyncio
    async def test_empty_headers_returns_empty(self):
        repo = FakeSecretRepo()
        cipher = FakeCipher()
        adapter = ToolSecretResolverAdapter(repo, cipher)

        resolved = await adapter.resolve_headers([], uuid.uuid4())
        assert resolved == {}

    @pytest.mark.asyncio
    async def test_header_without_key_is_skipped(self):
        repo = FakeSecretRepo()
        cipher = FakeCipher()
        adapter = ToolSecretResolverAdapter(repo, cipher)

        headers = [
            {"value": "no-key"},
            {"key": "", "value": "empty-key"},
            {"key": "Real", "value": "value"},
        ]
        resolved = await adapter.resolve_headers(headers, uuid.uuid4())

        assert "Real" in resolved
        assert resolved["Real"] == "value"
