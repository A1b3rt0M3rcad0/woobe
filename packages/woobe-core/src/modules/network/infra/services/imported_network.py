"""Native Network package effects executed inside the owner's receipt transaction."""

from modules.network.application.imported_network_dtos import ImportedNetworkInput
from modules.network.application.portable_definition import (
    compile_imported_network_definition,
)
from modules.network.domain.enums import NetworkEnvironment
from modules.network.domain.graph import composition_hash
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from modules.network.infra.database.schema_extensions import (
    NetworkProductionActivationModel,
)
from modules.network.infra.services.binding_service import ExplicitBindingNetworkService
from modules.network.infra.services.release_atomic import _promote_atomic_in_session
from shared.infra.errors import ConflictError, NotFoundError
from shared.presentation.contracts import OperationOutcome, OperationResult
from shared.security.principal import AuthenticatedPrincipal


class ImportedNetworkHandler:
    def __init__(self, uow, service):
        self._uow, self._service = uow, service

    async def handle(self, request):
        data = ImportedNetworkInput.model_validate(request.body)
        session = self._uow.session
        actor = (
            request.principal.user_id
            if isinstance(request.principal, AuthenticatedPrincipal)
            else None
        )
        if data.action == "prepare_network":
            if data.network_id is not None:
                network = await session.get(NetworkModel, data.network_id, with_for_update=True)
                if network is None or network.project_id != data.project_id:
                    raise NotFoundError("Network is unavailable")
                if data.expected_revision is None or network.draft_revision != data.expected_revision:
                    raise ConflictError("Network Draft changed after planning")
            else:
                network = await self._service._create_project_network_in_session(
                    session, project_id=data.project_id, name=data.name.strip(), description=data.description,
                )
            result = {"id": str(network.id), "revision": network.draft_revision}
        elif data.action == "save_network_draft":
            definition = compile_imported_network_definition(
                data.portable_spec,
                network_id=data.network_id,
                agents=data.agents,
                snapshots=data.snapshots,
            )
            network = await ExplicitBindingNetworkService._save_draft_in_session(
                self._service,
                session,
                network_id=data.network_id,
                project_id=data.project_id,
                expected_revision=data.expected_revision,
                name=data.name,
                description=data.description,
                definition=definition,
            )
            result = {"id": str(network.id), "revision": network.draft_revision}
        elif data.action in {"create_staging", "create_immutable_release"}:
            version = await _promote_atomic_in_session(
                self._service,
                session,
                network_id=data.network_id,
                project_id=data.project_id,
                environment=NetworkEnvironment.STAGING
                if data.action == "create_staging"
                else NetworkEnvironment.PRODUCTION,
                created_by=actor,
                expected_revision=data.expected_revision,
                expected_network_version_id=data.source_version_id,
                activate=False,
                release_notes=data.release_notes,
            )
            result = {
                "id": str(version.id),
                "network_id": str(version.network_id),
                "kind": version.kind,
                "version": version.version,
                "composition_hash": version.composition_hash,
            }
        else:
            network = await session.get(
                NetworkModel, data.network_id, with_for_update=True
            )
            if network is None or network.project_id != data.project_id:
                raise NotFoundError("Imported Network is unavailable")
            if data.action == "activate_production":
                version = await session.get(
                    NetworkVersionModel, data.source_version_id, with_for_update=True
                )
                if (
                    version is None
                    or version.network_id != network.id
                    or version.project_id != data.project_id
                    or version.kind != "release"
                ):
                    raise ConflictError(
                        "Production requires an immutable Network Release"
                    )
                definition = self._service._definition(version.definition)
                await self._service._freeze_bindings(
                    session,
                    project_id=data.project_id,
                    bindings=version.resolved_bindings,
                    environment="production",
                )
                if (
                    composition_hash(definition, version.resolved_bindings)
                    != version.composition_hash
                ):
                    raise ConflictError("Immutable Network bindings changed")
                previous = network.production_version_id
                if previous != version.id:
                    session.add(
                        NetworkProductionActivationModel(
                            network_id=network.id,
                            project_id=data.project_id,
                            version_id=version.id,
                            previous_version_id=previous,
                            activation_kind="reactivate",
                            change_description=data.activation_reason,
                            created_by=actor,
                        )
                    )
                    network.production_version_id = version.id
                result = {
                    "id": str(version.id),
                    "network_id": str(network.id),
                    "lifecycle_state": "production",
                }
            else:
                expected = compile_imported_network_definition(
                    data.portable_spec,
                    network_id=data.network_id,
                    agents=data.agents,
                    snapshots=data.snapshots,
                )
                if (
                    network.draft_revision != data.expected_revision
                    or network.draft_definition != expected
                ):
                    raise ConflictError(
                        "Imported Network differs from its approved graph"
                    )
                definition = self._service._definition(network.draft_definition)
                await self._service._resolve_draft_bindings(
                    session, definition, data.project_id
                )
                if data.lifecycle != "draft":
                    version = await session.get(
                        NetworkVersionModel, data.source_version_id
                    )
                    expected_kind = (
                        "staging" if data.lifecycle == "staging" else "release"
                    )
                    if (
                        version is None
                        or version.network_id != network.id
                        or version.project_id != data.project_id
                        or version.kind != expected_kind
                    ):
                        raise ConflictError("Imported Network snapshot is unavailable")
                    bindings = {
                        key: dict(value)
                        for key, value in version.resolved_bindings.items()
                    }
                    await self._service._freeze_bindings(
                        session,
                        project_id=data.project_id,
                        bindings=bindings,
                        environment="staging"
                        if expected_kind == "staging"
                        else "production",
                    )
                    if (
                        composition_hash(
                            self._service._definition(version.definition), bindings
                        )
                        != version.composition_hash
                    ):
                        raise ConflictError(
                            "Imported Network snapshot differs from native bindings"
                        )
                    if (
                        data.lifecycle == "production"
                        and network.production_version_id != version.id
                    ):
                        raise ConflictError("Imported Network Release is not active")
                result = {
                    "id": str(network.id),
                    "configuration_ready": True,
                    "execution_ready": True,
                    "lifecycle_state": data.lifecycle,
                }
        await session.flush()
        return OperationResult(
            outcome=OperationOutcome.SUCCESS, body={"success": True, "data": result}
        )
