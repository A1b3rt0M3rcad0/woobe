"""Core-owned metadata locks fence environment rotation during deployment."""
from uuid import UUID
from sqlalchemy import select
from modules.core.infra.database.models import ProjectEnvironmentKeyModel, ProjectEnvironmentValueModel
from shared.contracts.errors import ConflictError


class ASaCEnvironmentBindingReader:
    async def verify(self,session,*,project_id,expected):
        for alias,evidence in sorted(expected.items()):
            row=await session.scalar(select(ProjectEnvironmentKeyModel).where(
                ProjectEnvironmentKeyModel.id==UUID(evidence['id']),ProjectEnvironmentKeyModel.project_id==project_id)
                .with_for_update())
            if row is None:
                raise ConflictError('ASAC_DEPLOYMENT_BINDINGS_CHANGED: Project Environment key unavailable')
            values=(await session.scalars(select(ProjectEnvironmentValueModel).where(
                ProjectEnvironmentValueModel.key_id==row.id).order_by(ProjectEnvironmentValueModel.environment)
                .with_for_update(read=True))).all()
            actual={'id':str(row.id),'existing_key':row.key,'kind':row.kind,'revision':row.updated_at.isoformat(),
                'environments':{value.environment:value.updated_at.isoformat() for value in values}}
            if actual!=evidence:
                raise ConflictError('ASAC_DEPLOYMENT_BINDINGS_CHANGED: Project Environment version differs')
