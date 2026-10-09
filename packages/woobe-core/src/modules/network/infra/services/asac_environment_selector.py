"""Network activation selects an exact frozen Release without rebinding nodes."""
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from modules.network.infra.database.schema_extensions import NetworkProductionActivationModel
from modules.network.domain.entities import NetworkDefinition
from modules.network.domain.graph import composition_hash
from modules.network.domain.execution_identity import network_runtime_digest
from shared.contracts.errors import ConflictError
from sqlalchemy import text


class NetworkASaCEnvironmentSelector:
    async def inspect(self,session,*,project_id,resource_id,principal,release_id):
        row=await session.get(NetworkVersionModel,release_id)
        if row is None or row.project_id!=project_id or row.network_id!=resource_id or row.kind!='release':
            raise ConflictError('ASAC_DEPLOYMENT_RELEASE_UNAVAILABLE')
        parsed=NetworkDefinition.from_dict(row.definition)
        if composition_hash(parsed,row.resolved_bindings)!=row.composition_hash:
            raise ConflictError('ASAC_DEPLOYMENT_RUNTIME_CHANGED')
        digest=network_runtime_digest(parsed,row.resolved_bindings,row.effective_external_context_contract)
        fingerprint=digest.removeprefix('sha256:')
        if session.bind.dialect.name=='postgresql':
            fingerprint=await session.scalar(text("SELECT encode(sha256(convert_to((to_jsonb(r)-ARRAY['updated_at','activation_kind'])::text,'UTF8')),'hex') FROM network.network_versions r WHERE id=:id"),{'id':release_id})
        return {'runtime_digest':digest,'fingerprint':fingerprint}

    async def check_selection(self,session,*,project_id,resource_id,principal,selection):
        root=await session.get(NetworkModel,resource_id)
        if root is None or root.project_id!=project_id or getattr(root,selection.environment+'_version_id')!=selection.snapshot_id:
            raise ConflictError('ASAC_SELECTION_INCONSISTENT: native pointer differs')
        if selection.selection_authority=='asac':
            native=await self.inspect(session,project_id=project_id,resource_id=resource_id,principal=principal,release_id=selection.snapshot_id)
            if native['fingerprint']!=selection.execution_fingerprint:
                raise ConflictError('ASAC_SELECTION_INCONSISTENT: executable identity differs')

    async def apply(self,session,*,project_id,resource_id,principal,environment,release_id,
                    previous_release_id,action,reason,changed):
        root=await session.get(NetworkModel,resource_id)
        setattr(root,environment+'_version_id',release_id)
        if changed and environment=='production':
            session.add(NetworkProductionActivationModel(project_id=project_id,network_id=resource_id,
                version_id=release_id,previous_version_id=previous_release_id,
                activation_kind='rollback' if action=='rollback' else 'reactivate',change_description=reason,
                created_by=getattr(principal,'user_id',None)))

    def add_outbox(self,session,*,model,identifier,resource_id,operation_id,receipt):
        session.add(model(id=identifier,aggregate_type='network',aggregate_id=resource_id,
            event_type='network.asac.environment.selected',event_version=1,routing_key='network.asac.environment.selected',
            payload=receipt,metadata_={'schema_version':'1.0'},idempotency_key='asac-deployment:'+receipt['deployment_id'],
            correlation_id=operation_id,causation_id=identifier,status='pending',attempts=0))
