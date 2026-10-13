"""Transactional configuration persistence shared by every authorized consumer.

The caller owns the transaction. No method commits or performs external I/O.
Metadata reads select no encrypted value columns. Resolved material is only
returned by explicit internal runtime operations, never by the admin service.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, update

from modules.core.domain.project_configuration import (
    MAX_BATCH_SIZE, VERSION_RETENTION_SECONDS, canonical_destination,
    validate_declaration, validate_material,
)
from modules.core.infra.database.configuration_models import (
    ConfigurationAuditModel, ConfigurationLeaseModel, ConfigurationMutationModel, ConfigurationReferenceModel,
    ConfigurationUsePolicyModel, ConfigurationValueVersionModel,
    LegacyConfigurationAliasModel, LegacyConfigurationValueModel,
)
from modules.core.infra.database.models import (
    ProjectEnvironmentKeyModel as Key, ProjectEnvironmentValueModel as Value, ProjectModel,
)
from shared.contracts.errors import NotFoundError
from shared.contracts.project_configuration import ConfigurationDependency, ConfigurationError
from shared.infra.crypto import decrypt_secret, encrypt_secret
from shared.runtime_environment import normalize_runtime_environment


def now():
    return datetime.now(UTC)


def public_key(key: Key) -> dict:
    return {"id": str(key.id), "project_id": str(key.project_id), "key": key.key,
            "kind": key.kind, "description": key.description, "value_format": key.value_format,
            "validation_rules": key.validation_rules, "definition_revision": key.definition_revision,
            "origin": key.origin, "created_at": key.created_at.isoformat(),
            "updated_at": key.updated_at.isoformat()}


class ConfigurationStore:
    def __init__(self, session, *, encryption_key: str):
        self.session, self.encryption_key = session, encryption_key

    async def lock_project(self, project_id: UUID):
        found = await self.session.scalar(select(ProjectModel.id).where(ProjectModel.id == project_id).with_for_update())
        if found is None:
            raise NotFoundError("Project not found")

    async def key(self, project_id: UUID, identifier: UUID | str, *, lock=False) -> Key:
        predicate = Key.id == identifier if isinstance(identifier, UUID) else Key.key == identifier
        query = select(Key).where(Key.project_id == project_id, predicate)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = await self.session.scalar(query)
        if row is None:
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        return row

    async def audit(self, project_id, operation, actor, **evidence):
        # Keep this allowlist independent of any request dictionary.
        allowed = {"key_id", "environment", "value_version", "revision", "consumer_kind",
                   "consumer_id", "policy_id", "alias_id", "migration_id", "state", "count"}
        if set(evidence) - allowed:
            raise ValueError("Unsupported configuration audit evidence")
        self.session.add(ConfigurationAuditModel(project_id=project_id, operation=operation,
                                                actor=actor, evidence=evidence))

    async def declare(self, *, project_id, key, kind="secret", description="", value_format="token",
                      validation_rules=None, origin="manual", actor="system"):
        rules = validation_rules or {}
        validate_declaration(key, kind, value_format, rules)
        if not isinstance(description, str) or len(description) > 2048 or origin not in {"manual", "import", "migration"}:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        await self.lock_project(project_id)
        existing = await self.session.scalar(select(Key).where(Key.project_id == project_id, Key.key == key))
        if existing is not None:
            raise ConfigurationError("CONFIG_REVISION_CONFLICT", key=key)
        row = Key(id=uuid4(), project_id=project_id, key=key, kind=kind, description=description,
                  value_format=value_format, validation_rules=rules, definition_revision=1, origin=origin)
        self.session.add(row)
        await self.session.flush()
        await self.audit(project_id, "key.declared", actor, key_id=str(row.id), revision=1)
        return public_key(row)

    async def patch(self, *, project_id, key_id, expected_revision, changes, actor="system"):
        if set(changes) - {"description", "value_format", "validation_rules"}:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        row = await self.key(project_id, key_id, lock=True)
        if row.definition_revision != expected_revision:
            raise ConfigurationError("CONFIG_REVISION_CONFLICT", key=row.key)
        form = changes.get("value_format", row.value_format)
        rules = changes.get("validation_rules", row.validation_rules)
        validate_declaration(row.key, row.kind, form, rules)
        description = changes.get("description", row.description)
        if not isinstance(description, str) or len(description) > 2048:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        # Changes to format cannot relabel existing material without validating it.
        if form != row.value_format or rules != row.validation_rules:
            slots = (await self.session.scalars(select(Value).where(Value.key_id == row.id).with_for_update())).all()
            legacy_slots = (await self.session.scalars(select(LegacyConfigurationValueModel)
                .join(LegacyConfigurationAliasModel, LegacyConfigurationAliasModel.id == LegacyConfigurationValueModel.alias_id)
                .where(LegacyConfigurationAliasModel.key_id == row.id).with_for_update())).all()
            retained_slots = (await self.session.scalars(select(ConfigurationValueVersionModel).where(
                ConfigurationValueVersionModel.key_id == row.id, ConfigurationValueVersionModel.expires_at > now()).with_for_update())).all()
            for slot in [*slots, *legacy_slots, *retained_slots]:
                if slot.stored_value is not None and not slot.revoked:
                    try:
                        plain = decrypt_secret(slot.stored_value, self.encryption_key) if row.kind == "secret" else slot.stored_value
                    except Exception:
                        raise ConfigurationError("CONFIG_STORE_UNAVAILABLE") from None
                    validate_material(plain, kind=row.kind, value_format=form, rules=rules)
        row.description, row.value_format, row.validation_rules = description, form, rules
        row.definition_revision += 1
        row.updated_at = now()
        await self.session.flush()
        await self.audit(project_id, "key.updated", actor, key_id=str(row.id), revision=row.definition_revision)
        return public_key(row)

    async def list_keys(self, *, project_id, environment="draft", limit=50, offset=0,
                        search="", kind=None, status=None):
        environment = normalize_runtime_environment(environment)
        if not 1 <= limit <= 200 or offset < 0 or len(search) > 128:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        filters = [Key.project_id == project_id]
        if search:
            escaped = search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            filters.append((Key.key.ilike(f"%{escaped}%", escape="\\")) | Key.description.ilike(f"%{escaped}%", escape="\\"))
        if kind:
            if kind not in {"value", "secret"}:
                raise ConfigurationError("CONFIG_DEFINITION_INVALID")
            filters.append(Key.kind == kind)
        selected = select(Value.key_id).where(Value.environment == environment, Value.material_state == "present", Value.revoked.is_(False))
        if status == "configured":
            filters.append(Key.id.in_(selected))
        elif status == "missing":
            filters.append(~Key.id.in_(selected))
        elif status == "legacy":
            filters.append(Key.origin == "migration")
        elif status == "attention":
            filters.append(Key.id.in_(select(Value.key_id).where(Value.environment == environment,
                           Value.material_state.in_(["invalid_format", "revoked", "unavailable"]))))
        elif status not in {None, "all"}:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        total = await self.session.scalar(select(func.count()).select_from(Key).where(*filters))
        keys = (await self.session.scalars(select(Key).where(*filters).order_by(Key.key).offset(offset).limit(limit))).all()
        ids = [key.id for key in keys]
        slots = (await self.session.execute(select(Value.key_id, Value.environment, Value.revision,
                Value.value_version, Value.material_state, Value.revoked, Value.updated_at, Value.writer)
                .where(Value.key_id.in_(ids)))).mappings().all() if ids else []
        uses = (await self.session.execute(select(ConfigurationReferenceModel.key_id,
                func.count(func.distinct(ConfigurationReferenceModel.consumer_id)))
                .where(ConfigurationReferenceModel.project_id == project_id,
                       ConfigurationReferenceModel.key_id.in_(ids), ConfigurationReferenceModel.retained.is_(True))
                .group_by(ConfigurationReferenceModel.key_id))).all() if ids else []
        use_counts = dict(uses)
        by_id = {}
        for row in slots:
            by_id.setdefault(row["key_id"], {})[row["environment"]] = {
                "material": "revoked" if row["revoked"] else row["material_state"],
                "configured": row["material_state"] == "present" and not row["revoked"],
                "revision": row["revision"], "value_version": str(row["value_version"]) if row["value_version"] else None,
                "updated_at": row["updated_at"].isoformat(), "writer": row["writer"],
            }
        empty = {"material": "missing", "configured": False, "revision": 0, "value_version": None,
                 "updated_at": None, "writer": None}
        items = []
        for key in keys:
            item = public_key(key)
            item["values"] = {env: dict(by_id.get(key.id, {}).get(env, empty)) for env in ("draft", "staging", "production")}
            item["selected_environment"] = environment
            item["material"] = item["values"][environment]["material"]
            item["used_by_count"] = use_counts.get(key.id, 0)
            items.append(item)
        return {"items": items, "total": total, "limit": limit, "offset": offset,
                "has_next": offset + len(items) < total, "environment": environment}

    async def _archive(self, key: Key, slot, *, source: str):
        if slot.stored_value is None or slot.value_version is None:
            return
        self.session.add(ConfigurationValueVersionModel(project_id=key.project_id, key_id=key.id,
                         value_version=slot.value_version, source=source, stored_value=slot.stored_value,
                         revoked=slot.revoked, expires_at=now() + timedelta(seconds=VERSION_RETENTION_SECONDS)))

    async def write_value(self, *, project_id, key_id, environment, expected_revision,
                          value: str | None = None, clear=False, actor="system"):
        environment = normalize_runtime_environment(environment)
        key = await self.key(project_id, key_id, lock=True)
        slot = await self.session.scalar(select(Value).where(Value.key_id == key.id, Value.environment == environment)
                                         .with_for_update().execution_options(populate_existing=True))
        if (slot.revision if slot else 0) != expected_revision:
            raise ConfigurationError("CONFIG_REVISION_CONFLICT", key=key.key, environment=environment)
        if not clear:
            validate_material(value, kind=key.kind, value_format=key.value_format, rules=key.validation_rules)
        if slot is None:
            slot = Value(id=uuid4(), key_id=key.id, environment=environment, revision=0, revoked=False)
            self.session.add(slot)
        else:
            await self._archive(key, slot, source=environment)
        slot.revision += 1
        slot.value_version = uuid4()
        slot.writer, slot.updated_at = actor, now()
        slot.revoked = clear
        slot.material_state = "revoked" if clear else "present"
        slot.stored_value = None if clear else encrypt_secret(value, self.encryption_key) if key.kind == "secret" else value
        slot.crypto_key_id = "instance:v1" if key.kind == "secret" else None
        if clear:
            await self.session.flush()
            await self.session.execute(update(ConfigurationValueVersionModel).where(
                ConfigurationValueVersionModel.key_id == key.id,
                ConfigurationValueVersionModel.source == environment).values(revoked=True))
        await self.session.flush()
        await self.audit(project_id, "value.revoked" if clear else "value.written", actor,
                         key_id=str(key.id), environment=environment, revision=slot.revision,
                         value_version=str(slot.value_version))
        return {"key_id": str(key.id), "key": key.key, "environment": environment,
                "revision": slot.revision, "value_version": str(slot.value_version),
                "material": slot.material_state, "configured": not clear}

    async def write_batch(self, *, project_id, operations, actor, request_id):
        if (not isinstance(operations, list) or not 1 <= len(operations) <= MAX_BATCH_SIZE
                or not isinstance(request_id, str) or not 1 <= len(request_id) <= 128):
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        if any(not isinstance(item, dict) or not {"key_id", "environment", "expected_revision"} <= set(item)
               or set(item) - {"key_id", "environment", "expected_revision", "value", "clear"}
               or type(item["expected_revision"]) is not int or item["expected_revision"] < 0
               or not isinstance(item["environment"], str) for item in operations):
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        identities = [(str(item["key_id"]), item["environment"]) for item in operations]
        if len(set(identities)) != len(identities):
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        # An HMAC is private correlation evidence, never an externally visible
        # fingerprint. It is not persisted in receipts returned to clients.
        raw = json.dumps(operations, sort_keys=True, separators=(",", ":"), default=str).encode()
        digest = hmac.new(self.encryption_key.encode(), b"configuration-write-v1\x00" + raw, hashlib.sha256).hexdigest()
        await self.lock_project(project_id)
        record = await self.session.scalar(select(ConfigurationMutationModel).where(
            ConfigurationMutationModel.project_id == project_id, ConfigurationMutationModel.actor == actor,
            ConfigurationMutationModel.request_id == request_id))
        if record:
            if not hmac.compare_digest(record.request_mac, digest):
                raise ConfigurationError("CONFIG_REVISION_CONFLICT")
            return record.response
        # The outer transaction makes validation and all writes atomic. Lock in
        # stable order to avoid conflicting batches taking keys in reverse order.
        results = []
        for op in sorted(operations, key=lambda item: (str(item["key_id"]), item["environment"])):
            results.append(await self.write_value(project_id=project_id, actor=actor, **op))
        response = {"items": results, "request_id": request_id}
        self.session.add(ConfigurationMutationModel(project_id=project_id, actor=actor,
                         request_id=request_id, request_mac=digest, response=response))
        return response

    async def remove_key(self, *, project_id, key_id, expected_revision, actor):
        key = await self.key(project_id, key_id, lock=True)
        if key.definition_revision != expected_revision:
            raise ConfigurationError("CONFIG_REVISION_CONFLICT", key=key.key)
        references = await self.session.scalar(select(ConfigurationReferenceModel.id).where(
            ConfigurationReferenceModel.key_id == key.id, ConfigurationReferenceModel.retained.is_(True)).limit(1))
        alias = await self.session.scalar(select(LegacyConfigurationAliasModel.id).where(LegacyConfigurationAliasModel.key_id == key.id).limit(1))
        if references or alias:
            raise ConfigurationError("CONFIG_REFERENCE_IN_USE", key=key.key)
        # Retention alone is not a consumer: unused keys remain deletable.
        # A live Run lease protects both its current and archived material.
        lease = await self.session.scalar(select(ConfigurationLeaseModel.id).where(
            ConfigurationLeaseModel.project_id == project_id, ConfigurationLeaseModel.expires_at > now(),
            ConfigurationLeaseModel.pins.contains([{"key_id": str(key.id)}])).limit(1))
        if lease:
            raise ConfigurationError("CONFIG_REFERENCE_IN_USE", key=key.key)
        await self.session.execute(delete(ConfigurationUsePolicyModel).where(ConfigurationUsePolicyModel.key_id == key.id))
        await self.session.execute(delete(ConfigurationReferenceModel).where(ConfigurationReferenceModel.key_id == key.id))
        await self.session.execute(delete(ConfigurationValueVersionModel).where(ConfigurationValueVersionModel.key_id == key.id))
        await self.session.execute(delete(Value).where(Value.key_id == key.id))
        await self.session.delete(key)
        await self.audit(project_id, "key.deleted", actor, key_id=str(key.id))

    async def register_references(self, dependencies: list[ConfigurationDependency], *, retained=True):
        for dep in sorted(dependencies, key=lambda item: (str(item.project_id), item.key, item.field_path)):
            key = await self.key(dep.project_id, dep.key, lock=True)
            if key.kind != dep.kind:
                raise ConfigurationError("CONFIG_KIND_MISMATCH", key=key.key)
            match = [ConfigurationReferenceModel.project_id == dep.project_id,
                     ConfigurationReferenceModel.consumer_kind == dep.consumer_kind,
                     ConfigurationReferenceModel.consumer_id == dep.consumer_id,
                     ConfigurationReferenceModel.definition_revision == dep.definition_revision,
                     ConfigurationReferenceModel.field_path == dep.field_path,
                     ConfigurationReferenceModel.key_id == key.id]
            existing = await self.session.scalar(select(ConfigurationReferenceModel).where(*match))
            if existing is None:
                self.session.add(ConfigurationReferenceModel(project_id=dep.project_id, key_id=key.id,
                    consumer_kind=dep.consumer_kind, consumer_id=dep.consumer_id,
                    definition_revision=dep.definition_revision, field_path=dep.field_path,
                    destination=dep.destination, required=dep.required, retained=retained))
            elif existing.destination != dep.destination:
                raise ConfigurationError("CONFIG_REVISION_CONFLICT")
        await self.session.flush()

    async def grant_use(self, *, project_id, key_id, consumer_kind, consumer_scope, destination,
                        environments, field_paths, expected_revision, actor):
        key = await self.key(project_id, key_id, lock=True)
        destination = canonical_destination(destination)
        if consumer_kind not in {"provider_credential", "tool", "secret", "mcp_oauth"}:
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        if consumer_scope != "*":
            try:
                consumer_scope = str(UUID(consumer_scope))
            except (TypeError, ValueError, AttributeError):
                raise ConfigurationError("CONFIG_BINDING_INVALID") from None
        environments = sorted({normalize_runtime_environment(env) for env in environments})
        if (not environments or not field_paths or len(field_paths) > 32
                or any(not isinstance(path, str) or not path.startswith("/") or len(path) > 512 for path in field_paths)):
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        destination_id = hashlib.sha256(destination.encode()).hexdigest()
        row = await self.session.scalar(select(ConfigurationUsePolicyModel).where(
            ConfigurationUsePolicyModel.project_id == project_id, ConfigurationUsePolicyModel.key_id == key.id,
            ConfigurationUsePolicyModel.consumer_kind == consumer_kind,
            ConfigurationUsePolicyModel.consumer_scope == consumer_scope,
            ConfigurationUsePolicyModel.destination_id == destination_id).with_for_update())
        if (row.revision if row else 0) != expected_revision:
            raise ConfigurationError("CONFIG_REVISION_CONFLICT", key=key.key)
        if row is None:
            row = ConfigurationUsePolicyModel(project_id=project_id, key_id=key.id,
                consumer_kind=consumer_kind, consumer_scope=consumer_scope, destination=destination,
                destination_id=destination_id, revision=0)
            self.session.add(row)
        row.environments, row.field_paths = environments, sorted(set(field_paths))
        row.revision += 1
        row.actor, row.revoked = actor, False
        await self.session.flush()
        await self.audit(project_id, "usage.approved", actor, key_id=str(key.id),
                         policy_id=str(row.id), revision=row.revision)
        return {"id": str(row.id), "key_id": str(key.id), "revision": row.revision,
                "consumer_kind": consumer_kind, "consumer_scope": consumer_scope,
                "destination": destination, "environments": environments, "field_paths": row.field_paths}

    async def usage(self, *, project_id, key_id, limit=50, offset=0):
        key = await self.key(project_id, key_id)
        if not 1 <= limit <= 200 or offset < 0:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        filters = (ConfigurationReferenceModel.project_id == project_id,
                   ConfigurationReferenceModel.key_id == key.id, ConfigurationReferenceModel.retained.is_(True))
        count = await self.session.scalar(select(func.count()).select_from(ConfigurationReferenceModel).where(*filters))
        rows = (await self.session.scalars(select(ConfigurationReferenceModel).where(*filters)
                .order_by(ConfigurationReferenceModel.consumer_kind, ConfigurationReferenceModel.consumer_id,
                          ConfigurationReferenceModel.definition_revision, ConfigurationReferenceModel.field_path)
                .offset(offset).limit(limit))).all()
        return {"items": [{"consumer_kind": row.consumer_kind, "consumer_id": str(row.consumer_id),
                           "definition_revision": row.definition_revision, "field_path": row.field_path,
                           "required": row.required, "destination": row.destination} for row in rows],
                "total": count, "offset": offset, "limit": limit}

    async def list_use_policies(self, *, project_id, key_id, limit=50, offset=0):
        key = await self.key(project_id, key_id)
        if not 1 <= limit <= 200 or offset < 0:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        filters = (ConfigurationUsePolicyModel.project_id == project_id, ConfigurationUsePolicyModel.key_id == key.id)
        count = await self.session.scalar(select(func.count()).select_from(ConfigurationUsePolicyModel).where(*filters))
        rows = (await self.session.scalars(select(ConfigurationUsePolicyModel).where(*filters)
            .order_by(ConfigurationUsePolicyModel.id).offset(offset).limit(limit))).all()
        return {"items": [{"id": str(row.id), "consumer_kind": row.consumer_kind, "consumer_scope": row.consumer_scope,
            "destination": row.destination, "field_paths": row.field_paths, "environments": row.environments,
            "revision": row.revision, "revoked": row.revoked} for row in rows], "total": count, "offset": offset, "limit": limit}

    async def revoke_use(self, *, project_id, policy_id, expected_revision, actor):
        # Use the same key-before-policy order as grant/acceptance.
        key_id = await self.session.scalar(select(ConfigurationUsePolicyModel.key_id).where(
            ConfigurationUsePolicyModel.project_id == project_id, ConfigurationUsePolicyModel.id == policy_id))
        if key_id is None:
            raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
        await self.key(project_id, key_id, lock=True)
        policy = await self.session.scalar(select(ConfigurationUsePolicyModel).where(
            ConfigurationUsePolicyModel.project_id == project_id, ConfigurationUsePolicyModel.id == policy_id)
            .with_for_update().execution_options(populate_existing=True))
        if policy.revision != expected_revision:
            raise ConfigurationError("CONFIG_REVISION_CONFLICT")
        policy.revoked, policy.revision = True, policy.revision + 1
        await self.session.flush()
        await self.audit(project_id, "usage.revoked", actor, policy_id=str(policy.id), revision=policy.revision)
        return {"id": str(policy.id), "revision": policy.revision, "revoked": True}
