"""Read exact Network constituents for configuration readiness."""
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from modules.network.infra.services.session_mode_binding_service import NetworkApplicationService
from shared.contracts.errors import NotFoundError


async def read_configuration_bindings(session, *, project_id, target_id, environment, version_id=None):
    network = await session.get(NetworkModel, target_id)
    if network is None or network.project_id != project_id:
        raise NotFoundError("Network not found")
    if environment == "draft" and version_id is None:
        service = NetworkApplicationService(None)
        definition = service._definition(network.draft_definition)
        return {"bindings": await service._resolve_draft_bindings(session, definition, project_id),
                "selection": {"environment": environment, "version_id": None, "draft_revision": network.draft_revision, "source": "draft"}}
    identifier = version_id or (network.staging_version_id if environment == "staging" else network.production_version_id)
    version = await session.get(NetworkVersionModel, identifier) if identifier else None
    if version is None or version.project_id != project_id or version.network_id != target_id:
        raise NotFoundError("Selected Network version not found")
    return {"bindings": version.resolved_bindings or {},
            "selection": {"environment": environment, "version_id": str(version.id), "source": "version"}}
