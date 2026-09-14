from __future__ import annotations

from typing import Any

from modules.agent.application.interfaces.embedding_factory import EmbeddingFactory
from shared.contracts.errors import ValidationError
from shared.security.crypto import decrypt_secret


class RuntimeEmbeddingCapability:
    """Bind the accepted embedding provider snapshot to the RAG capability contract."""

    def __init__(
        self,
        *,
        embedding_factory: EmbeddingFactory,
        encryption_key: str,
        snapshot: Any,
        provider_model: Any,
        credential: Any,
    ) -> None:
        self._embedding_factory = embedding_factory
        self._encryption_key = encryption_key
        self._snapshot = snapshot
        self._provider_model = provider_model
        self._credential = credential

    def _base_url(self) -> str | None:
        provider = self._snapshot.embedding_provider
        provider_metadata = self._provider_model.metadata or {}
        credential_metadata = self._credential.metadata or {}

        if provider == "custom":
            value = provider_metadata.get("base_url") or credential_metadata.get("base_url")
            if not value:
                raise ValidationError("Custom embedding provider requires base_url")
            return str(value)
        if provider == "openrouter":
            value = credential_metadata.get("base_url") or provider_metadata.get("base_url")
            return str(value) if value else None
        return None

    async def embed_query(self, text: str) -> list[float]:
        try:
            api_key = decrypt_secret(
                self._credential.encrypted_secret,
                self._encryption_key,
            )
        except Exception as exc:
            raise ValidationError("Embedding provider credential could not be decrypted") from exc

        client = self._embedding_factory.create_embedding_client(
            provider=self._snapshot.embedding_provider,
            model=self._snapshot.embedding_model,
            api_key=api_key,
            base_url=self._base_url(),
            dimensions=int(self._snapshot.embedding_dimensions),
        )
        embedding = await client.aembed_query(text)
        expected_dimensions = int(self._snapshot.embedding_dimensions)
        if len(embedding) != expected_dimensions:
            raise ValidationError(
                "Query embedding dimensions do not match snapshot: "
                f"expected {expected_dimensions}, got {len(embedding)}"
            )
        return embedding
