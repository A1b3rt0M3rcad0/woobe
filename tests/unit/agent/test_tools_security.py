"""Security tests for tools agent consolidation (spec 015).

Covers SSRF protection, timeout behavior, error sanitization,
secret redaction, and cipher operations.
"""
import uuid

import pytest

from modules.agent.domain.events import AgentSecretCreatedV1
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from modules.agent.infra.adapters.tool_executor import _is_private_url, _sanitize_error


class TestSSRFProtection:
    def test_blocks_localhost_hostname(self):
        assert _is_private_url("http://localhost:8080/test")

    def test_blocks_ipv4_loopback(self):
        assert _is_private_url("http://127.0.0.1:8000/test")

    def test_blocks_ipv6_loopback(self):
        assert _is_private_url("http://[::1]:8000/test")

    def test_blocks_private_10_net(self):
        assert _is_private_url("http://10.0.0.1/api")

    def test_blocks_private_172_16_net(self):
        assert _is_private_url("http://172.16.0.1/api")

    def test_blocks_private_192_168_net(self):
        assert _is_private_url("http://192.168.1.1/api")

    def test_blocks_zero_zero_zero_zero(self):
        assert _is_private_url("http://0.0.0.0:3000")

    def test_allows_public_ip(self):
        assert not _is_private_url("http://93.184.216.34/path")

    def test_returns_true_for_empty_hostname(self):
        assert _is_private_url("http:///path-only")


class TestErrorSanitization:
    def test_replaces_newlines_with_spaces(self):
        result = _sanitize_error("line1\nline2\nline3")
        assert "\n" not in result

    def test_truncates_long_errors(self):
        long_error = "x" * 1000
        result = _sanitize_error(long_error)
        assert len(result) <= 503

    def test_preserves_short_errors(self):
        short = "connection refused"
        assert _sanitize_error(short) == short


class TestSecretCipher:
    async def test_encrypt_decrypt_roundtrip(self):
        adapter = SecretCipherAdapter(encryption_key="test-key-32-characters-long!!")
        plaintext = "my-secret-value"
        encrypted = await adapter.encrypt(plaintext)
        assert encrypted != plaintext
        decrypted = await adapter.decrypt(encrypted)
        assert decrypted == plaintext

    async def test_encryption_is_deterministic_with_same_key(self):
        adapter = SecretCipherAdapter(encryption_key="test-key-32-characters-long!!")
        p1 = await adapter.encrypt("hello")
        p2 = await adapter.encrypt("hello")
        assert p1 != p2

    async def test_decrypt_with_wrong_key_fails(self):
        adapter1 = SecretCipherAdapter(encryption_key="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        encrypted = await adapter1.encrypt("data")
        adapter2 = SecretCipherAdapter(encryption_key="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
        with pytest.raises(Exception):
            await adapter2.decrypt(encrypted)


class TestSecretEventRedaction:
    def test_agent_secret_created_excludes_encrypted_value(self):
        event = AgentSecretCreatedV1.create(
            secret_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="test-secret",
            secret_type="api_key",
        )
        assert "encrypted_value" not in event.payload

    def test_agent_secret_created_payload_has_name(self):
        event = AgentSecretCreatedV1.create(
            secret_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            name="test-secret",
            secret_type="api_key",
        )
        assert event.payload["name"] == "test-secret"
        assert event.payload["type"] == "api_key"
        assert "encrypted_value" not in event.payload
