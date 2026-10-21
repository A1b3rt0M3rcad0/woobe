"""Batched metadata readiness and internal, version-pinned material resolution."""
from __future__ import annotations

from datetime import timedelta
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib
import json
from uuid import UUID
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select

from modules.core.domain.project_configuration import canonical_destination, VERSION_RETENTION_SECONDS
from modules.core.domain.configuration_protocol_metadata import validate_protocol_metadata
from modules.core.infra.database.configuration_models import (
    ConfigurationLeaseModel, ConfigurationValidationModel, ConfigurationUsePolicyModel as Policy,
    ConfigurationValueVersionModel as Version, LegacyConfigurationAliasModel as Alias,
    LegacyConfigurationValueModel as LegacyValue, LegacyConfigurationConsumerModel as LegacyConsumer,
)
from modules.core.infra.database.configuration_store import ConfigurationStore, now
from modules.core.infra.database.models import ProjectEnvironmentKeyModel as Key, ProjectEnvironmentValueModel as Value
from shared.contracts.project_configuration import ConfigurationDependency, ConfigurationError, ConfigurationValuePin, ConfigurationResolvedValue
from shared.infra.crypto import decrypt_secret
from shared.runtime_environment import normalize_runtime_environment


def destination_matches(approved: str, actual: str) -> bool:
    # Grants describe scheme/host/port/path. Query parameters belong to the
    # operation, never to credential delivery or the approved origin identity.
    parsed = urlsplit(actual)
    actual = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", parsed.fragment))
    approved, actual = canonical_destination(approved), canonical_destination(actual)
    return actual == approved or actual.startswith(approved.rstrip("/") + "/")


def matching_policy(policies, dep, environment):
    matches = [p for p in policies if p.consumer_kind == dep.consumer_kind
               and p.consumer_scope in {"*", str(dep.consumer_id)}
               and environment in p.environments and dep.field_path in p.field_paths
               and not p.revoked and destination_matches(p.destination, dep.destination)]
    # An exact consumer policy takes precedence. Stable ordering makes the
    # selected evidence independent of the database's row order.
    return sorted(matches, key=lambda p: (p.consumer_scope == "*", -len(p.destination), str(p.id)))[0] if matches else None


def normalize_dependencies(dependencies):
    merged = {}
    for dep in dependencies:
        identity = (*dep.identity, canonical_destination(dep.destination))
        previous = merged.get(identity)
        if previous is None:
            merged[identity] = replace(dep, destination=identity[-1])
            continue
        if (previous.definition_revision, previous.kind, previous.legacy_alias_id) != (
                dep.definition_revision, dep.kind, dep.legacy_alias_id):
            raise ConfigurationError("CONFIG_REVISION_CONFLICT")
        # An optional path never weakens another required path to the same key.
        merged[identity] = replace(previous, required=previous.required or dep.required,
            impact=tuple(sorted(set(previous.impact) | set(dep.impact))))
    return [merged[key] for key in sorted(merged)]


