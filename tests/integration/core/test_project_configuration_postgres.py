"""Configuration authority: real PostgreSQL transactions and encrypted values."""
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select

from modules.core.infra.database.configuration_models import ConfigurationAuditModel, ConfigurationLeaseModel
from modules.core.infra.database.configuration_resolution import ConfigurationResolution
from modules.core.infra.database.models import ProjectModel, ProjectEnvironmentValueModel
from modules.identity.infra.database.models import WorkspaceModel
from shared.contracts.project_configuration import ConfigurationDependency, ConfigurationError
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory

CANARY = "configuration-private-canary-7c2f"


@pytest.mark.asyncio
async def test_host_protocol_registration_uses_unique_boot_identity_and_retires(configuration):
    from modules.core.infra.services.configuration_process import ConfigurationProcessRegistration
    from modules.core.infra.database.configuration_fleet import assert_configuration_bridge
    from modules.core.infra.database.configuration_models import ConfigurationProcessModel
    _, _, engine = configuration
    factory = create_session_factory(engine)
    api = ConfigurationProcessRegistration(factory, role="api")
    worker = ConfigurationProcessRegistration(factory, role="worker")
    assert api.identity != ConfigurationProcessRegistration(factory, role="api").identity
    try:
        await api.start()
        await worker.start()
        async with factory() as session, session.begin():
            await assert_configuration_bridge(session, required_processes=[api.identity, worker.identity])
        with pytest.raises(RuntimeError, match="already registered"):
            await api.start()
        await api.stop()
        async with factory() as session, session.begin():
            with pytest.raises(ConfigurationError) as error:
                await assert_configuration_bridge(session, required_processes=[api.identity, worker.identity])
            assert error.value.code == "CONFIG_BRIDGE_REQUIRED"
    finally:
        await api.stop()
        await worker.stop()
    async with factory() as session:
        assert await session.scalar(select(ConfigurationProcessModel.id).where(
            ConfigurationProcessModel.process_identity.in_([api.identity, worker.identity]))) is None


@pytest.mark.asyncio
async def test_provider_migration_job_is_metadata_only_resumable_and_revision_guarded(configuration, monkeypatch):
    import json
    from datetime import timedelta
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.infra.database.configuration_provider_migration import inventory_provider_configuration, migrate_provider_configuration
    from modules.agent.infra.database.models import ProviderCredentialModel
    from modules.core.infra.services.configuration_migration import ConfigurationMigrationService
    from modules.core.infra.database.configuration_fleet import register_configuration_process, BRIDGE_CAPABILITY
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from shared.infra.crypto import encrypt_secret
    original, project, engine = configuration
    store = LegacyConfigurationStore(original.session, encryption_key=original.encryption_key)
    monkeypatch.setattr(port, "_factory", lambda session: LegacyConfigurationStore(session, encryption_key=store.encryption_key))
    rows = [ProviderCredentialModel(id=UUID(int=900 + index), project_id=project, provider="openai",
        name=f"Migrating {index}", encrypted_secret=encrypt_secret(CANARY, store.encryption_key)) for index in range(3)]
    store.session.add_all(rows)
    await store.session.flush()
    service = ConfigurationMigrationService(store.session, encryption_key=store.encryption_key,
        inventory=inventory_provider_configuration, cutover=migrate_provider_configuration)
    selects = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT"):
            selects.append(statement)
    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        preview = await service.preview(project_id=project, limit=2)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    assert preview["next_after"] == str(rows[1].id)
    assert len(preview["items"]) == 2
    assert all("encrypted_secret" not in statement for statement in selects)
    assert CANARY not in json.dumps(preview)
    migration_id = uuid4()
    arguments = dict(project_id=project, migration_id=migration_id, actor="owner", limit=3)
    first = await service.create(**arguments)
    assert await service.create(**arguments) == first
    with pytest.raises(ConfigurationError):
        await service.create(**{**arguments, "limit": 2})
    rows[2].updated_at += timedelta(seconds=1)
    await store.session.flush()
    process = "job-api-" + str(uuid4())
    await register_configuration_process(store.session, identity=process, capabilities=[BRIDGE_CAPABILITY])
    batch = dict(project_id=project, migration_id=migration_id, actor="owner", expected_revision=1,
        required_processes=[process], old_processes_drained=False, limit=1)
    with pytest.raises(ConfigurationError) as blocked:
        await service.advance(**batch)
    assert blocked.value.code == "CONFIG_BRIDGE_REQUIRED"
    batch["old_processes_drained"] = True
    result = await service.advance(**batch)
    assert result["counts"] == {"completed": 1, "eligible": 2}
    assert await service.advance(**batch) == result  # Retry after lost response.
    paused = await service.advance(**{**batch, "expected_revision": 2, "pause": True})
    assert paused["state"] == "paused" and paused["counts"] == result["counts"]
    final = await service.advance(**{**batch, "expected_revision": 3, "limit": 3})
    assert final["state"] == "blocked" and final["counts"] == {"completed": 2, "blocked": 1}
    assert final["items"][2]["code"] == "CONFIG_REVISION_CONFLICT"
    assert CANARY not in json.dumps(final)
    assert (await service.status(project_id=project, migration_id=migration_id, offset=2, limit=1))["items"] == final["items"][2:]
    for row in rows[:2]:
        await store.session.refresh(row)
        assert row.encrypted_secret is None and row.authentication is not None
    assert rows[2].encrypted_secret is not None  # Failed source remains authoritative.


@pytest.fixture
async def configuration():
    engine = create_engine(Settings.model_validate({}))
    factory = create_session_factory(engine)
    async with factory() as session, session.begin() as transaction:
        workspace, project = uuid4(), uuid4()
        session.add(WorkspaceModel(id=workspace, name="Configuration", slug=str(workspace), status="active"))
        await session.flush()
        session.add(ProjectModel(id=project, workspace_id=workspace, name="Configuration", slug=str(project), status="active", data={}))
        await session.flush()
        store = ConfigurationResolution(session, encryption_key="disposable-configuration-test-key")
        yield store, project, engine
        await transaction.rollback()
    await engine.dispose()


async def prepared(store, project):
    key = await store.declare(project_id=project, key="PRIMARY_API_KEY")
    key_id, consumer = UUID(key["id"]), uuid4()
    dep = ConfigurationDependency(project, "provider_credential", consumer, "1", "/authentication/fields/api_key", "PRIMARY_API_KEY", "https://provider.example/v1")
    await store.grant_use(project_id=project, key_id=key_id, consumer_kind=dep.consumer_kind,
        consumer_scope=str(consumer), destination=dep.destination, environments=["draft"], field_paths=[dep.field_path], expected_revision=0, actor="owner")
    return key_id, dep


async def resolve(store, project, run, dep, **kwargs):
    return await store.resolve(project_id=project, run_id=run, consumer_kind=dep.consumer_kind,
        consumer_id=dep.consumer_id, field_path=dep.field_path, destination=kwargs.get("destination", dep.destination))


@pytest.mark.asyncio
async def test_reference_without_value_and_no_environment_fallback(configuration):
    store, project, _ = configuration
    key, dep = await prepared(store, project)
    result, _ = await store.inspect(project_id=project, environment="draft", dependencies=[dep])
    assert result["state"] == "blocked"
    assert result["missing_key_count"] == 1
    await store.write_value(project_id=project, key_id=key, environment="production", expected_revision=0, value=CANARY)
    result, _ = await store.inspect(project_id=project, environment="draft", dependencies=[dep])
    assert result["dependencies"][0]["code"] == "CONFIG_VALUE_MISSING"
    result, _ = await store.inspect(project_id=project, environment="production", dependencies=[dep])
    assert result["dependencies"][0]["code"] == "CONFIG_USAGE_NOT_AUTHORIZED"


@pytest.mark.asyncio
async def test_batched_metadata_preserves_independent_revisions_requiredness_and_admission(configuration, monkeypatch):
    from modules.core.infra.database import configuration_resolution as module

    store, project, engine = configuration
    _, dep = await prepared(store, project)
    optional = replace(dep, definition_revision='another-release', required=False)
    groups = [[dep], [optional]] * 50
    await store.session.flush()
    statements = []
    def record(_conn, _cursor, statement, *_): statements.append(statement)
    monkeypatch.setattr(module, 'decrypt_secret', lambda *_: pytest.fail('Metadata must not decrypt'))
    event.listen(engine.sync_engine, 'before_cursor_execute', record)
    try:
        results = await store.inspect_many(project_id=project, environment='draft', groups=groups)
        assert len(statements) == 4, statements
        assert all('stored_value' not in statement for statement in statements)
        assert len(results) == 100
        assert all(result[0]['state'] == ('blocked' if index % 2 == 0 else 'ready_with_notices')
                   for index, result in enumerate(results))
        # Independent target observation is not permission to mix revisions in
        # one actual Run. Admission keeps its existing strict closure contract.
        with pytest.raises(ConfigurationError) as conflict:
            await store.acquire(project_id=project, run_id=uuid4(), environment='draft', dependencies=[dep, optional])
        assert conflict.value.code == 'CONFIG_REVISION_CONFLICT'
        statements.clear()
        with pytest.raises(ConfigurationError) as forbidden:
            await store.inspect_many(project_id=project, environment='draft', groups=[[dep], [replace(dep, project_id=uuid4())]])
        assert forbidden.value.code == 'CONFIG_USAGE_NOT_AUTHORIZED'
        assert not statements
    finally:
        event.remove(engine.sync_engine, 'before_cursor_execute', record)


@pytest.mark.asyncio
async def test_lease_retry_requires_exact_closure_and_preserves_accepted_version(configuration):
    store, project, _ = configuration
    key, dep = await prepared(store, project)
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=0, value=CANARY)
    run = uuid4()
    first = await store.acquire(project_id=project, run_id=run, environment="draft", dependencies=[dep, dep])
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=1, value="rotated")
    assert await store.acquire(project_id=project, run_id=run, environment="draft", dependencies=[dep]) == first
    assert await resolve(store, project, run, dep) == CANARY
    for changed in ([], [replace(dep, definition_revision="2")], [replace(dep, destination="https://other.example")]):
        with pytest.raises(ConfigurationError) as error:
            await store.acquire(project_id=project, run_id=run, environment="draft", dependencies=changed)
        assert error.value.code == "CONFIG_REVISION_CONFLICT"


