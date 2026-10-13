"""Preserve old Environment envelopes while sharing the new write authority."""
from uuid import UUID

from sqlalchemy import select

from modules.core.infra.database.configuration_store import ConfigurationStore
from modules.core.infra.database.configuration_models import ConfigurationReferenceModel
from modules.core.infra.database.models import ProjectEnvironmentKeyModel as Key, ProjectEnvironmentValueModel as Value
from shared.contracts.project_configuration import ConfigurationError
from shared.project_environment import ProjectEnvironmentService, normalize_project_environment_key, normalize_project_environment_kind
from shared.runtime_environment import normalize_runtime_environment


class LegacyProjectEnvironmentService(ProjectEnvironmentService):
    async def upsert_key(self, *, project_id, key, kind=None, values, clear_environments=()):
        key = normalize_project_environment_key(key)
        async with self._session_factory() as session, session.begin():
            store = ConfigurationStore(session, encryption_key=self._encryption_key)
            await store.lock_project(project_id)
            existing = await session.scalar(select(Key).where(Key.project_id == project_id, Key.key == key).with_for_update())
            resolved_kind = normalize_project_environment_kind(kind if kind is not None else existing.kind if existing else "value")
            if existing is None:
                declaration = await store.declare(project_id=project_id, key=key, kind=resolved_kind,
                    value_format="string", validation_rules={"allow_empty": resolved_kind == "value"}, actor="legacy-client")
                existing = await store.key(project_id, UUID(declaration["id"]), lock=True)
            elif resolved_kind != existing.kind:
                value = await session.scalar(select(Value.id).where(Value.key_id == existing.id).limit(1))
                reference = await session.scalar(select(ConfigurationReferenceModel.id).where(ConfigurationReferenceModel.key_id == existing.id).limit(1))
                if value or reference:
                    raise ConfigurationError("CONFIG_KIND_MISMATCH", key=key)
                existing.kind, existing.definition_revision = resolved_kind, existing.definition_revision + 1
                existing.validation_rules = {"allow_empty": resolved_kind == "value"}
            clear = {normalize_runtime_environment(env) for env in clear_environments}
            updates = {normalize_runtime_environment(env): str(value) for env, value in values.items() if value is not None}
            for environment in sorted(clear | updates.keys()):
                slot = await session.scalar(select(Value).where(Value.key_id == existing.id, Value.environment == environment).with_for_update())
                await store.write_value(project_id=project_id, key_id=existing.id, environment=environment,
                    expected_revision=slot.revision if slot else 0, value=updates.get(environment),
                    clear=environment in clear and environment not in updates, actor="legacy-client")
        return next(item for item in await self.list_keys(project_id=project_id) if item["key"] == key)

    async def delete_key(self, *, project_id, key):
        async with self._session_factory() as session, session.begin():
            store = ConfigurationStore(session, encryption_key=self._encryption_key)
            existing = await store.key(project_id, normalize_project_environment_key(key), lock=True)
            await store.remove_key(project_id=project_id, key_id=existing.id,
                expected_revision=existing.definition_revision, actor="legacy-client")
