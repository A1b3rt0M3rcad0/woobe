"""Public owner gateway holds binding versions through the caller's commit."""
from uuid import UUID
from sqlalchemy import select
from modules.agent.infra.database.models import ProviderCredentialModel, AgentToolSecretModel
from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotModel
from modules.agent.infra.database.portable_export_reader import authorize_export_read
from shared.contracts.errors import ConflictError


class AgentASaCBindingGuard:
    def __init__(self,environment):
        self.environment=environment

    async def verify(self,session,*,project_id,resource_id,principal,environment,expected):
        for group,permission in (('credentials','provider:read'),('secrets','secret:read'),
            ('knowledge','knowledge:read'),('project_environment','project:environment:read')):
            if expected.get(group):
                await authorize_export_read(session,principal,project_id,permission,identifiers={'environment':environment})
        for alias,evidence in sorted(expected.get('credentials',{}).items()):
            if evidence.get('existing') is not True or 'credential_id' not in evidence:
                raise ConflictError('ASAC_DEPLOYMENT_BINDINGS_CHANGED: exact existing credentials required')
            row=await session.scalar(select(ProviderCredentialModel).where(
                ProviderCredentialModel.id==UUID(evidence['credential_id']),ProviderCredentialModel.project_id==project_id)
                .with_for_update(read=True))
            if row is None or row.status!='active' or {'credential_id':str(row.id),'provider':row.provider,
                'revision':row.updated_at.isoformat(),'existing':True}!=evidence:
                raise ConflictError('ASAC_DEPLOYMENT_BINDINGS_CHANGED: credential version unavailable')
        for alias,evidence in sorted(expected.get('secrets',{}).items()):
            if evidence.get('existing') is not True or 'secret_id' not in evidence:
                raise ConflictError('ASAC_DEPLOYMENT_BINDINGS_CHANGED: exact existing secrets required')
            row=await session.scalar(select(AgentToolSecretModel).where(
                AgentToolSecretModel.id==UUID(evidence['secret_id']),AgentToolSecretModel.project_id==project_id)
                .with_for_update(read=True))
            if row is None or {'secret_id':str(row.id),'name':row.name,'revision':row.updated_at.isoformat(),'existing':True}!=evidence:
                raise ConflictError('ASAC_DEPLOYMENT_BINDINGS_CHANGED: secret version unavailable')
        for alias,evidence in sorted(expected.get('knowledge',{}).items()):
            row=await session.scalar(select(VectorSnapshotModel).where(
                VectorSnapshotModel.id==UUID(evidence['vector_snapshot_id']),VectorSnapshotModel.project_id==project_id)
                .with_for_update(read=True))
            if row is None or row.status!='READY' or {'vector_snapshot_id':str(row.id),'collection_id':str(row.collection_id),
                'snapshot_hash':row.snapshot_hash,'revision':row.updated_at.isoformat(),
                'embedding_provider_model_id':str(row.embedding_provider_model_id)}!=evidence:
                raise ConflictError('ASAC_DEPLOYMENT_BINDINGS_CHANGED: Knowledge snapshot unavailable')
        await self.environment.verify(session,project_id=project_id,expected=expected.get('project_environment',{}))