@pytest.mark.asyncio
async def test_optional_dependency_never_downgrades_a_required_path(configuration):
    store, project, _ = configuration
    _, dep = await prepared(store, project)
    optional = replace(dep, required=False)
    for dependencies in ([dep, optional], [optional, dep]):
        result, _ = await store.inspect(project_id=project, environment="draft", dependencies=dependencies)
        assert result["state"] == "blocked"
        assert result["required_key_count"] == 1
        assert result["dependencies"][0]["required"] is True


@pytest.mark.asyncio
async def test_provider_readiness_reader_uses_metadata_and_explicit_remote_binding(configuration):
    store, project, engine = configuration
    from modules.agent.infra.database.models import ProviderCredentialModel
    from modules.agent.entrypoint import read_configuration_target
    _, dep = await prepared(store, project)
    store.session.add(ProviderCredentialModel(id=dep.consumer_id, project_id=project, provider="custom", name="Remote",
        status="active", encrypted_secret=None, meta={"base_url": dep.destination},
        authentication={"type": "api_key", "fields": {"api_key": {"source": "project_environment", "key": dep.key}}}))
    await store.session.flush()
    statements = []
    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)
    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        closure = await read_configuration_target(store.session, project_id=project, target_kind="provider_credential",
            target_id=dep.consumer_id, environment="draft")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    assert not closure["unresolved"]
    result, _ = await store.inspect(project_id=project, environment="draft", dependencies=closure["dependencies"])
    assert result["state"] == "blocked"
    assert result["dependencies"][0]["key"] == dep.key
    assert all("encrypted_secret" not in statement for statement in statements)
    assert len(statements) == 1
    with pytest.raises(ConfigurationError):
        await read_configuration_target(store.session, project_id=uuid4(), target_kind="provider_credential",
            target_id=dep.consumer_id, environment="draft")


@pytest.mark.asyncio
async def test_rotation_pins_previous_value_revocation_blocks_and_no_durable_material(configuration):
    store, project, _ = configuration
    key, dep = await prepared(store, project)
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=0, value=CANARY)
    run = uuid4()
    await store.acquire(project_id=project, run_id=run, environment="draft", dependencies=[dep])
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=1, value="rotated-token")
    assert await resolve(store, project, run, dep) == CANARY
    with pytest.raises(ConfigurationError, match="destination"):
        await resolve(store, project, run, dep, destination="https://attacker.example/v1")
    leases = (await store.session.scalars(select(ConfigurationLeaseModel).where(ConfigurationLeaseModel.project_id == project))).all()
    audit = (await store.session.scalars(select(ConfigurationAuditModel).where(ConfigurationAuditModel.project_id == project))).all()
    assert CANARY not in str([row.pins for row in leases]) + str([row.evidence for row in audit])
    slot = await store.session.scalar(select(ProjectEnvironmentValueModel).where(ProjectEnvironmentValueModel.key_id == key))
    assert "rotated-token" not in slot.stored_value
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=2, clear=True)
    with pytest.raises(ConfigurationError) as error:
        await resolve(store, project, run, dep)
    assert error.value.code == "CONFIG_VALUE_REVOKED"


@pytest.mark.asyncio
async def test_metadata_queries_never_select_material_and_deduplicate(configuration):
    store, project, engine = configuration
    key, dep = await prepared(store, project)
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=0, value=CANARY)
    statements = []
    await store.session.flush()
    def record(_conn, _cursor, statement, *_):
        statements.append(statement)
    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        output = await store.list_keys(project_id=project)
        result, _ = await store.inspect(project_id=project, environment="draft", dependencies=[dep] * 100)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)
    assert result["required_key_count"] == 1
    assert result["state"] == "ready_with_notices"
    assert len(statements) <= 8  # Includes the batched latest external-validation evidence query.
    assert all("stored_value" not in statement for statement in statements)
    assert CANARY not in str(output) + str(result)


@pytest.mark.asyncio
async def test_value_cas_and_atomic_batch_idempotency(configuration):
    store, project, _ = configuration
    key, dep = await prepared(store, project)
    operations = [{"key_id": key, "environment": "draft", "expected_revision": 0, "value": CANARY}]
    first = await store.write_batch(project_id=project, actor="owner", request_id="write-1", operations=operations)
    assert await store.write_batch(project_id=project, actor="owner", request_id="write-1", operations=operations) == first
    with pytest.raises(ConfigurationError) as error:
        await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=0, value="stale")
    assert error.value.code == "CONFIG_REVISION_CONFLICT"
    with pytest.raises(ConfigurationError):
        async with store.session.begin_nested():
            await store.write_batch(project_id=project, actor="owner", request_id="write-2", operations=[
                {"key_id": key, "environment": "draft", "expected_revision": 1, "value": "would-rollback"},
                {"key_id": key, "environment": "production", "expected_revision": 1, "value": "invalid-revision"}])
    run = uuid4()
    await store.acquire(project_id=project, run_id=run, environment="draft", dependencies=[dep])
    assert await resolve(store, project, run, dep) == CANARY


@pytest.mark.asyncio
async def test_cross_project_reference_and_deletion_protection(configuration):
    store, project, _ = configuration
    key, dep = await prepared(store, project)
    with pytest.raises(ConfigurationError):
        await store.inspect(project_id=uuid4(), environment="draft", dependencies=[dep])
    await store.register_references([dep])
    with pytest.raises(ConfigurationError) as error:
        await store.remove_key(project_id=project, key_id=key, expected_revision=1, actor="owner")
    assert error.value.code == "CONFIG_REFERENCE_IN_USE"


@pytest.mark.asyncio
async def test_legacy_upsert_omitted_kind_preserves_secret_and_central_versions(configuration):
    from modules.core.infra.services.legacy_project_environment_service import LegacyProjectEnvironmentService
    store, project, _ = configuration
    class BorrowedSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *_): pass
        def __getattr__(self, name): return getattr(store.session, name)
        def begin(self): return store.session.begin_nested()
    legacy = LegacyProjectEnvironmentService(BorrowedSession, encryption_key=store.encryption_key)
    before = await legacy.upsert_key(project_id=project, key="OLD_KEY", kind="secret", values={"draft": CANARY})
    after = await legacy.upsert_key(project_id=project, key="OLD_KEY", values={"staging": "stage-only"})
    assert before["id"] == after["id"]
    assert after["kind"] == "secret"
    assert after["values"]["draft"] == {"configured": True, "value": None}
    assert after["values"]["staging"] == {"configured": True, "value": None}
    assert after["values"]["production"] == {"configured": False, "value": None}
    with pytest.raises(ConfigurationError):
        await legacy.upsert_key(project_id=project, key="OLD_KEY", kind="value", values={})
    cleared = await legacy.upsert_key(project_id=project, key="OLD_KEY", values={}, clear_environments=["draft"])
    assert not cleared["values"]["draft"]["configured"]
    assert await legacy.resolve_values(project_id=project, environment="draft", keys={"OLD_KEY"}) == {}


@pytest.mark.asyncio
async def test_legacy_adoption_is_idempotent_routes_are_explicit_and_partial_conversion_is_atomic(configuration):
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from modules.core.infra.database.configuration_models import LegacyConfigurationValueModel
    from shared.infra.crypto import encrypt_secret
    store, project, _ = configuration
    legacy = LegacyConfigurationStore(store.session, encryption_key=store.encryption_key)
    consumer = uuid4()
    original = ConfigurationDependency(project, "provider_credential", consumer, "original-revision", "/authentication/fields/api_key", "unused", "https://provider.example/v1")
    arguments = dict(project_id=project, source_kind=original.consumer_kind, source_id=consumer,
        field_path=original.field_path, source_revision="original-revision", encrypted_value=encrypt_secret(CANARY, store.encryption_key),
        dependencies=[original], actor="migration-owner")
    adopted = await legacy.adopt(**arguments)
    repeated = await legacy.adopt(**arguments)
    assert repeated["unchanged"] and repeated["alias_id"] == adopted["alias_id"]
    alias_id, key_id = UUID(adopted["alias_id"]), UUID(adopted["key_id"])
    dep = replace(original, key=adopted["key"], legacy_alias_id=alias_id)
    # No material was cloned into ordinary Environment slots.
    assert not (await store.session.scalars(select(ProjectEnvironmentValueModel).where(ProjectEnvironmentValueModel.key_id == key_id))).all()
    result, _ = await legacy.inspect(project_id=project, environment="production", dependencies=[dep])
    assert result["dependencies"][0]["source"] == "legacy_compat"
    run = uuid4()
    await legacy.acquire(project_id=project, run_id=run, environment="draft", dependencies=[dep])
    assert await resolve(legacy, project, run, dep) == CANARY
    converted = await legacy.convert(project_id=project, alias_id=alias_id, environments=["draft"],
        expected_revision=1, expected_values={"draft": 0}, actor="owner")
    assert converted["routes"] == {"draft": "environment", "staging": "legacy_compat", "production": "legacy_compat"}
    with pytest.raises(ConfigurationError) as error:
        await legacy.rotate_legacy(project_id=project, alias_id=alias_id, encrypted_value=arguments["encrypted_value"], source_revision="next", actor="old-client")
    assert error.value.code == "LEGACY_ENVIRONMENT_REQUIRED"
    await legacy.write_value(project_id=project, key_id=key_id, environment="draft", expected_revision=1, clear=True)
    result, _ = await legacy.inspect(project_id=project, environment="draft", dependencies=[dep])
    assert result["dependencies"][0]["material"] == "revoked"  # no fallback to legacy
    await legacy.convert(project_id=project, alias_id=alias_id, environments=["staging", "production"],
        expected_revision=2, expected_values={"staging": 0, "production": 0}, actor="owner")
    retired = await legacy.session.scalar(select(LegacyConfigurationValueModel).where(LegacyConfigurationValueModel.alias_id == alias_id))
    assert retired.stored_value is None
    # An already accepted pre-conversion Run retains only its original version.
    assert await resolve(legacy, project, run, dep) == CANARY


