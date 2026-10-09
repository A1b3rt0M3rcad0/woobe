"""Runtime resolves independent immutable ASaC selections at admission only."""
from modules.agent.infra.database.provider_model_repositories import SQLAlchemyAgentReleaseRepositoryWithProviderModels, _release_from_model
from modules.agent.infra.database.asac_environment_selector import selected_agent_release
from modules.agent.application.interfaces.repositories import AgentReleaseRepository


class SQLAlchemySelectedAgentReleaseRepository(SQLAlchemyAgentReleaseRepositoryWithProviderModels, AgentReleaseRepository):
    async def get_active_production(self,agent_id):
        row=await selected_agent_release(self._session,agent_id,'production')
        return _release_from_model(row) if row is not None else await super().get_active_production(agent_id)

    async def get_active_staging(self,agent_id):
        row=await selected_agent_release(self._session,agent_id,'staging')
        return _release_from_model(row) if row is not None else await super().get_active_staging(agent_id)

    async def runtime_provenance(self, *, project_id, agent_id, release_id, environment):
        from modules.agent.infra.database.asac_models import ASaCPublicationModel, ASaCEnvironmentSelectionModel, ASaCDeploymentModel
        from shared.infra.asac_runtime_provenance import admitted_publication
        return await admitted_publication(self._session, publications=ASaCPublicationModel,
            selections=ASaCEnvironmentSelectionModel, deployments=ASaCDeploymentModel,
            project_id=project_id, resource_id=agent_id, snapshot_id=release_id, environment=environment)
