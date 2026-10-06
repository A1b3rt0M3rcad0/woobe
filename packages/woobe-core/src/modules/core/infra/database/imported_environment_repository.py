from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from modules.core.infra.database.models import (
    ProjectEnvironmentKeyModel,
    ProjectEnvironmentValueModel,
    ProjectModel,
)
from shared.contracts.errors import ConflictError, NotFoundError
from shared.infra.crypto import encrypt_secret
from shared.runtime_environment import RUNTIME_ENVIRONMENTS


class SQLAlchemyImportedEnvironmentRepository:
    """Create-only native keys; receipt and encrypted values share the owner UoW."""

    def __init__(self, uow, *, encryption_key):
        self._uow, self._encryption_key = uow, encryption_key

    async def create(self, definition):
        session = self._uow.session
        if await session.get(ProjectModel, definition.project_id) is None:
            raise NotFoundError("Project is unavailable")
        existing = await session.scalar(
            select(ProjectEnvironmentKeyModel.id).where(
                ProjectEnvironmentKeyModel.project_id == definition.project_id,
                ProjectEnvironmentKeyModel.key == definition.key,
            )
        )
        if existing is not None:
            raise ConflictError("Imported Project Environment key already exists")
        key = ProjectEnvironmentKeyModel(
            project_id=definition.project_id, key=definition.key, kind=definition.kind
        )
        stored = (
            encrypt_secret(definition.value, self._encryption_key)
            if definition.kind == "secret"
            else definition.value
        )
        try:
            session.add(key)
            await session.flush()
            session.add_all(
                [
                    ProjectEnvironmentValueModel(
                        key_id=key.id, environment=environment, stored_value=stored
                    )
                    for environment in RUNTIME_ENVIRONMENTS
                ]
            )
            await session.flush()
        except IntegrityError:
            raise ConflictError(
                "Imported Project Environment key already exists"
            ) from None
        return {
            "id": str(key.id),
            "key": key.key,
            "kind": key.kind,
            "project_id": str(key.project_id),
            "environments": list(RUNTIME_ENVIRONMENTS),
        }