@pytest.mark.asyncio
@pytest.mark.parametrize("source,expected", [(None, "missing"), ("broken-ciphertext", "unavailable")])
async def test_legacy_missing_or_corrupt_material_is_never_ready(configuration, source, expected):
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    store, project, _ = configuration
    legacy = LegacyConfigurationStore(store.session, encryption_key=store.encryption_key)
    result = await legacy.adopt(project_id=project, source_kind="secret", source_id=uuid4(), field_path="/value",
        source_revision="1", encrypted_value=source, dependencies=[], actor="migration-owner")
    assert result["state"] == expected


@pytest.mark.asyncio
async def test_external_validation_is_version_specific_and_reads_do_not_validate(configuration):
    store, project, _ = configuration
    key, dep = await prepared(store, project)
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=0, value=CANARY)
    result, _ = await store.inspect(project_id=project, environment="draft", dependencies=[dep])
    assert result["dependencies"][0]["external_validation"] == "not_tested"
    run = uuid4()
    await store.acquire(project_id=project, run_id=run, environment="draft", dependencies=[dep])
    await store.record_validation(project_id=project, run_id=run, consumer_kind=dep.consumer_kind,
        consumer_id=dep.consumer_id, state="valid", actor="operator")
    result, _ = await store.inspect(project_id=project, environment="draft", dependencies=[dep])
    assert result["dependencies"][0]["external_validation"] == "valid"
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=1, value="rotated")
    result, _ = await store.inspect(project_id=project, environment="draft", dependencies=[dep])
    assert result["dependencies"][0]["external_validation"] == "stale"
    assert result["dependencies"][0]["material"] == "present"


@pytest.mark.asyncio
async def test_provider_binding_replacement_uses_revision_and_retains_old_usage(configuration, monkeypatch):
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.infra.database.configuration_binding_writer import configuration_binding
    from modules.agent.infra.database.models import ProviderCredentialModel
    store, project, _ = configuration
    monkeypatch.setattr(port, "_factory", lambda session: store)
    await store.declare(project_id=project, key="FIRST")
    await store.declare(project_id=project, key="SECOND")
    consumer = uuid4()
    auth = lambda key: {"type": "api_key", "fields": {"api_key": {"source": "project_environment", "key": key}}}
    store.session.add(ProviderCredentialModel(id=consumer, project_id=project, provider="openai", name="CAS",
        status="active", encrypted_secret=None, authentication=auth("FIRST")))
    await store.session.flush()
    before = await configuration_binding(store.session, project_id=project, target_kind="provider_credential", target_id=consumer)
    assert before["revision"] == "1"
    after = await configuration_binding(store.session, project_id=project, target_kind="provider_credential", target_id=consumer,
        authentication=auth("SECOND"), expected_revision="1")
    assert after["revision"] == "2"
    with pytest.raises(ConfigurationError) as failure:
        await configuration_binding(store.session, project_id=project, target_kind="provider_credential", target_id=consumer,
            authentication=auth("FIRST"), expected_revision="1")
    assert failure.value.code == "CONFIG_REVISION_CONFLICT"
    assert (await configuration_binding(store.session, project_id=project, target_kind="provider_credential", target_id=consumer))["authentication"] == auth("SECOND")
    key = await store.key(project, "SECOND")
    assert (await store.usage(project_id=project, key_id=key.id))["total"] == 1