def dependency_digest(dependencies):
    documents = [asdict(dep) for dep in dependencies]
    return hashlib.sha256(json.dumps(documents, default=str, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


class ConfigurationResolution(ConfigurationStore):
    async def inspect(self, *, project_id, environment, dependencies: list[ConfigurationDependency], lock=False):
        environment = normalize_runtime_environment(environment)
        self._require_project(project_id, dependencies)
        dependencies = normalize_dependencies(dependencies)
        metadata = await self._read_metadata(project_id, environment, dependencies, lock=lock)
        return self._inspect_metadata(environment, dependencies, metadata)

    async def inspect_many(self, *, project_id, environment, groups):
        """One metadata observation for independently authorized target closures.

        Never merge definitions across targets: two Releases may legitimately
        bind different revisions of the same Tool. Admission still normalizes and
        locks one exact closure independently through inspect/acquire.
        """
        environment = normalize_runtime_environment(environment)
        for dependencies in groups:
            self._require_project(project_id, dependencies)
        normalized = [normalize_dependencies(dependencies) for dependencies in groups]
        metadata = await self._read_metadata(project_id, environment,
            [dep for dependencies in normalized for dep in dependencies], lock=False)
        return [self._inspect_metadata(environment, dependencies, metadata) for dependencies in normalized]

    @staticmethod
    def _require_project(project_id, dependencies):
        if any(dep.project_id != project_id for dep in dependencies):
            raise ConfigurationError("CONFIG_USAGE_NOT_AUTHORIZED")

    async def _read_metadata(self, project_id, environment, dependencies, *, lock):
        names = sorted({dep.key for dep in dependencies})
        query = select(Key).where(Key.project_id == project_id, Key.key.in_(names)).order_by(Key.key)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        keys = {k.key: k for k in (await self.session.scalars(query)).all()} if names else {}
        ids = [key.id for key in keys.values()]
        # Never select stored_value on this path: status must not decrypt or
        # perform an external validation, even when the value is present.
        values = {row.key_id: row for row in (await self.session.execute(select(
            Value.key_id, Value.value_version, Value.material_state, Value.revoked,
        ).where(Value.key_id.in_(ids), Value.environment == environment))).all()} if ids else {}
        policies = (await self.session.scalars(select(Policy).where(
            Policy.project_id == project_id, Policy.key_id.in_(ids)))).all() if ids else []
        policy_index = defaultdict(list)
        for policy in policies:
            policy_index[(policy.key_id, policy.consumer_kind, policy.consumer_scope)].append(policy)
        alias_ids = [dep.legacy_alias_id for dep in dependencies if dep.legacy_alias_id]
        aliases = {a.id: a for a in (await self.session.scalars(select(Alias).where(
            Alias.project_id == project_id, Alias.id.in_(alias_ids)))).all()} if alias_ids else {}
        legacy_consumers = {(row.alias_id, row.consumer_kind, row.consumer_id, row.field_path)
            for row in (await self.session.scalars(select(LegacyConsumer).where(
                LegacyConsumer.alias_id.in_(aliases), LegacyConsumer.consumer_id.in_({dep.consumer_id for dep in dependencies})))).all()} if aliases else set()
        legacy = {v.alias_id: v for v in (await self.session.execute(select(
            LegacyValue.alias_id, LegacyValue.value_version, LegacyValue.material_state, LegacyValue.revoked,
        ).where(LegacyValue.alias_id.in_(aliases)))).all()} if aliases else {}
        consumer_ids = {dep.consumer_id for dep in dependencies}
        validation_rows = (await self.session.scalars(select(ConfigurationValidationModel).where(
            ConfigurationValidationModel.project_id == project_id,
            ConfigurationValidationModel.environment == environment,
            ConfigurationValidationModel.consumer_id.in_(consumer_ids)).order_by(
                ConfigurationValidationModel.consumer_kind, ConfigurationValidationModel.consumer_id,
                ConfigurationValidationModel.created_at.desc(), ConfigurationValidationModel.id.desc())
            .distinct(ConfigurationValidationModel.consumer_kind, ConfigurationValidationModel.consumer_id))).all() if consumer_ids else []
        validations = {(v.consumer_kind, v.consumer_id): v for v in validation_rows}
        return keys, values, policy_index, aliases, legacy_consumers, legacy, validations

    @staticmethod
    def _inspect_metadata(environment, dependencies, metadata):
        keys, values, policy_index, aliases, legacy_consumers, legacy, validations = metadata
        items, pins = [], []
        for dep in dependencies:
            key = keys.get(dep.key)
            candidates = ([*policy_index[(key.id, dep.consumer_kind, str(dep.consumer_id))],
                           *policy_index[(key.id, dep.consumer_kind, "*")]] if key else [])
            policy = matching_policy(candidates, dep, environment)
            alias = aliases.get(dep.legacy_alias_id)
            if dep.legacy_alias_id is not None and alias is None:
                raise ConfigurationError("CONFIG_REFERENCE_NOT_FOUND")
            source, slot = "none", None
            if alias is not None:
                same_owner = (alias.source_kind == dep.consumer_kind and alias.source_id == dep.consumer_id
                    and alias.field_path == dep.field_path)
                captured_consumer = (alias.id, dep.consumer_kind, dep.consumer_id, dep.field_path) in legacy_consumers
                if not key or alias.key_id != key.id or not (same_owner or captured_consumer):
                    raise ConfigurationError("CONFIG_USAGE_NOT_AUTHORIZED")
                route = alias.routes.get(environment)
                if route == "legacy_compat":
                    source, slot = "legacy_compat", legacy.get(alias.id)
                elif route == "environment":
                    source, slot = "environment", values.get(key.id)
            elif key:
                source, slot = "environment", values.get(key.id)
            material = "revoked" if slot and slot.revoked else slot.material_state if slot else "missing"
            code = None
            if key is None:
                code = "CONFIG_REFERENCE_NOT_FOUND"
            elif key.kind != dep.kind:
                code = "CONFIG_KIND_MISMATCH"
            elif policy is None:
                code = "CONFIG_USAGE_NOT_AUTHORIZED"
            elif material != "present":
                code = {"missing": "CONFIG_VALUE_MISSING", "revoked": "CONFIG_VALUE_REVOKED",
                        "invalid_format": "CONFIG_VALUE_INVALID", "unavailable": "CONFIG_STORE_UNAVAILABLE"}[material]
            elif not slot.value_version:
                code = "CONFIG_VERSION_UNAVAILABLE"
            external_state = "not_tested"
            validation = validations.get((dep.consumer_kind, dep.consumer_id))
            if validation is not None:
                evidence = validation.evidence.get("pins", [])
                expected = {"key_id": str(key.id) if key else None, "version": str(slot.value_version) if slot else None,
                    "source": source, "field_path": dep.field_path, "destination": canonical_destination(dep.destination),
                    "policy_revision": policy.revision if policy else None, "policy_id": str(policy.id) if policy else None}
                external_state = validation.state if code is None and any(all(pin.get(k) == v for k, v in expected.items()) for pin in evidence) else "stale"
            item = {"key": dep.key, "consumer_kind": dep.consumer_kind, "consumer_id": str(dep.consumer_id),
                    "field_path": dep.field_path, "required": dep.required,
                    "material": material, "external_validation": external_state, "source": source,
                    "code": code, "impact": [list(path) for path in dep.impact]}
            items.append(item)
            if code is None:
                pins.append(ConfigurationValuePin(key.id, slot.value_version, environment, source,
                    dep.consumer_kind, dep.consumer_id, dep.field_path, canonical_destination(dep.destination),
                    policy.revision, policy.id, alias.id if alias else None))
        blockers = [i for i in items if i["code"] and i["required"]]
        unknown = any(i["code"] == "CONFIG_STORE_UNAVAILABLE" for i in blockers)
        notices = any(i["code"] or i["external_validation"] != "valid" or i["source"] == "legacy_compat" for i in items)
        state = "unknown" if unknown else "blocked" if blockers else "ready_with_notices" if notices else "ready"
        return {"environment": environment, "state": state, "dependencies": items,
                "required_key_count": len({i["key"] for i in items if i["required"]}),
                "missing_key_count": len({i["key"] for i in blockers if i["material"] == "missing"}),
                "affected_consumer_count": len({(i["consumer_kind"], i["consumer_id"]) for i in blockers})}, pins

    async def record_validation(self, *, project_id, run_id, consumer_kind, consumer_id, state, actor):
        if state not in {"valid", "invalid", "unknown"}:
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
        lease = await self.session.scalar(select(ConfigurationLeaseModel).where(
            ConfigurationLeaseModel.project_id == project_id, ConfigurationLeaseModel.run_id == run_id))
        if lease is None or lease.expires_at <= now():
            raise ConfigurationError("CONFIG_VERSION_UNAVAILABLE")
        pins = [pin for pin in lease.pins if pin["consumer_kind"] == consumer_kind and pin["consumer_id"] == str(consumer_id)]
        if not pins:
            raise ConfigurationError("CONFIG_USAGE_NOT_AUTHORIZED")
        self.session.add(ConfigurationValidationModel(project_id=project_id, consumer_kind=consumer_kind,
            consumer_id=consumer_id, environment=lease.environment, state=state,
            evidence={"run_id": str(run_id), "pins": pins}, actor=actor))
        await self.session.flush()
        return {"state": state, "environment": lease.environment}

    async def activation_evidence(self, *, project_id, environment, dependencies):
        """Qualify one exact closure without decrypting or creating a Run lease.

        The caller owns the activation transaction. Project/key locks fence
        rotation, policy edits and declaration changes until its commit.
        """
        environment = normalize_runtime_environment(environment)
        dependencies = normalize_dependencies(dependencies)
        await self.lock_project(project_id)
        result, pins = await self.inspect(project_id=project_id, environment=environment,
            dependencies=dependencies, lock=True)
        for item in result["dependencies"]:
            if item["required"] and item["code"]:
                raise ConfigurationError(item["code"], key=item["key"], environment=environment)
        names = {dependency.key for dependency in dependencies}
        definitions = (await self.session.execute(select(Key.id, Key.definition_revision).where(
            Key.project_id == project_id, Key.key.in_(names)).order_by(Key.id))).all() if names else []
        return {"schema_version": "1", "environment": environment,
            "dependency_digest": dependency_digest(dependencies),
            "definitions": [{"key_id": str(row.id), "revision": row.definition_revision} for row in definitions],
            "pins": [pin.document() for pin in pins]}

    async def acquire(self, *, project_id, run_id, environment, dependencies):
        # Project lock serializes lease retries; key locks serialize acceptance
        # against value rotation/deletion. Caller commits with Run acceptance.
        environment = normalize_runtime_environment(environment)
        dependencies = normalize_dependencies(dependencies)
        if any(dep.project_id != project_id for dep in dependencies):
            raise ConfigurationError("CONFIG_USAGE_NOT_AUTHORIZED")
        digest = dependency_digest(dependencies)
        await self.lock_project(project_id)
        existing = await self.session.scalar(select(ConfigurationLeaseModel).where(
            ConfigurationLeaseModel.project_id == project_id, ConfigurationLeaseModel.run_id == run_id))
        if existing:
            if existing.environment != environment or existing.dependency_digest != digest:
                raise ConfigurationError("CONFIG_REVISION_CONFLICT")
            if existing.expires_at <= now():
                raise ConfigurationError("CONFIG_VERSION_UNAVAILABLE")
            return existing.pins
        result, pins = await self.inspect(project_id=project_id, environment=environment, dependencies=dependencies, lock=True)
        for item in result["dependencies"]:
            if item["required"] and item["code"]:
                raise ConfigurationError(item["code"], key=item["key"], environment=environment)
        document = [pin.document() for pin in pins]
        self.session.add(ConfigurationLeaseModel(project_id=project_id, run_id=run_id,
            environment=environment, pins=document, dependency_digest=digest,
            expires_at=now() + timedelta(seconds=VERSION_RETENTION_SECONDS)))
        await self.session.flush()
        return document

    async def resolve(self, *, project_id, run_id, consumer_kind, consumer_id, field_path, destination):
        resolved = await self.resolve_with_metadata(project_id=project_id, run_id=run_id,
            consumer_kind=consumer_kind, consumer_id=consumer_id, field_path=field_path, destination=destination)
        return resolved.value

    async def resolve_with_metadata(self, *, project_id, run_id, consumer_kind, consumer_id, field_path, destination):
        lease = await self.session.scalar(select(ConfigurationLeaseModel).where(
            ConfigurationLeaseModel.project_id == project_id, ConfigurationLeaseModel.run_id == run_id,
            ConfigurationLeaseModel.expires_at > now()))
        if lease is None:
            raise ConfigurationError("CONFIG_VERSION_UNAVAILABLE")
        return await self._resolve_pinned_material(project_id=project_id, environment=lease.environment,
            pins=lease.pins, consumer_kind=consumer_kind, consumer_id=consumer_id,
            field_path=field_path, destination=destination)

    async def verify_operation_evidence(self, *, project_id, environment, dependencies, evidence):
        """Check current approval/definitions without locks or decrypting material.

        Value rotation is allowed; callers retain their accepted version pins.
        This path also fences publication of a recovered cached model result.
        """
        environment = normalize_runtime_environment(environment)
        self._require_project(project_id, dependencies)
        dependencies = normalize_dependencies(dependencies)
        metadata = await self._read_metadata(project_id, environment, dependencies, lock=False)
        result, current_pins = self._inspect_metadata(environment, dependencies, metadata)
        for item in result['dependencies']:
            if item['required'] and item['code']:
                raise ConfigurationError(item['code'])
        keys = metadata[0]
        definitions = sorted([{'key_id': str(key.id), 'revision': key.definition_revision}
            for key in keys.values()], key=lambda item: item['key_id'])
        if (evidence.get('environment') != environment
            or sorted(evidence.get('definitions', []), key=lambda item: item['key_id']) != definitions):
            raise ConfigurationError('CONFIG_REVISION_CONFLICT')
        # The immutable accepted value version is checked on actual resolution;
        # all other current pin authority must still match for cache reuse.
        def authority(pin):
            return {name: value for name, value in pin.items() if name != 'version'}
        accepted = sorted([authority(pin) for pin in evidence.get('pins', [])], key=lambda pin: str(pin))
        current = sorted([authority(pin.document()) for pin in current_pins], key=lambda pin: str(pin))
        if accepted != current:
            raise ConfigurationError('CONFIG_REVISION_CONFLICT')
        return True

    async def resolve_operation_material(self, *, project_id, environment, pins, definitions,
                                         consumer_kind, consumer_id, field_path, destination):
        # Only the operation resolver calls this after its host-supplied verifier
        # has loaded the durable accepted operation's stored snapshot. Pins here
        # are never accepted from an HTTP body or a model response.
        environment = normalize_runtime_environment(environment)
        if any(pin.get('source') != 'environment' or pin.get('environment') != environment for pin in pins):
            raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
        revisions = {str(item['key_id']): item['revision'] for item in definitions}
        for pin in pins:
            key = await self.key(project_id, UUID(pin['key_id']))
            if revisions.get(str(key.id)) != key.definition_revision:
                raise ConfigurationError('CONFIG_REVISION_CONFLICT')
        return await self._resolve_pinned_material(project_id=project_id, environment=environment,
            pins=pins, consumer_kind=consumer_kind, consumer_id=consumer_id,
            field_path=field_path, destination=destination)

    async def _resolve_pinned_material(self, *, project_id, environment, pins, consumer_kind,
                                       consumer_id, field_path, destination):
        matches = [p for p in pins if p["consumer_kind"] == consumer_kind
                   and p["consumer_id"] == str(consumer_id) and p["field_path"] == field_path
                   and destination_matches(p["destination"], destination)]
        if len(matches) != 1:
            raise ConfigurationError("CONFIG_DESTINATION_CHANGED")
        pin = matches[0]
        if not destination_matches(pin["destination"], destination):
            raise ConfigurationError("CONFIG_DESTINATION_CHANGED")
        key = await self.key(project_id, UUID(pin["key_id"]))
        dep = ConfigurationDependency(project_id, consumer_kind, consumer_id, "pinned", field_path, key.key, destination)
        policies = (await self.session.scalars(select(Policy).where(Policy.project_id == project_id, Policy.key_id == key.id))).all()
        policy = matching_policy(policies, dep, environment)
        if policy is None:
            raise ConfigurationError("CONFIG_USAGE_NOT_AUTHORIZED")
        # A policy edit invalidates in-flight authority instead of silently
        # expanding it. Reapproval can authorize a new accepted operation.
        if policy.revision != pin["policy_revision"] or str(policy.id) != pin["policy_id"]:
            raise ConfigurationError("CONFIG_REVISION_CONFLICT")
        version = UUID(pin["version"])
        if pin["source"] == "legacy_compat":
            source = "legacy:" + pin["alias_id"]
            alias = await self.session.scalar(select(Alias).where(Alias.id == UUID(pin["alias_id"]), Alias.project_id == project_id, Alias.key_id == key.id))
            if alias is None:
                raise ConfigurationError("CONFIG_VERSION_UNAVAILABLE")
            current = await self.session.scalar(select(LegacyValue).where(LegacyValue.alias_id == alias.id))
        else:
            source = environment
            current = await self.session.scalar(select(Value).where(Value.key_id == key.id, Value.environment == environment))
        material = current if current and current.value_version == version else await self.session.scalar(select(Version).where(
            Version.project_id == project_id, Version.key_id == key.id, Version.value_version == version,
            Version.source == source, Version.expires_at > now()))
        if material is None:
            raise ConfigurationError("CONFIG_VERSION_UNAVAILABLE")
        if material.revoked:
            raise ConfigurationError("CONFIG_VALUE_REVOKED")
        if material.stored_value is None:
            raise ConfigurationError("CONFIG_VERSION_UNAVAILABLE")
        try:
            value = decrypt_secret(material.stored_value, self.encryption_key) if key.kind == "secret" else material.stored_value
        except Exception:
            # Crypto/backend failures must not echo material or provider details.
            raise ConfigurationError("CONFIG_STORE_UNAVAILABLE") from None
        return ConfigurationResolvedValue(value=value, value_version=version, environment=environment,
            source=pin['source'], protocol_metadata=validate_protocol_metadata(deepcopy(material.protocol_metadata or {})))
