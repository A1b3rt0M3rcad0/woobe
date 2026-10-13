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
        assert len(statements) <= 4 * len(durations)
        assert max(inspected) == 1
        assert all("stored_value" not in statement for statement in statements)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    print({"keys": key_count, "references": reference_count, "milliseconds": durations, "queries_per_read": len(statements) / len(durations)})


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