@pytest.mark.asyncio
async def test_retention_preserves_live_pins_then_removes_expired_material(configuration):
    from datetime import timedelta
    from modules.core.infra.database.configuration_retention import purge_configuration_retention
    from modules.core.infra.database.configuration_store import now
    from modules.core.infra.database.configuration_models import ConfigurationValueVersionModel
    store, project, _ = configuration
    key, dep = await prepared(store, project)
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=0, value=CANARY)
    run = uuid4()
    await store.acquire(project_id=project, run_id=run, environment="draft", dependencies=[dep])
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=1, value="rotated")
    archive = await store.session.scalar(select(ConfigurationValueVersionModel).where(ConfigurationValueVersionModel.key_id == key))
    archive.expires_at = now() - timedelta(seconds=1)
    await store.session.flush()
    await purge_configuration_retention(store.session)
    assert await store.session.get(ConfigurationValueVersionModel, archive.id) is not None
    lease = await store.session.scalar(select(ConfigurationLeaseModel).where(ConfigurationLeaseModel.run_id == run))
    lease.expires_at = now() - timedelta(seconds=1)
    await store.session.flush()
    result = await purge_configuration_retention(store.session)
    assert result["expired_versions"] >= 1
    assert await store.session.get(ConfigurationValueVersionModel, archive.id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("key_count,reference_count", [(100, 500), (1000, 10000)])
async def test_configuration_readiness_large_closure_has_bounded_queries_and_policy_scans(configuration, monkeypatch, key_count, reference_count):
    from time import perf_counter
    from modules.core.infra.database import configuration_resolution as module
    from modules.core.infra.database.models import ProjectEnvironmentKeyModel
    from modules.core.infra.database.configuration_models import ConfigurationUsePolicyModel
    from hashlib import sha256
    store, project, engine = configuration
    keys = [ProjectEnvironmentKeyModel(id=uuid4(), project_id=project, key=f"KEY_{index}", kind="secret",
        value_format="token", validation_rules={}, origin="manual") for index in range(key_count)]
    store.session.add_all(keys)
    await store.session.flush()
    store.session.add_all([ProjectEnvironmentValueModel(key_id=key.id, environment="draft", stored_value="never-decrypted",
        value_version=uuid4(), material_state="present", revision=1, revoked=False) for key in keys])
    destination = "https://approved.example/v1"
    dependencies = [ConfigurationDependency(project, "provider_credential", uuid4(), "1", "/authentication/fields/api_key", keys[index % key_count].key, destination) for index in range(reference_count)]
    store.session.add_all([ConfigurationUsePolicyModel(project_id=project, key_id=keys[index % key_count].id,
        consumer_kind=dep.consumer_kind, consumer_scope=str(dep.consumer_id), destination=destination,
        destination_id=sha256(destination.encode()).hexdigest(), environments=["draft"], field_paths=[dep.field_path], actor="fixture", revision=1, revoked=False)
        for index, dep in enumerate(dependencies)])
    await store.session.flush()
    inspected = []
    original = module.matching_policy
    def matching(policies, *args):
        inspected.append(len(policies))
        return original(policies, *args)
    monkeypatch.setattr(module, "matching_policy", matching)
    monkeypatch.setattr(module, "decrypt_secret", lambda *_: pytest.fail("Readiness must not decrypt"))
    statements = []
    def capture(_conn, _cursor, statement, *_): statements.append(statement)
    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    durations = []
    try:
        for _ in range(6 if reference_count == 500 else 2):
            start = perf_counter()
            result, pins = await store.inspect(project_id=project, environment="draft", dependencies=dependencies)
            durations.append((perf_counter() - start) * 1000)
            assert result["required_key_count"] == key_count and len(pins) == reference_count
            assert result["state"] == "ready_with_notices"
        group_durations = []
        groups = [dependencies[index:index + 5] for index in range(0, reference_count, 5)]
        for _ in range(6 if reference_count == 500 else 2):
            start = perf_counter()
            grouped = await store.inspect_many(project_id=project, environment="draft", groups=groups)
            group_durations.append((perf_counter() - start) * 1000)
            assert len(grouped) == len(groups)
            assert sum(len(pins) for _, pins in grouped) == reference_count
            assert all(result['state'] == 'ready_with_notices' for result, _ in grouped)
        assert len(statements) <= 4 * (len(durations) + len(group_durations))
        assert max(inspected) == 1
        assert all("stored_value" not in statement for statement in statements)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    print({"keys": key_count, "references": reference_count, "milliseconds": durations,
           "independent_closures": len(groups), "batch_milliseconds": group_durations,
           "queries_per_read": len(statements) / (len(durations) + len(group_durations))})


@pytest.mark.asyncio
async def test_binding_cannot_discard_unmigrated_provider_material(configuration):
    from modules.agent.infra.database.configuration_binding_writer import configuration_binding
    from modules.agent.infra.database.models import ProviderCredentialModel
    store, project, _ = configuration
    identifier = uuid4()
    row = ProviderCredentialModel(id=identifier, project_id=project, provider='openai', name='Legacy', status='active', encrypted_secret='restricted-old-cipher', authentication=None)
    store.session.add(row)
    await store.session.flush()
    with pytest.raises(ConfigurationError) as error:
        await configuration_binding(store.session, project_id=project, target_kind='provider_credential', target_id=identifier,
            expected_revision='1', authentication={'type':'api_key', 'fields':{'api_key':{'source':'project_environment','key':'NEW_KEY'}}})
    assert error.value.code == 'LEGACY_ENVIRONMENT_REQUIRED'
    await store.session.refresh(row)
    assert row.encrypted_secret == 'restricted-old-cipher' and row.authentication is None



@pytest.mark.asyncio
async def test_unused_rotated_key_can_be_deleted_but_live_pins_cannot(configuration):
    from modules.core.infra.database.models import ProjectEnvironmentKeyModel
    from modules.core.infra.database.configuration_models import ConfigurationValueVersionModel
    store, project, _ = configuration
    declaration = await store.declare(project_id=project, key='UNUSED')
    identifier = UUID(declaration['id'])
    await store.write_value(project_id=project, key_id=identifier, environment='draft', value=CANARY, expected_revision=0)
    await store.write_value(project_id=project, key_id=identifier, environment='draft', clear=True, expected_revision=1)
    assert await store.session.scalar(select(ConfigurationValueVersionModel.id).where(ConfigurationValueVersionModel.key_id == identifier))
    await store.remove_key(project_id=project, key_id=identifier, expected_revision=1, actor='owner')
    await store.session.flush()
    assert await store.session.get(ProjectEnvironmentKeyModel, identifier) is None
    assert await store.session.scalar(select(ConfigurationValueVersionModel.id).where(ConfigurationValueVersionModel.key_id == identifier)) is None

    key, dep = await prepared(store, project)
    await store.write_value(project_id=project, key_id=key, environment='draft', value=CANARY, expected_revision=0)
    await store.acquire(project_id=project, run_id=uuid4(), environment='draft', dependencies=[dep])
    await store.write_value(project_id=project, key_id=key, environment='draft', clear=True, expected_revision=1)
    with pytest.raises(ConfigurationError) as failure:
        await store.remove_key(project_id=project, key_id=key, expected_revision=1, actor='owner')
    assert failure.value.code == 'CONFIG_REFERENCE_IN_USE'



@pytest.mark.asyncio
async def test_provider_cutover_preserves_identity_and_revision_and_requires_explicit_bridge_fleet(configuration, monkeypatch):
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.infra.database.configuration_provider_migration import migrate_provider_configuration
    from modules.agent.infra.database.models import ProviderCredentialModel
    from modules.agent.infra.database.mappers import provider_credential_model_to_entity
    from modules.agent.infra.adapters.configuration_bindings import provider_dependencies
    from modules.core.infra.database.configuration_fleet import register_configuration_process, BRIDGE_CAPABILITY
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from shared.infra.crypto import encrypt_secret
    from shared.contracts.project_configuration import compile_authentication
    original_store, project, _ = configuration
    store = LegacyConfigurationStore(original_store.session, encryption_key=original_store.encryption_key)
    monkeypatch.setattr(port, '_factory', lambda session: store)
    identifier = uuid4()
    row = ProviderCredentialModel(id=identifier, project_id=project, provider='openai', name='Preserved', status='active',
        encrypted_secret=encrypt_secret(CANARY, store.encryption_key))
    store.session.add(row)
    await store.session.flush()
    before = row.updated_at
    args = dict(project_id=project, credential_id=identifier, expected_revision=before.isoformat(),
        destinations=['https://api.openai.com/v1'], actor='operator')
    with pytest.raises(ConfigurationError) as failure:
        await migrate_provider_configuration(store.session, required_processes=[], **args)
    assert failure.value.code == 'CONFIG_BRIDGE_REQUIRED'
    assert row.encrypted_secret and row.authentication is None
    process = 'synthetic-api-' + str(uuid4())
    await register_configuration_process(store.session, identity=process, capabilities=['project_configuration.v1'])
    with pytest.raises(ConfigurationError):
        await migrate_provider_configuration(store.session, required_processes=[process], **args)
    await register_configuration_process(store.session, identity=process, capabilities=[BRIDGE_CAPABILITY])
    result = await migrate_provider_configuration(store.session, required_processes=[process], **args)
    await store.session.refresh(row)
    assert result['state'] == 'cutover' and not result['unchanged']
    assert row.id == identifier and row.updated_at == before and row.encrypted_secret is None
    assert row.name == 'Preserved'
    with pytest.raises(ConfigurationError):
        compile_authentication(row.authentication)  # An API caller cannot forge the internal route.
    assert (await migrate_provider_configuration(store.session, required_processes=[process], **args))['unchanged']
    dependencies = provider_dependencies(provider_credential_model_to_entity(row))
    run = uuid4()
    await store.acquire(project_id=project, run_id=run, environment='staging', dependencies=dependencies)
    assert await resolve(store, project, run, dependencies[0]) == CANARY
    from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
    repository = SQLAlchemyProviderCredentialRepository(store.session)
    rotated = await repository.get_by_id(identifier)
    rotated.encrypted_secret = encrypt_secret('central-rotated-canary', store.encryption_key)
    await repository.update(rotated)
    await store.session.refresh(row)
    assert row.encrypted_secret is None
    assert await resolve(store, project, run, dependencies[0]) == CANARY
    next_run = uuid4()
    await store.acquire(project_id=project, run_id=next_run, environment='staging', dependencies=dependencies)
    assert await resolve(store, project, next_run, dependencies[0]) == 'central-rotated-canary'
    await store.convert(project_id=project, alias_id=UUID(result['alias_id']), environments=['draft'],
        expected_revision=2, expected_values={'draft': 0}, actor='owner')
    rotated = await repository.get_by_id(identifier)
    rotated.encrypted_secret = encrypt_secret('must-not-overwrite', store.encryption_key)
    with pytest.raises(ConfigurationError) as split:
        await repository.update(rotated)
    assert split.value.code == 'LEGACY_ENVIRONMENT_REQUIRED'
    direct = replace(dependencies[0], legacy_alias_id=None)
    readiness, _ = await store.inspect(project_id=project, environment='staging', dependencies=[direct])
    assert readiness['state'] == 'blocked' and readiness['dependencies'][0]['material'] == 'missing'
    from modules.agent.infra.database.configuration_consumer_guard import verify_configuration_consumer
    await verify_configuration_consumer(store.session, project_id=project, consumer_kind='provider_credential', consumer_id=identifier)
    row.status = 'revoked'
    await store.session.flush()
    with pytest.raises(ConfigurationError) as revoked:
        await verify_configuration_consumer(store.session, project_id=project, consumer_kind='provider_credential', consumer_id=identifier)
    assert revoked.value.code == 'CONFIG_VALUE_REVOKED'



@pytest.mark.asyncio
async def test_cutover_barrier_rejects_expired_missing_and_omitted_incompatible_processes(configuration):
    from datetime import timedelta
    from modules.core.infra.database.configuration_fleet import register_configuration_process, assert_configuration_bridge, BRIDGE_CAPABILITY
    from modules.core.infra.database.configuration_models import ConfigurationProcessModel
    from modules.core.infra.database.configuration_store import now
    store, _, _ = configuration
    expected, old = 'bridge-' + str(uuid4()), 'old-' + str(uuid4())
    await register_configuration_process(store.session, identity=expected, capabilities=[BRIDGE_CAPABILITY])
    await assert_configuration_bridge(store.session, required_processes=[expected])
    for missing in [[expected, 'unknown-' + str(uuid4())], [expected, expected]]:
        with pytest.raises(ConfigurationError) as failure:
            await assert_configuration_bridge(store.session, required_processes=missing)
        assert failure.value.code == 'CONFIG_BRIDGE_REQUIRED'
    await register_configuration_process(store.session, identity=old, capabilities=['old'])
    with pytest.raises(ConfigurationError):
        await assert_configuration_bridge(store.session, required_processes=[expected])
    row = await store.session.scalar(select(ConfigurationProcessModel).where(ConfigurationProcessModel.process_identity == old))
    row.expires_at = now() - timedelta(seconds=1)
    await store.session.flush()
    await assert_configuration_bridge(store.session, required_processes=[expected])
    row = await store.session.scalar(select(ConfigurationProcessModel).where(ConfigurationProcessModel.process_identity == expected))
    row.expires_at = now() - timedelta(seconds=1)
    await store.session.flush()
    with pytest.raises(ConfigurationError):
        await assert_configuration_bridge(store.session, required_processes=[expected])


@pytest.mark.asyncio
async def test_shared_legacy_secret_authorizes_only_captured_tools_fields_and_destinations(configuration):
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from shared.infra.crypto import encrypt_secret
    store, project, _ = configuration
    legacy = LegacyConfigurationStore(store.session, encryption_key=store.encryption_key)
    secret, tool, other_tool = uuid4(), uuid4(), uuid4()
    dependencies = [ConfigurationDependency(project, "tool", tool, "frozen", "/config/authentication/fields/" + field,
        "unused", "https://legacy.example/api") for field in ["Authorization", "X-Client-Key"]]
    adopted = await legacy.adopt(project_id=project, source_kind="secret", source_id=secret,
        field_path="/value", source_revision="frozen-inventory", encrypted_value=encrypt_secret(CANARY, store.encryption_key),
        dependencies=dependencies, actor="migration-owner")
    reference = await legacy.legacy_reference(project_id=project, source_kind="secret", source_id=secret, field_path="/value")
    assert reference == {"source": "legacy_configuration", "key": adopted["key"], "alias_id": adopted["alias_id"]}
    assert CANARY not in repr(reference)
    assert await legacy.legacy_reference(project_id=uuid4(), source_kind="secret", source_id=secret, field_path="/value") is None
    bindings = [replace(dep, key=adopted["key"], legacy_alias_id=UUID(adopted["alias_id"])) for dep in dependencies]
    run = uuid4()
    await legacy.acquire(project_id=project, run_id=run, environment="production", dependencies=bindings)
    for binding in bindings:
        assert await resolve(legacy, project, run, binding) == CANARY
    for forged in [replace(bindings[0], consumer_id=other_tool), replace(bindings[0], field_path="/config/authentication/fields/X-New-Key")]:
        with pytest.raises(ConfigurationError) as error:
            await legacy.inspect(project_id=project, environment="production", dependencies=[forged])
        assert error.value.code == "CONFIG_USAGE_NOT_AUTHORIZED"
    report, _ = await legacy.inspect(project_id=project, environment="production",
        dependencies=[replace(bindings[0], destination="https://other.example")])
    assert report["state"] == "blocked"
    assert report["dependencies"][0]["code"] == "CONFIG_USAGE_NOT_AUTHORIZED"
    # Knowing the central key name does not recover legacy material without its
    # captured alias binding, even for an otherwise allowed consumer.
    report, _ = await legacy.inspect(project_id=project, environment="production",
        dependencies=[replace(bindings[0], legacy_alias_id=None)])
    assert report["state"] == "blocked"


@pytest.mark.asyncio
async def test_unknown_legacy_alias_never_falls_back_to_environment_material(configuration):
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    store, project, _ = configuration
    key, dep = await prepared(store, project)
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=0, value=CANARY)
    legacy = LegacyConfigurationStore(store.session, encryption_key=store.encryption_key)
    with pytest.raises(ConfigurationError) as error:
        await legacy.acquire(project_id=project, run_id=uuid4(), environment="draft", dependencies=[replace(dep, legacy_alias_id=uuid4())])
    assert error.value.code == "CONFIG_REFERENCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_cutover_guard_includes_agent_network_and_package_work_without_material(configuration):
    from datetime import UTC, datetime, timedelta
    from modules.agent.infra.database.models import AgentModel, SessionModel, AskJobModel
    from modules.agent.infra.database.run_models import AgentRunModel
    from modules.network.infra.database.models import NetworkModel, NetworkSessionModel, NetworkExecutionModel
    from modules.package.infra.models import PackagePlanModel, PackageOperationModel
    from woobe_api.configuration_composition import assert_configuration_quiescent
    store, project, _ = configuration
    session = store.session
    await assert_configuration_quiescent(session, project_id=project)
    agent = AgentModel(project_id=project, name='Guard fixture', type='chat', provider='openai', model='fixture')
    network = NetworkModel(project_id=project, name='Guard network')
    session.add_all([agent, network])
    await session.flush()
    agent_session = SessionModel(project_id=project, agent_id=agent.id)
    network_session = NetworkSessionModel(project_id=project, network_id=network.id, environment='draft')
    session.add_all([agent_session, network_session])
    await session.flush()
    run = AgentRunModel(project_id=project, agent_id=agent.id, session_id=agent_session.id,
        trace_id=uuid4(), environment='draft', input_message='fixture', status='running')
    session.add(run)
    for status in ('running', 'uncertain'):
        run.status = status
        await session.flush()
        with pytest.raises(ConfigurationError, match='Finish active Runs'):
            await assert_configuration_quiescent(session, project_id=project)
    run.status = 'completed'
    await session.flush()
    await assert_configuration_quiescent(session, project_id=project)
    network_run = NetworkExecutionModel(project_id=project, network_id=network.id,
        network_session_id=network_session.id, input_message='fixture', draft_revision=1, definition_snapshot={}, resolved_bindings_snapshot={})
    session.add(network_run)
    for status in ('queued', 'running', 'cancel_requested', 'uncertain'):
        network_run.status = status
        await session.flush()
        with pytest.raises(ConfigurationError, match='Finish active Runs'):
            await assert_configuration_quiescent(session, project_id=project)
    network_run.status = 'completed'
    await session.flush()
    await assert_configuration_quiescent(session, project_id=project)
    plan = PackagePlanModel(project_id=project, actor='owner', upload_id=uuid4(),
        artifact_digest='a'*64, plan_digest='b'*64, document={}, expires_at=datetime.now(UTC)+timedelta(hours=1))
    session.add(plan)
    await session.flush()
    with pytest.raises(ConfigurationError, match='pending package plans'):
        await assert_configuration_quiescent(session, project_id=project)
    operation = PackageOperationModel(project_id=project, actor='owner', key_digest=b'fixture',
        payload_fingerprint=b'fixture', payload_ciphertext='protected', principal_ciphertext='protected',
        artifact_digest='a'*64, upload_id=plan.upload_id, plan_id=plan.id, lifecycle='draft', phases_total=1)
    session.add(operation)
    for state in ('accepted', 'resolving', 'materializing', 'waiting_dependency', 'verifying', 'cancelling'):
        operation.state = state
        await session.flush()
        with pytest.raises(ConfigurationError, match='Finish active Runs'):
            await assert_configuration_quiescent(session, project_id=project)
    operation.state = 'succeeded'
    await session.flush()
    # An already-consumed plan does not force waiting for expiry.
    await assert_configuration_quiescent(session, project_id=project)
    job = AskJobModel(project_id=project, agent_id=agent.id, params={}, status='pending')
    session.add(job)
    for status in ('pending', 'running'):
        job.status = status
        await session.flush()
        with pytest.raises(ConfigurationError, match='Finish active Runs'):
            await assert_configuration_quiescent(session, project_id=project)
    job.status = 'completed'
    await session.flush()
    await assert_configuration_quiescent(session, project_id=project)
    # Other Projects never inherit these temporary barriers.
    operation.state = 'accepted'
    await session.flush()
    await assert_configuration_quiescent(session, project_id=uuid4())


