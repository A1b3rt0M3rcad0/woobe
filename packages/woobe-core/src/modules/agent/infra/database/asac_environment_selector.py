"""Agent-owned selections do not rewrite immutable executable Release content."""
from sqlalchemy import select, text
from modules.agent.infra.database.asac_models import ASaCEnvironmentSelectionModel
from modules.agent.infra.database.models import AgentReleaseModel
from modules.agent.infra.database.release_activation_repository import AgentReleaseActivationModel
from modules.agent.infra.database.asac_publisher import frozen_release_entity
from modules.agent.domain.execution_definition import hash_agent_execution_snapshot
from shared.contracts.errors import ConflictError


class AgentASaCEnvironmentSelector:
    async def inspect(self,session,*,project_id,resource_id,principal,release_id):
        row=await session.get(AgentReleaseModel,release_id)
        if row is None or row.project_id!=project_id or row.agent_id!=resource_id or row.snapshot_kind!='release':
            raise ConflictError('ASAC_DEPLOYMENT_RELEASE_UNAVAILABLE')
        digest=hash_agent_execution_snapshot(frozen_release_entity(row))
        fingerprint=digest
        if session.bind.dialect.name=='postgresql':
            fingerprint=await session.scalar(text("SELECT encode(sha256(convert_to((to_jsonb(r)-ARRAY['status','updated_at','promoted_at','promoted_by'])::text,'UTF8')),'hex') FROM agent.agent_releases r WHERE id=:id"),{'id':release_id})
        return {'runtime_digest':'sha256:'+digest,'fingerprint':fingerprint}

    async def check_selection(self,session,*,project_id,resource_id,principal,selection):
        if selection.selection_authority=='asac':
            current=await self.inspect(session,project_id=project_id,resource_id=resource_id,
                principal=principal,release_id=selection.snapshot_id)
            if current['fingerprint']!=selection.execution_fingerprint:
                raise ConflictError('ASAC_SELECTION_INCONSISTENT: executable selection changed')
        else:
            current=await session.scalar(select(AgentReleaseModel.id).where(AgentReleaseModel.project_id==project_id,
                AgentReleaseModel.agent_id==resource_id,AgentReleaseModel.status==selection.environment)
                .order_by(AgentReleaseModel.updated_at.desc(),AgentReleaseModel.id.desc()).limit(1))
            if current!=selection.snapshot_id:
                raise ConflictError('ASAC_SELECTION_INCONSISTENT: native selection differs')

    async def apply(self,session,*,project_id,resource_id,principal,environment,release_id,
                    previous_release_id,action,reason,changed):
        if changed and environment=='production':
            session.add(AgentReleaseActivationModel(project_id=project_id,agent_id=resource_id,
                release_id=release_id,previous_release_id=previous_release_id,
                action='rollback' if action=='rollback' else 'reactivate',change_description=reason,
                created_by=getattr(principal,'user_id',None)))

    def add_outbox(self,session,*,model,identifier,resource_id,operation_id,receipt):
        session.add(model(id=identifier,aggregate_type='agent',aggregate_id=resource_id,
            event_type='agent.asac.environment.selected',event_version=1,routing_key='agent.asac.environment.selected',
            payload=receipt,metadata_={'schema_version':'1.0'},idempotency_key='asac-deployment:'+receipt['deployment_id'],
            correlation_id=operation_id,causation_id=identifier,status='pending',attempts=0))


async def selected_agent_release(session,agent_id,environment):
    selection=await session.scalar(select(ASaCEnvironmentSelectionModel).where(
        ASaCEnvironmentSelectionModel.resource_id==agent_id,ASaCEnvironmentSelectionModel.environment==environment,
        ASaCEnvironmentSelectionModel.selection_authority=='asac'))
    if selection is None: return None
    row=await session.get(AgentReleaseModel,selection.snapshot_id)
    if row is None or row.project_id!=selection.project_id or row.agent_id!=agent_id:
        raise ConflictError('ASAC_SELECTION_INCONSISTENT')
    current=await AgentASaCEnvironmentSelector().inspect(session,project_id=selection.project_id,
        resource_id=agent_id,principal=None,release_id=row.id)
    if current['fingerprint']!=selection.execution_fingerprint:
        raise ConflictError('ASAC_SELECTION_INCONSISTENT')
    return row
