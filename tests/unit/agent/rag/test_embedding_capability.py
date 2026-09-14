from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.agent.infra.execution.rag import embedding_capability as embedding_module
from modules.agent.infra.execution.rag.embedding_capability import RuntimeEmbeddingCapability
from shared.contracts.errors import ValidationError


class _Client:
    def __init__(self, embedding) -> None:
        self.embedding = embedding
        self.queries: list[str] = []

    async def aembed_query(self, text: str):
        self.queries.append(text)
        return list(self.embedding)


class _Factory:
    def __init__(self, client: _Client) -> None:
        self.client = client
        self.calls: list[dict] = []

    def create_embedding_client(self, **kwargs):
        self.calls.append(dict(kwargs))
        return self.client


def _capability(
    factory: _Factory,
    *,
    provider: str = "openai",
    provider_metadata=None,
    credential_metadata=None,
    dimensions: int = 3,
) -> RuntimeEmbeddingCapability:
    return RuntimeEmbeddingCapability(
        embedding_factory=factory,
        encryption_key="key",
        snapshot=SimpleNamespace(
            embedding_provider=provider,
            embedding_model="embedding-test",
            embedding_dimensions=dimensions,
        ),
        provider_model=SimpleNamespace(metadata=provider_metadata or {}),
        credential=SimpleNamespace(
            encrypted_secret="ciphertext",
            metadata=credential_metadata or {},
        ),
    )


@pytest.mark.asyncio
async def test_embedding_capability_uses_accepted_provider_snapshot(monkeypatch) -> None:
    client = _Client([0.1, 0.2, 0.3])
    factory = _Factory(client)
    monkeypatch.setattr(embedding_module, "decrypt_secret", lambda *_args: "api-key")

    result = await _capability(factory).embed_query("query")

    assert result == [0.1, 0.2, 0.3]
    assert client.queries == ["query"]
    assert factory.calls == [
        {
            "provider": "openai",
            "model": "embedding-test",
            "api_key": "api-key",
            "base_url": None,
            "dimensions": 3,
        }
    ]


@pytest.mark.asyncio
async def test_embedding_capability_resolves_custom_base_url_from_provider_model(monkeypatch) -> None:
    client = _Client([0.1, 0.2, 0.3])
    factory = _Factory(client)
    monkeypatch.setattr(embedding_module, "decrypt_secret", lambda *_args: "api-key")

    await _capability(
        factory,
        provider="custom",
        provider_metadata={"base_url": "https://provider-model.test/v1"},
        credential_metadata={"base_url": "https://credential.test/v1"},
    ).embed_query("query")

    assert factory.calls[0]["base_url"] == "https://provider-model.test/v1"


@pytest.mark.asyncio
async def test_embedding_capability_prefers_credential_base_url_for_openrouter(monkeypatch) -> None:
    client = _Client([0.1, 0.2, 0.3])
    factory = _Factory(client)
    monkeypatch.setattr(embedding_module, "decrypt_secret", lambda *_args: "api-key")

    await _capability(
        factory,
        provider="openrouter",
        provider_metadata={"base_url": "https://provider-model.test/v1"},
        credential_metadata={"base_url": "https://credential.test/v1"},
    ).embed_query("query")

    assert factory.calls[0]["base_url"] == "https://credential.test/v1"


@pytest.mark.asyncio
async def test_embedding_capability_requires_custom_base_url(monkeypatch) -> None:
    client = _Client([0.1, 0.2, 0.3])
    factory = _Factory(client)
    monkeypatch.setattr(embedding_module, "decrypt_secret", lambda *_args: "api-key")

    with pytest.raises(ValidationError, match="Custom embedding provider requires base_url"):
        await _capability(factory, provider="custom").embed_query("query")


@pytest.mark.asyncio
async def test_embedding_capability_rejects_dimension_mismatch(monkeypatch) -> None:
    client = _Client([0.1, 0.2])
    factory = _Factory(client)
    monkeypatch.setattr(embedding_module, "decrypt_secret", lambda *_args: "api-key")

    with pytest.raises(ValidationError, match="expected 3, got 2"):
        await _capability(factory, dimensions=3).embed_query("query")


@pytest.mark.asyncio
async def test_embedding_capability_wraps_credential_decryption_failure(monkeypatch) -> None:
    client = _Client([0.1, 0.2, 0.3])
    factory = _Factory(client)

    def fail(*_args):
        raise RuntimeError("secret detail")

    monkeypatch.setattr(embedding_module, "decrypt_secret", fail)

    with pytest.raises(ValidationError, match="credential could not be decrypted"):
        await _capability(factory).embed_query("query")