@pytest.mark.asyncio
async def test_legacy_only_acceptance_waits_for_cutover_before_reading_sources(configuration, monkeypatch):
    import asyncio
    from sqlalchemy import delete
    from modules.core.composition import public_api
    from modules.agent.infra.database.models import ProviderCredentialModel
    _, _, engine = configuration
    factory = create_session_factory(engine)
    project, workspace, credential = uuid4(), uuid4(), uuid4()
    async with factory() as session, session.begin():
        session.add(WorkspaceModel(id=workspace, name='Barrier', slug=str(workspace), status='active'))
        await session.flush()
        session.add(ProjectModel(id=project, workspace_id=workspace, name='Barrier', slug=str(project), status='active', data={}))
        session.add(ProviderCredentialModel(id=credential, project_id=project, provider='openai', name='Before', encrypted_secret='protected'))
    monkeypatch.setattr(public_api, 'build_project_configuration_runtime', lambda session: ConfigurationResolution(session, encryption_key='fixture'))
    started, read = asyncio.Event(), asyncio.Event()
    observed = []
    async def dependency_reader(session, **kwargs):
        observed.append(await session.scalar(select(ProviderCredentialModel.name).where(ProviderCredentialModel.id == credential)))
        read.set()
        return []  # Legacy-only Acceptance must participate in the barrier too.
    accept = public_api.build_configuration_acceptor(dependency_reader)
    async def acceptance():
        async with factory() as session, session.begin():
            started.set()
            return await accept(session, project_id=project, run_id=uuid4(), environment='draft', bindings={})
    task = None
    try:
        async with factory() as session, session.begin():
            await ConfigurationResolution(session, encryption_key='fixture').lock_project(project)
            source = await session.get(ProviderCredentialModel, credential)
            source.name = 'After'
            await session.flush()
            task = asyncio.create_task(acceptance())
            await asyncio.wait_for(started.wait(), 2)
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(read.wait(), 0.1)
        assert await asyncio.wait_for(task, 3) == []
        assert observed == ['After']
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        async with factory() as session, session.begin():
            await session.execute(delete(ProviderCredentialModel).where(ProviderCredentialModel.id == credential))
            await session.execute(delete(ProjectModel).where(ProjectModel.id == project))
            await session.execute(delete(WorkspaceModel).where(WorkspaceModel.id == workspace))


@pytest.mark.asyncio
async def test_secret_header_cutover_preserves_author_bytes_and_pins_central_rotation(configuration, monkeypatch):
    import json
    from copy import deepcopy
    from types import SimpleNamespace
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.domain.tool_configuration import tool_dependencies, validate_tool_authentication
    from modules.agent.infra.database.configuration_secret_migration import inventory_secret_configuration, migrate_secret_configuration
    from modules.agent.infra.database.configuration_secret_projection import project_secret_headers
    from modules.agent.infra.database.configuration_dependency_reader import collect_configuration_dependencies
    from modules.agent.infra.database.models import AgentToolModel, AgentToolSecretModel
    from modules.agent.infra.database.repositories import SQLAlchemyAgentToolSecretRepository
    from modules.agent.infra.execution.runtime_preparation import prepare_tool_state
    from modules.core.infra.database.configuration_fleet import register_configuration_process, BRIDGE_CAPABILITY
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from shared.infra.crypto import encrypt_secret
    original, project, engine = configuration
    store = LegacyConfigurationStore(original.session, encryption_key=original.encryption_key)
    session = store.session
    monkeypatch.setattr(port, '_factory', lambda session: store)
    source = AgentToolSecretModel(project_id=project, name='shared', type='api_key', encrypted_value=encrypt_secret(CANARY, store.encryption_key))
    author = {'url':'https://approved.example/api', 'method':'GET', 'headers':[{'key':'Authorization', 'value':'{{secret:shared}}'}]}
    target = AgentToolModel(project_id=project, name='Captured', type='http', config=deepcopy(author))
    session.add_all([source, target])
    await session.flush()
    before = source.updated_at
    statements = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith('SELECT'):
            statements.append(statement)
    event.listen(engine.sync_engine, 'before_cursor_execute', capture)
    try:
        preview = await inventory_secret_configuration(session, project_id=project)
    finally:
        event.remove(engine.sync_engine, 'before_cursor_execute', capture)
    assert all('encrypted_value' not in statement for statement in statements)
    assert CANARY not in json.dumps(preview)
    item = preview['items'][0]
    assert item['state'] == 'eligible' and item['consumers'] == 1
    process = 'secret-bridge-' + str(uuid4())
    await register_configuration_process(session, identity=process, capabilities=[BRIDGE_CAPABILITY])
    kwargs = dict(project_id=project, secret_id=source.id, expected_revision=item['revision'],
        expected_closure=item['closure'], required_processes=[process], actor='owner')
    result = await migrate_secret_configuration(session, **kwargs)
    assert result['state'] == 'cutover'
    await session.refresh(source)
    await session.refresh(target)
    assert source.encrypted_value is None and source.updated_at == before and source.name == 'shared'
    assert target.config == author
    assert (await migrate_secret_configuration(session, **kwargs))['unchanged']
    tools = await project_secret_headers(session, project_id=project, tools=[target])
    assert tools[0].config['headers'] == [] and target.config == author
    portable = (await project_secret_headers(session, project_id=project, tools=[target], portable=True))[0]
    assert portable.config['authentication']['fields']['Authorization'] == {
        'source':'project_environment', 'key':source.configuration_reference['key']}
    assert 'alias_id' not in json.dumps(portable.config) and CANARY not in json.dumps(portable.config)
    with pytest.raises(ConfigurationError):
        validate_tool_authentication(tools[0].config)  # An API caller cannot forge this projection.
    dependencies = tool_dependencies(tools[0])
    bindings = {'node': {'snapshot_override': {'runtime_config': {'tools': {'tool_ids': [str(target.id)]}}}}}
    metadata = await collect_configuration_dependencies(session, project_id=project, bindings=bindings,
        snapshot_builder=lambda row: None)
    assert [replace(dep, impact=()) for dep in metadata] == dependencies
    repositories = SimpleNamespace(tools=SimpleNamespace(list_by_agent=None),
        tool_secrets=SQLAlchemyAgentToolSecretRepository(session))
    repositories.tools.get_by_id = __import__('unittest.mock', fromlist=['AsyncMock']).AsyncMock(return_value=target)
    runtime_tools, material = await prepare_tool_state(repositories,
        agent=SimpleNamespace(id=uuid4(), project_id=project, settings={'runtime_config': {'tools': {'tool_ids': [str(target.id)]}}}),
        tool_from_snapshot=lambda raw: None, tool_with_permissions=lambda tool, _: tool)
    assert material == {} and runtime_tools[0].config == tools[0].config
    run = uuid4()
    await store.acquire(project_id=project, run_id=run, environment='production', dependencies=dependencies)
    assert await resolve(store, project, run, dependencies[0]) == CANARY
    repository = repositories.tool_secrets
    changed = await repository.get_by_id(source.id)
    changed.encrypted_value = encrypt_secret('rotated-secret-canary', store.encryption_key)
    await repository.update(changed)
    await session.flush()
    await session.refresh(source)
    assert source.encrypted_value is None
    assert await resolve(store, project, run, dependencies[0]) == CANARY
    next_run = uuid4()
    await store.acquire(project_id=project, run_id=next_run, environment='production', dependencies=dependencies)
    assert await resolve(store, project, next_run, dependencies[0]) == 'rotated-secret-canary'
    new_consumer = replace(dependencies[0], consumer_id=uuid4())
    with pytest.raises(ConfigurationError) as denied:
        await store.acquire(project_id=project, run_id=uuid4(), environment='production', dependencies=[new_consumer])
    assert denied.value.code == 'CONFIG_USAGE_NOT_AUTHORIZED'
    await store.convert(project_id=project, alias_id=UUID(source.configuration_reference['alias_id']),
        environments=['draft'], expected_revision=2, expected_values={'draft':0}, actor='owner')
    changed = await repository.get_by_id(source.id)
    changed.encrypted_value = encrypt_secret('ambiguous-write', store.encryption_key)
    with pytest.raises(ConfigurationError) as ambiguous:
        await repository.update(changed)
    assert ambiguous.value.code == 'LEGACY_ENVIRONMENT_REQUIRED'


