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

    def _base_url(self):
        return embedding_base_url(self._snapshot, self._provider_model, self._credential)

    async def embed_query(self, text: str) -> list[float]:
        if getattr(self._credential, "authentication", None) is not None:
            from modules.agent.application.interfaces.execution_context import current_execution
            from modules.agent.application.interfaces.project_configuration import resolve_runtime_configuration
            from modules.agent.infra.adapters.configuration_transport import BoundConfigurationCredential
            from shared.contracts.project_configuration import ConfigurationError
            context = current_execution.get()
            if context is None or context.run_id is None or context.project_id != self._credential.project_id:
                raise ConfigurationError("CONFIG_USAGE_NOT_AUTHORIZED")
            project_id, run_id, credential_id = context.project_id, context.network_execution_id or context.run_id, self._credential.id
            async def resolve(destination):
                return await resolve_runtime_configuration(project_id=project_id, run_id=run_id,
                    consumer_kind="provider_credential", consumer_id=credential_id,
                    field_path="/authentication/fields/api_key", destination=destination)
            api_key = BoundConfigurationCredential(resolve)
        else:
            try:
                api_key = decrypt_secret(self._credential.encrypted_secret, self._encryption_key)
            except Exception:
                raise ValidationError("Embedding provider credential could not be decrypted") from None

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


def embedding_base_url(snapshot, provider_model, credential) -> str | None:
    from modules.agent.domain.provider_identity import canonical_provider_key
    provider = canonical_provider_key(snapshot.embedding_provider)
    provider_metadata = provider_model.metadata or {}
    credential_metadata = credential.metadata or {}

    if provider == "openai_compatible":
        value = provider_metadata.get("base_url") or credential_metadata.get("base_url")
        if not value:
            raise ValidationError("Custom embedding provider requires base_url")
        return str(value)
    if provider == "openrouter":
        value = credential_metadata.get("base_url") or provider_metadata.get("base_url")
        return str(value) if value else None
    return None
