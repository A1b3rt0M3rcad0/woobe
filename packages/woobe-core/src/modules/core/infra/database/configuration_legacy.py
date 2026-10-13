"""Central legacy aliases: explicit compatibility routes, never env fallback."""
from uuid import UUID, uuid4
import hashlib
import re

from sqlalchemy import select, func

from modules.core.infra.database.configuration_models import (
    LegacyConfigurationAliasModel as Alias, LegacyConfigurationValueModel as Material,
    ConfigurationValueVersionModel as Version,
)
from modules.core.infra.database.configuration_resolution import ConfigurationResolution
from modules.core.infra.database.models import ProjectEnvironmentKeyModel as Key, ProjectEnvironmentValueModel as Value
from modules.core.domain.project_configuration import validate_material
from shared.contracts.project_configuration import ConfigurationDependency, ConfigurationError
from shared.infra.crypto import decrypt_secret
from shared.runtime_environment import normalize_runtime_environment


class LegacyConfigurationStore(ConfigurationResolution):
    async def require_bridge(self, *, required_processes):
        from modules.core.infra.database.configuration_fleet import assert_configuration_bridge
        await assert_configuration_bridge(self.session, required_processes=required_processes)

    async def legacy_bindings(self, *, project_id, environment="draft", limit=50, offset=0):
        environment = normalize_runtime_environment(environment)
        if not 1 <= limit <= 200 or offset < 0:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        count = await self.session.scalar(select(func.count()).select_from(Alias).where(Alias.project_id == project_id))
        rows = (await self.session.execute(select(Alias.id, Alias.source_kind, Alias.source_id,
            Alias.field_path, Alias.revision, Alias.state, Alias.routes, Key.key, Key.id.label("key_id"),
            Material.material_state, Material.revoked).join(Key, Key.id == Alias.key_id)
            .outerjoin(Material, Material.alias_id == Alias.id).where(Alias.project_id == project_id)
            .order_by(Alias.id).limit(limit).offset(offset))).all()
        return {"items": [{"id": str(row.id), "key_id": str(row.key_id), "key": row.key,
            "source_kind": row.source_kind, "source_id": str(row.source_id), "field_path": row.field_path,
            "revision": row.revision, "state": row.state, "source": row.routes.get(environment, "none"),
            "material": "revoked" if row.revoked else row.material_state or "missing"} for row in rows],
            "environment": environment, "total": count, "offset": offset, "limit": limit}

    async def adopt(self, *, project_id, source_kind, source_id, field_path, source_revision,
                    encrypted_value, dependencies, actor):
        """Called in the source writer's transaction after locking its source row.

        The caller clears the old active field in the same transaction. Matching
        source identity/revision makes backfill restartable without re-encryption
        or duplicate declarations. This operation never selects an Environment.
        """
        if source_kind not in {"provider_credential", "secret", "tool", "mcp_oauth"}:
            raise ConfigurationError("LEGACY_FORMAT_UNSUPPORTED")
        await self.lock_project(project_id)
        alias = await self.session.scalar(select(Alias).where(Alias.project_id == project_id,
            Alias.source_kind == source_kind, Alias.source_id == source_id, Alias.field_path == field_path).with_for_update())
        if alias:
            if alias.source_revision != source_revision:
                raise ConfigurationError("CONFIG_REVISION_CONFLICT")
            key_name = await self.session.scalar(select(Key.key).where(Key.id == alias.key_id))
            material_state = await self.session.scalar(select(Material.material_state).where(Material.alias_id == alias.id))
            return {"alias_id": str(alias.id), "key_id": str(alias.key_id), "key": key_name, "state": material_state or "missing", "phase": alias.state, "unchanged": True}
        # Full source UUID avoids name collisions and does not disclose material.
        base = ("PROVIDER" if source_kind == "provider_credential" else source_kind.upper()) + "_" + source_id.hex
        suffix = "_" + re.sub(r"[^A-Z0-9_]", "_", field_path.rsplit("/", 1)[-1].upper())
        name = (base + suffix)[:128]
        existing = await self.session.scalar(select(Key.id).where(Key.project_id == project_id, Key.key == name))
        if existing:
            # Never overwrite a user declaration that happens to use this name.
            discriminator = hashlib.sha256((field_path + ":" + str(source_revision)).encode()).hexdigest()[:12]
            name = base + "_" + discriminator
        key = await self.declare(project_id=project_id, key=name, kind="secret", value_format="string",
                                 origin="migration", actor=actor)
        alias = Alias(project_id=project_id, key_id=UUID(key["id"]), source_kind=source_kind,
            source_id=source_id, field_path=field_path, source_revision=source_revision,
            routes={env: "legacy_compat" for env in ("draft", "staging", "production")}, state="cutover", revision=1)
        self.session.add(alias)
        await self.session.flush()
        state = "missing"
        if encrypted_value:
            try:
                plain = decrypt_secret(encrypted_value, self.encryption_key)
                if plain == "":
                    state = "missing"
                    encrypted_value = None
                else:
                    validate_material(plain, kind="secret", value_format="string", rules={})
                    state = "present"
            except Exception:
                state = "unavailable"
        self.session.add(Material(alias_id=alias.id, stored_value=encrypted_value or None,
            value_version=uuid4(), revision=1, material_state=state, revoked=False))
        destinations = set()
        for dependency in dependencies:
            if (dependency.project_id != project_id or dependency.consumer_id != source_id
                    or dependency.consumer_kind != source_kind or dependency.field_path != field_path):
                raise ConfigurationError("CONFIG_USAGE_NOT_AUTHORIZED")
            if dependency.destination not in destinations:
                await self.grant_use(project_id=project_id, key_id=alias.key_id, consumer_kind=source_kind,
                    consumer_scope=str(source_id), destination=dependency.destination,
                    environments=["draft", "staging", "production"], field_paths=[field_path],
                    expected_revision=0, actor=actor)
                destinations.add(dependency.destination)
        reference = ConfigurationDependency(project_id, source_kind, source_id, source_revision,
            field_path, name, "", legacy_alias_id=alias.id)
        await self.register_references([reference])
        await self.session.flush()
        await self.audit(project_id, "legacy.adopted", actor, alias_id=str(alias.id), key_id=str(alias.key_id), state=state)
        return {"alias_id": str(alias.id), "key_id": str(alias.key_id), "key": name, "state": state, "phase": alias.state, "unchanged": False}

    async def convert(self, *, project_id, alias_id, environments, expected_revision, expected_values, actor):
        # Caller has independently authorized migrate + value:write for every
        # chosen Environment. No value returns to the operator or HTTP caller.
        await self.lock_project(project_id)
        alias = await self.session.scalar(select(Alias).where(Alias.project_id == project_id, Alias.id == alias_id).with_for_update())
        if alias is None:
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        key = await self.key(project_id, alias.key_id, lock=True)
        if alias.revision != expected_revision:
            raise ConfigurationError("CONFIG_REVISION_CONFLICT")
        environments = sorted({normalize_runtime_environment(env) for env in environments})
        if not environments or set(expected_values) != set(environments):
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        material = await self.session.scalar(select(Material).where(Material.alias_id == alias.id).with_for_update())
        if not material or material.material_state != "present" or material.revoked:
            raise ConfigurationError("CONFIG_VERSION_UNAVAILABLE")
        try:
            plain = decrypt_secret(material.stored_value, self.encryption_key)
        except Exception:
            raise ConfigurationError("CONFIG_STORE_UNAVAILABLE") from None
        for env in environments:
            if alias.routes.get(env) != "legacy_compat":
                raise ConfigurationError("CONFIG_REVISION_CONFLICT")
            await self.write_value(project_id=project_id, key_id=key.id, environment=env,
                expected_revision=expected_values[env], value=plain, actor=actor)
        alias.routes = {**alias.routes, **{env: "environment" for env in environments}}
        alias.revision += 1
        if all(route == "environment" for route in alias.routes.values()):
            await self._archive(key, material, source="legacy:" + str(alias.id))
            material.stored_value, material.material_state, material.value_version = None, "missing", uuid4()
            alias.state = "completed"
        await self.session.flush()
        await self.audit(project_id, "legacy.converted", actor, alias_id=str(alias.id), revision=alias.revision)
        return {"alias_id": str(alias.id), "revision": alias.revision, "routes": alias.routes, "state": alias.state}

    async def rotate_legacy(self, *, project_id, alias_id, encrypted_value, source_revision, actor):
        await self.lock_project(project_id)
        alias = await self.session.scalar(select(Alias).where(Alias.project_id == project_id, Alias.id == alias_id).with_for_update())
        if alias is None:
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        if any(route != "legacy_compat" for route in alias.routes.values()):
            raise ConfigurationError("LEGACY_ENVIRONMENT_REQUIRED")
        key = await self.key(project_id, alias.key_id, lock=True)
        try:
            validate_material(decrypt_secret(encrypted_value, self.encryption_key), kind=key.kind,
                              value_format=key.value_format, rules=key.validation_rules)
        except Exception:
            raise ConfigurationError("CONFIG_VALUE_INVALID") from None
        material = await self.session.scalar(select(Material).where(Material.alias_id == alias.id).with_for_update())
        await self._archive(key, material, source="legacy:" + str(alias.id))
        material.stored_value, material.value_version = encrypted_value, uuid4()
        material.material_state, material.revoked = "present", False
        material.revision += 1
        alias.source_revision = source_revision
        alias.revision += 1
        await self.session.flush()
        await self.audit(project_id, "legacy.rotated", actor, alias_id=str(alias.id), revision=alias.revision)