@pytest.mark.asyncio
async def test_secret_migration_job_rejects_changed_consumer_closure_and_reports_unsupported_sources(configuration, monkeypatch):
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.infra.database.configuration_secret_migration import inventory_configuration_sources, migrate_configuration_source
    from modules.agent.infra.database.models import AgentToolModel, AgentToolSecretModel
    from modules.core.infra.database.configuration_fleet import register_configuration_process, BRIDGE_CAPABILITY
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from modules.core.infra.services.configuration_migration import ConfigurationMigrationService
    from shared.infra.crypto import encrypt_secret
    original, project, _ = configuration
    store = LegacyConfigurationStore(original.session, encryption_key=original.encryption_key)
    monkeypatch.setattr(port, '_factory', lambda session: store)
    secret = AgentToolSecretModel(project_id=project, name='before', type='api_key', encrypted_value=encrypt_secret(CANARY, store.encryption_key))
    unsupported = AgentToolSecretModel(project_id=project, name='old-oauth', type='oauth2', encrypted_value='protected')
    target = AgentToolModel(project_id=project, name='Captured', type='http', config={
        'url':'https://before.example', 'headers':[{'key':'Authorization', 'value':'{{secret:before}}'}]})
    store.session.add_all([secret, unsupported, target])
    await store.session.flush()
    service = ConfigurationMigrationService(store.session, encryption_key=store.encryption_key,
        inventory=inventory_configuration_sources, cutover=migrate_configuration_source)
    preview = await service.preview(project_id=project, source_kind='secret')
    assert preview['scope'] == 'secrets'
    assert {item['state'] for item in preview['items']} == {'eligible','blocked'}
    job = await service.create(project_id=project, migration_id=uuid4(), actor='owner', source_kind='secret')
    target.config = {**target.config, 'url':'https://changed.example'}
    await store.session.flush()
    process = 'closure-bridge-' + str(uuid4())
    await register_configuration_process(store.session, identity=process, capabilities=[BRIDGE_CAPABILITY])
    args = dict(project_id=project, migration_id=UUID(job['id']), actor='owner', expected_revision=1,
        required_processes=[process], old_processes_drained=True)
    rejected = await service.advance(**args)
    assert rejected['state'] == 'blocked'
    assert next(item for item in rejected['items'] if item['id'] == str(secret.id))['code'] == 'CONFIG_REVISION_CONFLICT'
    assert await service.advance(**args) == rejected
    await store.session.refresh(secret)
    assert secret.encrypted_value and secret.configuration_reference is None


@pytest.mark.asyncio
async def test_legacy_provider_create_is_central_from_first_commit(configuration, monkeypatch):
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.domain.entities import ProviderCredential
    from modules.agent.domain.enums import Provider
    from modules.agent.infra.database.configuration_provider_migration import inventory_provider_configuration
    from modules.agent.infra.database.repositories import SQLAlchemyProviderCredentialRepository
    from modules.agent.infra.database.models import ProviderCredentialModel
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from modules.core.infra.database.configuration_models import LegacyConfigurationValueModel
    from shared.infra.crypto import encrypt_secret
    original, project, _ = configuration
    store = LegacyConfigurationStore(original.session, encryption_key=original.encryption_key)
    monkeypatch.setattr(port, '_factory', lambda session: store)
    repository = SQLAlchemyProviderCredentialRepository(store.session)
    cipher = encrypt_secret(CANARY, store.encryption_key)
    created = await repository.save(ProviderCredential(project_id=project, provider=Provider.openai,
        name='Compatible writer', encrypted_secret=cipher))
    row = await store.session.get(ProviderCredentialModel, created.id)
    assert row.encrypted_secret is None and created.encrypted_secret == ''
    reference = created.authentication['fields']['api_key']
    assert reference['source'] == 'legacy_configuration'
    material = await store.session.scalar(select(LegacyConfigurationValueModel).where(LegacyConfigurationValueModel.alias_id == UUID(reference['alias_id'])))
    assert material.stored_value == cipher
    assert not (await inventory_provider_configuration(store.session, project_id=project))['items']
    from modules.agent.infra.adapters.configuration_bindings import provider_dependencies
    run = uuid4()
    await store.acquire(project_id=project, run_id=run, environment='staging', dependencies=provider_dependencies(created))
    resolved = await store.resolve(project_id=project, run_id=run, consumer_kind='provider_credential',
        consumer_id=created.id, field_path='/authentication/fields/api_key', destination='https://api.openai.com/v1')
    assert resolved == CANARY
    from modules.agent.infra.database.configuration_package import inspect_configuration_provider_reuse
    portable = {'provider':'openai','authentication': {'type':'api_key','fields': {'api_key': {
        'source':'project_environment','key':'portable-key'}}}}
    evidence = await inspect_configuration_provider_reuse(store.session, project_id=project,
        connections={'primary':portable}, bindings={'primary':{'credential_id':str(created.id)}},
        configuration={'portable-key':{'key':reference['key']}})
    assert evidence['primary']['binding_source'] == 'legacy_configuration'
    assert row.authentication['fields']['api_key'] == reference
    with pytest.raises(ConfigurationError) as incompatible:
        await inspect_configuration_provider_reuse(store.session, project_id=project,
            connections={'primary':portable}, bindings={'primary':{'credential_id':str(created.id)}},
            configuration={'portable-key':{'key':'ANOTHER_KEY'}})
    assert incompatible.value.code == 'CONFIG_BINDING_INVALID'

    revision = created.binding_revision
    created.encrypted_secret = encrypt_secret(CANARY + '-rotated', store.encryption_key)
    rotated = await repository.update(created)
    assert rotated.binding_revision == revision and rotated.encrypted_secret == ''
    await store.session.refresh(material)
    assert material.revision == 2
    incomplete = await repository.save(ProviderCredential(project_id=project, provider=Provider.custom,
        name='Destination not selected', encrypted_secret=cipher))
    assert incomplete.encrypted_secret == '' and incomplete.authentication
    with pytest.raises(ConfigurationError) as failure:
        provider_dependencies(incomplete)
    assert failure.value.code == 'CONFIG_BINDING_INVALID'
    # A Model-supplied destination cannot implicitly authorize this material.
    dependencies = provider_dependencies(incomplete, base_url='https://unapproved.example/v1')
    status, _ = await store.inspect(project_id=project, environment='draft', dependencies=dependencies)
    assert status['state'] == 'blocked'
    assert status['dependencies'][0]['code'] == 'CONFIG_USAGE_NOT_AUTHORIZED'

    monkeypatch.setattr(port, '_factory', None)
    with pytest.raises(ConfigurationError) as failure:
        await repository.save(ProviderCredential(project_id=project, provider=Provider.openai,
            name='Unavailable store', encrypted_secret=cipher))
    assert failure.value.code == 'CONFIG_STORE_UNAVAILABLE'


@pytest.mark.asyncio
async def test_old_provider_database_rows_remain_in_inventory(configuration):
    from modules.agent.infra.database.configuration_provider_migration import inventory_provider_configuration
    from modules.agent.infra.database.models import ProviderCredentialModel
    store, project, _ = configuration
    row = ProviderCredentialModel(project_id=project, provider='openai', name='Pre-upgrade row', encrypted_secret='protected')
    store.session.add(row)
    await store.session.flush()
    assert any(item['id'] == str(row.id) for item in (await inventory_provider_configuration(store.session, project_id=project))['items'])


