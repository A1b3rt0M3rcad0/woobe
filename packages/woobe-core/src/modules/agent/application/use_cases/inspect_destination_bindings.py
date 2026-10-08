from modules.agent.application.dtos.destination_binding_dtos import (
    InspectDestinationBindingsInput,
)


from modules.agent.application.interfaces.repositories import (
    ProviderCredentialRepository,
    SecretRepository,
)
from modules.agent.application.interfaces.project_environment import (
    ProjectEnvironmentKeyReader,
)
from modules.agent.application.interfaces.vector_snapshot_repository import (
    VectorSnapshotRepository,
)
from modules.agent.domain.enums import CredentialStatus
from modules.agent.domain.vector_snapshot_entities import VECTOR_SNAPSHOT_READY
from shared.contracts.errors import NotFoundError, ValidationError


def revision(item):
    instant = item.updated_at or item.created_at
    return instant.isoformat() if instant else None


class InspectDestinationBindingsUseCase:
    """Expose scoped binding identities and revisions without decrypting their values."""

    def __init__(
        self,
        credentials: ProviderCredentialRepository,
        secrets: SecretRepository,
        vectors: VectorSnapshotRepository,
        environment: ProjectEnvironmentKeyReader,
    ):
        self._credentials, self._secrets = credentials, secrets
        self._vectors, self._environment = vectors, environment

    async def execute(self, definition: InspectDestinationBindingsInput) -> dict:
        project = definition.project_id
        result = {
            "credentials": {},
            "secrets": {},
            "project_environment": {},
            "knowledge": {},
        }
        for alias, binding in definition.credentials.items():
            if binding.credential_id is None:
                if not binding.protected_ref:
                    raise ValidationError(
                        "Credential binding has no destination source"
                    )
                result["credentials"][alias] = {
                    "provider": binding.provider.value,
                    "protected_ref": binding.protected_ref,
                    "existing": False,
                }
                continue
            if binding.protected_ref is not None:
                raise ValidationError("Credential binding has more than one source")
            credential = await self._credentials.get_by_id(binding.credential_id)
            if credential is None or credential.project_id != project:
                raise NotFoundError("Destination credential is unavailable")
            if (
                credential.status != CredentialStatus.active
                or credential.provider != binding.provider
            ):
                raise ValidationError(
                    "Destination credential must be active and use the declared provider"
                )
            expected_metadata = (
                binding.metadata.model_dump(exclude_none=True)
                if binding.metadata is not None
                else {}
            )
            if any(
                (credential.metadata or {}).get(field) != value
                for field, value in expected_metadata.items()
            ):
                raise ValidationError(
                    "Destination credential connection metadata differs from the declared SDK intent"
                )
            result["credentials"][alias] = {
                "credential_id": str(credential.id),
                "provider": binding.provider.value,
                "revision": revision(credential),
                "existing": True,
            }
        for alias, binding in definition.secrets.items():
            if binding.existing_key is None:
                if not binding.protected_ref:
                    raise ValidationError("Secret binding has no destination source")
                result["secrets"][alias] = {
                    "protected_ref": binding.protected_ref,
                    "existing": False,
                }
                continue
            if binding.protected_ref is not None:
                raise ValidationError("Secret binding has more than one source")
            secret = await self._secrets.get_by_name(project, binding.existing_key)
            if secret is None or secret.project_id != project:
                raise NotFoundError("Destination secret is unavailable")
            result["secrets"][alias] = {
                "secret_id": str(secret.id),
                "name": secret.name,
                "revision": revision(secret),
                "existing": True,
            }
        keys = {
            item.existing_key
            for item in definition.project_environment.values()
            if item.existing_key is not None
        }
        await self._environment.require_keys(project_id=project, keys=keys)
        key_evidence = await self._environment.inspect_keys(
            project_id=project, keys=keys
        )
        for alias, binding in definition.project_environment.items():
            if (binding.existing_key is None) == (binding.protected_ref is None):
                raise ValidationError(
                    "Environment binding requires exactly one destination source"
                )
            if binding.existing_key is not None:
                evidence = key_evidence.get(binding.existing_key)
                if evidence is None:
                    raise NotFoundError(
                        "Destination Project Environment key is unavailable"
                    )
                if binding.kind is not None and evidence["kind"] != binding.kind:
                    raise ValidationError(
                        "Destination Project Environment kind differs from the requirement"
                    )
                result["project_environment"][alias] = evidence
            else:
                result["project_environment"][alias] = binding.model_dump(
                    exclude_none=True
                )
        for alias, binding in definition.knowledge.items():
            snapshot = await self._vectors.get_by_id(binding.vector_snapshot_id)
            if snapshot is None or snapshot.project_id != project:
                raise NotFoundError("Destination VectorSnapshot is unavailable")
            if snapshot.status != VECTOR_SNAPSHOT_READY or not snapshot.snapshot_hash:
                raise ValidationError(
                    "Destination VectorSnapshot must be READY with immutable evidence"
                )
            result["knowledge"][alias] = {
                "vector_snapshot_id": str(snapshot.id),
                "collection_id": str(snapshot.collection_id),
                "snapshot_hash": snapshot.snapshot_hash,
                "revision": revision(snapshot),
                "embedding_provider_model_id": str(
                    snapshot.embedding_provider_model_id
                ),
            }
        return result
