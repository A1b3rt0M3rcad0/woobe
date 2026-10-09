"""Capture Network publication provenance inside the Run admission transaction."""
from modules.network.infra.database.asac_models import ASaCPublicationModel, ASaCEnvironmentSelectionModel, ASaCDeploymentModel
from shared.infra.asac_runtime_provenance import admitted_publication

async def network_publication_identity(session, *, project_id, network_id, version_id, environment):
    return await admitted_publication(session, publications=ASaCPublicationModel,
        selections=ASaCEnvironmentSelectionModel, deployments=ASaCDeploymentModel,
        project_id=project_id, resource_id=network_id, snapshot_id=version_id, environment=environment)