@pytest.mark.asyncio
async def test_migrated_secret_resolves_at_http_send_without_transaction_and_rechecks_revocation(configuration, monkeypatch):
    import httpx
    from sqlalchemy import delete, update
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
    from modules.agent.domain.tool_configuration import tool_dependencies
    from modules.agent.infra.adapters.tool_configuration_transport import configuration_bound_tool
    from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
    from modules.agent.infra.database.configuration_consumer_guard import verify_configuration_consumer
    from modules.agent.infra.database.configuration_secret_migration import inventory_secret_configuration, migrate_secret_configuration
    from modules.agent.infra.database.configuration_secret_projection import project_secret_headers
    from modules.agent.infra.database.models import AgentToolModel, AgentToolSecretModel
    from modules.core.infra.database.configuration_fleet import register_configuration_process, BRIDGE_CAPABILITY
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from modules.core.infra.database.configuration_models import ConfigurationProcessModel
    from modules.core.infra.services.configuration_runtime_resolver import ConfigurationRuntimeResolver
    from shared.infra.database.base import BaseModel
    from shared.infra.crypto import encrypt_secret
    _, _, engine = configuration
    factory = create_session_factory(engine)
    active_connections = set()
    def checkout(dbapi_connection, record, proxy):
        active_connections.add(id(record))
    def checkin(dbapi_connection, record):
        active_connections.discard(id(record))
    event.listen(engine.sync_engine, 'checkout', checkout)
    event.listen(engine.sync_engine, 'checkin', checkin)
    project, workspace, run = uuid4(), uuid4(), uuid4()
    process = 'transport-bridge-' + str(uuid4())
    encryption_key = 'transport-fixture-only'
    monkeypatch.setattr(port, '_factory', lambda session: LegacyConfigurationStore(session, encryption_key=encryption_key))
    monkeypatch.setattr(port, '_runtime_resolver', ConfigurationRuntimeResolver(factory, encryption_key=encryption_key,
        consumer_verifier=verify_configuration_consumer))
    monkeypatch.setattr('modules.agent.infra.adapters.tool_executor._validated_local_addresses', lambda url: frozenset({'8.8.8.8'}))
    execution = new_execution_context()
    execution.project_id, execution.run_id = project, run
    token = current_execution.set(execution)
    sent = []
    try:
        async with factory() as session, session.begin():
            session.add(WorkspaceModel(id=workspace, name='Secret HTTP fixture', slug=str(workspace), status='active'))
            await session.flush()
            session.add(ProjectModel(id=project, workspace_id=workspace, name='Secret HTTP fixture', slug=str(project), status='active', data={}))
            await session.flush()
            secret = AgentToolSecretModel(project_id=project, name='header', type='api_key', encrypted_value=encrypt_secret(CANARY, encryption_key))
            original = AgentToolModel(project_id=project, name='Transport fixture', type='http', config={
                'url':'https://approved.example/api', 'headers':[{'key':'Authorization', 'value':'{{secret:header}}'}]})
            session.add_all([secret, original])
            await session.flush()
            item = (await inventory_secret_configuration(session, project_id=project))['items'][0]
            await register_configuration_process(session, identity=process, capabilities=[BRIDGE_CAPABILITY])
            await migrate_secret_configuration(session, project_id=project, secret_id=secret.id,
                expected_revision=item['revision'], expected_closure=item['closure'], required_processes=[process], actor='test')
            target = (await project_secret_headers(session, project_id=project, tools=[original]))[0]
            await port._factory(session).acquire(project_id=project, run_id=run, environment='draft', dependencies=tool_dependencies(target))
        def send(request):
            assert not active_connections
            assert request.headers['authorization'] == CANARY
            sent.append(request)
            return httpx.Response(200, json={'echo':CANARY}, request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(send)) as client:
            executor = HttpToolExecutor(client=client)
            class Runtime:
                @configuration_bound_tool
                async def execute(self, tool):
                    return await executor.execute('GET', tool.config['url'])
            result = await Runtime().execute(target)
            assert result.success and CANARY not in str(result.output)
            assert 'authorization' not in sent[0].headers
            async with factory() as session, session.begin():
                await session.execute(update(AgentToolModel).where(AgentToolModel.id == target.id).values(status='inactive'))
            with pytest.raises(ConfigurationError) as error:
                await Runtime().execute(target)
            assert error.value.code == 'CONFIG_VALUE_REVOKED' and len(sent) == 1
    finally:
        current_execution.reset(token)
        async with factory() as session, session.begin():
            # Only this test's committed synthetic Project; dependency order is
            # required because retained keys deliberately use restrictive FKs.
            from sqlalchemy.sql.ddl import sort_tables
            tables = [table for table in BaseModel.metadata.tables.values()
                if 'project_id' in table.c and table.schema == 'core'
                and (table.name.startswith('project_configuration_') or table.name in {'project_environment_keys', 'project_environment_values'})]
            for table in reversed(sort_tables(tables)):
                await session.execute(delete(table).where(table.c.project_id == project))
            await session.execute(delete(AgentToolModel).where(AgentToolModel.project_id == project))
            await session.execute(delete(AgentToolSecretModel).where(AgentToolSecretModel.project_id == project))
            await session.execute(delete(ConfigurationProcessModel).where(ConfigurationProcessModel.process_identity == process))
            await session.execute(delete(ProjectModel).where(ProjectModel.id == project))
            await session.execute(delete(WorkspaceModel).where(WorkspaceModel.id == workspace))

        event.remove(engine.sync_engine, "checkout", checkout)
        event.remove(engine.sync_engine, "checkin", checkin)


@pytest.mark.asyncio
async def test_corrupt_secret_replay_preserves_incomplete_material_status(configuration, monkeypatch):
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.infra.database.configuration_secret_migration import inventory_secret_configuration, migrate_secret_configuration
    from modules.agent.infra.database.models import AgentToolSecretModel
    from modules.core.infra.database.configuration_fleet import register_configuration_process, BRIDGE_CAPABILITY
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    original, project, _ = configuration
    store = LegacyConfigurationStore(original.session, encryption_key=original.encryption_key)
    monkeypatch.setattr(port, '_factory', lambda session: store)
    source = AgentToolSecretModel(project_id=project, name='orphan-corrupt', type='custom', encrypted_value='unreadable-fixture')
    store.session.add(source)
    await store.session.flush()
    item = (await inventory_secret_configuration(store.session, project_id=project))['items'][0]
    process = 'corrupt-replay-' + str(uuid4())
    await register_configuration_process(store.session, identity=process, capabilities=[BRIDGE_CAPABILITY])
    args = dict(project_id=project, secret_id=source.id, expected_revision=item['revision'], expected_closure=item['closure'],
        required_processes=[process], actor='owner')
    first = await migrate_secret_configuration(store.session, **args)
    second = await migrate_secret_configuration(store.session, **args)
    assert first['material'] == second['material'] == 'unavailable'
    assert first['state'] == second['state'] == 'cutover'
    assert not first['unchanged'] and second['unchanged']


@pytest.mark.asyncio
async def test_activation_evidence_is_metadata_only_and_fences_material_versions(configuration):
    store, project, engine = configuration
    key, dep = await prepared(store, project)
    with pytest.raises(ConfigurationError) as error:
        await store.activation_evidence(project_id=project, environment="draft", dependencies=[dep])
    assert error.value.code == "CONFIG_VALUE_MISSING"
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=0, value=CANARY)
    statements = []
    def record(_conn, _cursor, statement, *_):
        statements.append(statement)
    event.listen(engine.sync_engine, "before_cursor_execute", record)
    try:
        first = await store.activation_evidence(project_id=project, environment="draft", dependencies=[dep])
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", record)
    assert all("stored_value" not in statement for statement in statements)
    assert CANARY not in str(first)
    assert len(first["pins"]) == 1
    assert first["definitions"][0]["revision"] == 1
    assert first == await store.activation_evidence(project_id=project, environment="draft", dependencies=[dep, dep])
    await store.write_value(project_id=project, key_id=key, environment="draft", expected_revision=1, value="rotated-only")
    current = await store.activation_evidence(project_id=project, environment="draft", dependencies=[dep])
    assert current["pins"] != first["pins"]
    assert current["dependency_digest"] == first["dependency_digest"]
    # Draft values never satisfy Staging/Production, even with an existing policy.
    with pytest.raises(ConfigurationError):
        await store.activation_evidence(project_id=project, environment="production", dependencies=[dep])


@pytest.mark.asyncio
async def test_new_secret_is_central_and_new_tool_use_requires_explicit_authority(configuration, monkeypatch):
    from unittest.mock import AsyncMock
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.domain.entities import Secret, Tool
    from modules.agent.infra.database.models import AgentToolSecretModel
    from modules.agent.infra.database.repositories import SQLAlchemyAgentToolSecretRepository
    from modules.agent.infra.database.configuration_secret_projection import project_secret_headers
    from modules.agent.domain.tool_configuration import tool_dependencies
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from modules.core.infra.database.configuration_models import LegacyConfigurationValueModel, ConfigurationUsePolicyModel
    from shared.contracts.errors import AuthorizationError
    from shared.infra.crypto import encrypt_secret
    original,project,_=configuration
    store=LegacyConfigurationStore(original.session,encryption_key=original.encryption_key)
    monkeypatch.setattr(port,'_factory',lambda session:store)
    cipher=encrypt_secret(CANARY,store.encryption_key)
    secret=await SQLAlchemyAgentToolSecretRepository(store.session).create(Secret(project_id=project,name='new-secret',encrypted_value=cipher))
    row=await store.session.get(AgentToolSecretModel,secret.id)
    assert row.encrypted_value is None and secret.encrypted_value==''
    alias=UUID(secret.configuration_reference['alias_id'])
    assert (await store.session.scalar(select(LegacyConfigurationValueModel).where(LegacyConfigurationValueModel.alias_id==alias))).stored_value==cipher
    tool=Tool(project_id=project,name='Secret header',config={'url':'https://approved.example/api','headers':[{'key':'Authorization','value':'{{secret:new-secret}}'}]})
    projected=(await project_secret_headers(store.session,project_id=project,tools=[tool]))[0]
    dependencies=tool_dependencies(projected)
    denied=AsyncMock(side_effect=AuthorizationError('not granted'))
    with pytest.raises(AuthorizationError):
        await store.approve_legacy_consumers(project_id=project,dependencies=dependencies,authorize=denied,actor='test')
    with pytest.raises(ConfigurationError) as blocked:
        await store.acquire(project_id=project,run_id=uuid4(),environment='draft',dependencies=dependencies)
    assert blocked.value.code=='CONFIG_USAGE_NOT_AUTHORIZED'
    approval=AsyncMock()
    await store.approve_legacy_consumers(project_id=project,dependencies=dependencies,authorize=approval,actor='test')
    approval.assert_awaited_once()
    assert approval.call_args.args[1]==secret.id
    run=uuid4()
    await store.acquire(project_id=project,run_id=run,environment='draft',dependencies=dependencies)
    assert await resolve(store,project,run,dependencies[0])==CANARY
    # Another Tool cannot acquire the same material just by copying the name.
    tool.id=uuid4()
    copied=tool_dependencies((await project_secret_headers(store.session,project_id=project,tools=[tool]))[0])
    with pytest.raises(ConfigurationError):
        await store.acquire(project_id=project,run_id=uuid4(),environment='draft',dependencies=copied)
    policy=await store.session.scalar(select(ConfigurationUsePolicyModel).where(ConfigurationUsePolicyModel.project_id==project))
    await store.revoke_use(project_id=project,policy_id=policy.id,expected_revision=policy.revision,actor='test')
    # Re-saving the old definition preserves a deliberate revocation, rather
    # than implicitly re-granting the route with the editor's admin authority.
    await store.approve_legacy_consumers(project_id=project,dependencies=dependencies,authorize=denied,actor='test')
    with pytest.raises(ConfigurationError):
        await store.acquire(project_id=project,run_id=uuid4(),environment='draft',dependencies=dependencies)


@pytest.mark.asyncio
async def test_inline_tool_material_is_central_owner_scoped_and_rotation_cannot_regrant(configuration, monkeypatch):
    import json
    from copy import deepcopy
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.domain.entities import Tool
    from modules.agent.domain.enums import ToolType
    from modules.agent.domain.tool_configuration import tool_dependencies
    from modules.agent.infra.database.repositories import SQLAlchemyAgentToolRepository
    from modules.agent.infra.database.models import AgentToolModel
    from modules.agent.infra.database import configuration_tool_writer as writer
    from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from modules.core.infra.database.configuration_models import ConfigurationUsePolicyModel
    original, project, _ = configuration
    store = LegacyConfigurationStore(original.session, encryption_key=original.encryption_key)
    monkeypatch.setattr(port, '_factory', lambda session: store)
    monkeypatch.setattr(writer, 'SecretCipherAdapter', lambda: SecretCipherAdapter(store.encryption_key))
    repo = SQLAlchemyAgentToolRepository(store.session)
    source = {'url': 'https://approved.example/api',
        'headers': [{'key': 'Authorization', 'value': 'Bearer ' + CANARY}]}
    tool = await repo.create(Tool(project_id=project, type=ToolType.HTTP, name='Inline bridge', config=deepcopy(source)))
    row = await store.session.get(AgentToolModel, tool.id)
    assert CANARY not in json.dumps(row.config)
    assert row.config['headers'] == []
    dependency, = tool_dependencies(tool)
    run = uuid4()
    await store.acquire(project_id=project, run_id=run, environment='draft', dependencies=[dependency])
    assert await resolve(store, project, run, dependency) == 'Bearer ' + CANARY
    # Rename is metadata-only and preserves the exact reference.
    reference = deepcopy(tool.config['authentication'])
    tool.name = 'Renamed'; tool = await repo.update(tool)
    assert tool.config['authentication'] == reference
    # A copied alias cannot be persisted by another Tool, including internal writers.
    impostor = deepcopy(tool); impostor.id = uuid4()
    with pytest.raises(ConfigurationError) as denied:
        await repo.create(impostor)
    assert denied.value.code == 'CONFIG_USAGE_NOT_AUTHORIZED'
    policy = await store.session.scalar(select(ConfigurationUsePolicyModel).where(ConfigurationUsePolicyModel.project_id == project))
    await store.revoke_use(project_id=project, policy_id=policy.id, expected_revision=policy.revision, actor='test')
    tool.config = deepcopy(source)
    tool.config['headers'][0]['value'] = 'Bearer rotated-test-material'
    tool = await repo.update(tool)
    assert tool.config['authentication'] == reference
    with pytest.raises(ConfigurationError) as denied:
        await store.acquire(project_id=project, run_id=uuid4(), environment='draft', dependencies=tool_dependencies(tool))
    assert denied.value.code == 'CONFIG_USAGE_NOT_AUTHORIZED'
    with pytest.raises(ConfigurationError) as denied:
        await resolve(store, project, run, dependency)
    assert denied.value.code == 'CONFIG_USAGE_NOT_AUTHORIZED'


@pytest.mark.asyncio
async def test_tool_migration_is_sanitized_cas_guarded_and_replayable(configuration, monkeypatch):
    import json
    from datetime import timedelta
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.infra.database.configuration_secret_migration import inventory_configuration_sources, migrate_configuration_source
    from modules.agent.infra.database import configuration_tool_writer as writer
    from modules.agent.infra.database.models import AgentToolModel
    from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from modules.core.infra.services.configuration_migration import ConfigurationMigrationService
    from modules.core.infra.database.configuration_fleet import register_configuration_process, BRIDGE_CAPABILITY
    original, project, _ = configuration
    store = LegacyConfigurationStore(original.session, encryption_key=original.encryption_key)
    monkeypatch.setattr(port, '_factory', lambda session: store)
    monkeypatch.setattr(writer, 'SecretCipherAdapter', lambda: SecretCipherAdapter(store.encryption_key))
    rows = [AgentToolModel(id=UUID(int=5000 + index), project_id=project, name='Old Tool', type='http',
        config={'url': 'https://approved.example/api', 'headers': [{'key': 'Authorization', 'value': CANARY}]}) for index in range(2)]
    store.session.add_all(rows)
    await store.session.flush()
    service = ConfigurationMigrationService(store.session, encryption_key=store.encryption_key,
        inventory=inventory_configuration_sources, cutover=migrate_configuration_source)
    preview = await service.preview(project_id=project, source_kind='tool', limit=1)
    assert preview['scope'] == 'tools' and preview['next_after'] == str(rows[0].id)
    assert CANARY not in json.dumps(preview)
    migration = uuid4()
    await service.create(project_id=project, migration_id=migration, actor='owner', source_kind='tool')
    rows[1].updated_at += timedelta(seconds=1)
    await store.session.flush()
    process = 'tool-bridge-' + str(uuid4())
    await register_configuration_process(store.session, identity=process, capabilities=[BRIDGE_CAPABILITY])
    args = dict(project_id=project, migration_id=migration, actor='owner', expected_revision=1,
        required_processes=[process], old_processes_drained=True)
    result = await service.advance(**args)
    assert result['counts'] == {'completed': 1, 'blocked': 1}
    assert result['items'][1]['code'] == 'CONFIG_REVISION_CONFLICT'
    assert await service.advance(**args) == result
    await store.session.refresh(rows[0])
    assert CANARY not in json.dumps(rows[0].config)
    assert rows[1].config['headers'][0]['value'] == CANARY
    assert CANARY not in json.dumps(result)
    assert (await service.preview(project_id=project, source_kind='tool'))['items'][0]['id'] == str(rows[1].id)


@pytest.mark.asyncio
async def test_tool_migration_does_not_certify_retained_inline_or_broaden_routes(configuration, monkeypatch):
    import json
    from modules.agent.application.interfaces import project_configuration as port
    from modules.agent.infra.database.configuration_tool_migration import inventory_tool_configuration, migrate_tool_configuration
    from modules.agent.infra.database.models import AgentModel, AgentReleaseModel, AgentToolModel
    from modules.core.infra.database.configuration_legacy import LegacyConfigurationStore
    from modules.core.infra.database.configuration_fleet import register_configuration_process, BRIDGE_CAPABILITY
    original, project, _ = configuration
    store = LegacyConfigurationStore(original.session, encryption_key=original.encryption_key)
    monkeypatch.setattr(port, '_factory', lambda session: store)
    config = {'url': 'https://approved.example/api', 'headers': [{'key': 'Authorization', 'value': CANARY}]}
    rows = [AgentToolModel(project_id=project, name='Retained', type='http', config=config),
        AgentToolModel(project_id=project, name='Route local', type='http', config={'base_url': 'https://approved.example',
            'routes': [{'id': 'one', 'path': '/one', 'headers': config['headers']}]}),
        AgentToolModel(project_id=project, name='OAuth', type='mcp', config={'server': {'url': 'https://approved.example/mcp'},
            'oauth': {'status': 'connected', 'access_token_encrypted': 'historical-ciphertext-placeholder'}})]
    agent = AgentModel(project_id=project, name='Historical owner', type='chat', provider='custom', model='example')
    store.session.add_all([*rows, agent]); await store.session.flush()
    release = AgentReleaseModel(project_id=project, agent_id=agent.id, version='1.0.0', status='release',
        snapshot_kind='release', session_mode='stateful', runtime_config={'tools': {'snapshots': [
            {'id': str(rows[0].id), 'config': config}]}})
    store.session.add(release); await store.session.flush()
    result = await inventory_tool_configuration(store.session, project_id=project)
    assert len(result['items']) == 3 and all(item['state'] == 'blocked' for item in result['items'])
    assert CANARY not in json.dumps(result) and 'historical-ciphertext-placeholder' not in json.dumps(result)
    process = 'retention-tool-bridge-' + str(uuid4())
    await register_configuration_process(store.session, identity=process, capabilities=[BRIDGE_CAPABILITY])
    with pytest.raises(ConfigurationError) as blocked:
        await migrate_tool_configuration(store.session, project_id=project, tool_id=rows[0].id,
            expected_revision=rows[0].updated_at.isoformat(), destinations=['https://approved.example/api'],
            required_processes=[process], actor='owner')
    assert blocked.value.code == 'LEGACY_FORMAT_UNSUPPORTED'
    assert release.runtime_config['tools']['snapshots'][0]['config'] == config
    assert rows[0].config == config
