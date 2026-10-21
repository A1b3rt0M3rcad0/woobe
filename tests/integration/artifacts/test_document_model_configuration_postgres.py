from copy import deepcopy
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.core.entrypoint import build_operation_configuration_runtime_resolver
from modules.core.infra.database.configuration_models import ConfigurationLeaseModel
from modules.core.infra.database.configuration_resolution import ConfigurationResolution
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.contracts.project_configuration import ConfigurationDependency, ConfigurationError


CANARY = 'document-operation-private-test-material'
ENCRYPTION_KEY = 'disposable-document-operation-key'


async def operation_snapshot(engine, project):
    consumer, operation = uuid4(), uuid4()
    async with ArtifactsUnitOfWork(engine) as uow:
        store = ConfigurationResolution(uow.session, encryption_key=ENCRYPTION_KEY)
        key = await store.declare(project_id=project, key='MODEL_' + uuid4().hex.upper())
        key_id = UUID(key['id'])
        await store.write_value(project_id=project, key_id=key_id, environment='staging',
            expected_revision=0, value=CANARY)
        dep = ConfigurationDependency(project, 'provider_credential', consumer, '1',
            '/authentication/fields/api_key', key['key'], 'https://provider.example/v1')
        policy = await store.grant_use(project_id=project, key_id=key_id, consumer_kind=dep.consumer_kind,
            consumer_scope=str(consumer), destination=dep.destination, environments=['staging'],
            field_paths=[dep.field_path], expected_revision=0, actor='fixture-owner')
        evidence = await store.activation_evidence(project_id=project, environment='staging', dependencies=[dep])
    snapshot = {**evidence, 'project_id': str(project), 'operation_kind': 'artifact_processing', 'operation_id': str(operation)}
    assert CANARY not in str(snapshot)
    return snapshot, dep, key_id, policy


def resolver(engine, snapshot):
    async def accepted_operation(**identity):
        if (str(identity['project_id']), identity['operation_kind'], str(identity['operation_id'])) != (
            snapshot['project_id'], snapshot['operation_kind'], snapshot['operation_id']):
            raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
        return deepcopy(snapshot)
    return build_operation_configuration_runtime_resolver(operation_verifier=accepted_operation,
        session_factory=async_sessionmaker(engine, expire_on_commit=False), encryption_key=ENCRYPTION_KEY)


def identity(snapshot, dep):
    return {'project_id': dep.project_id, 'operation_kind': snapshot['operation_kind'],
        'operation_id': UUID(snapshot['operation_id']), 'consumer_kind': dep.consumer_kind,
        'consumer_id': dep.consumer_id, 'field_path': dep.field_path, 'destination': dep.destination + '/chat/completions'}


async def test_non_run_operation_resolves_only_accepted_environment_pins_and_keeps_rotation_frozen(engine, artifacts_database):
    project = UUID(artifacts_database['project_id'])
    snapshot, dep, key, policy = await operation_snapshot(engine, project)
    resolve = resolver(engine, snapshot)
    context = identity(snapshot, dep)
    result = await resolve(**context)
    assert result.value == CANARY and CANARY not in repr(result)
    async with ArtifactsUnitOfWork(engine) as uow:
        store = ConfigurationResolution(uow.session, encryption_key=ENCRYPTION_KEY)
        await store.write_value(project_id=project, key_id=key, environment='staging',
            expected_revision=1, value='rotated-document-operation-material')
        assert await uow.session.scalar(select(func.count()).select_from(ConfigurationLeaseModel).where(
            ConfigurationLeaseModel.project_id == project)) == 0
    # No run_id/Run lease is invented; accepted immutable pins retain their version.
    assert (await resolve(**context)).value == CANARY
    for changed in ({'consumer_id': uuid4()}, {'destination': 'https://foreign.example/v1'}, {'operation_id': uuid4()}):
        with pytest.raises(ConfigurationError):
            await resolve(**{**context, **changed})
    async with ArtifactsUnitOfWork(engine) as uow:
        await ConfigurationResolution(uow.session, encryption_key=ENCRYPTION_KEY).revoke_use(
            project_id=project, policy_id=UUID(policy['id']), expected_revision=1, actor='fixture-owner')
    with pytest.raises(ConfigurationError) as failure:
        await resolve(**context)
    assert failure.value.code == 'CONFIG_USAGE_NOT_AUTHORIZED'


async def test_operation_snapshot_cannot_cross_project_definition_environment_or_bypass_verifier(engine, artifacts_database):
    project = UUID(artifacts_database['project_id'])
    snapshot, dep, key, policy = await operation_snapshot(engine, project)
    context = identity(snapshot, dep)
    for changed in (
        {'project_id': str(uuid4())}, {'operation_id': str(uuid4())}, {'operation_kind': 'invented'},
        {'environment': 'production'}, {'definitions': [{'key_id': str(key), 'revision': 999}]},
        {'pins': [{**snapshot['pins'][0], 'source': 'legacy_compat'}]},
    ):
        supplied = {**snapshot, **changed}
        async def invalid_verifier(**kwargs):
            return supplied
        resolve = build_operation_configuration_runtime_resolver(operation_verifier=invalid_verifier,
            session_factory=async_sessionmaker(engine), encryption_key=ENCRYPTION_KEY)
        with pytest.raises(ConfigurationError):
            await resolve(**context)
    with pytest.raises(TypeError):
        build_operation_configuration_runtime_resolver(operation_verifier=None)


async def test_mutable_provider_model_has_a_real_definition_revision_distinct_from_spec_schema_version(engine, artifacts_database):
    from sqlalchemy import text
    from modules.agent.domain.entities import ProviderModel
    from modules.agent.infra.database.models import ProviderCredentialModel
    from modules.agent.infra.database.provider_model_repositories import SQLAlchemyProviderModelRepository
    project, credential_id = UUID(artifacts_database['project_id']), uuid4()
    async with ArtifactsUnitOfWork(engine) as uow:
        uow.session.add(ProviderCredentialModel(id=credential_id, project_id=project, provider='openai',
            name='Model revision fixture', authentication={'type': 'api_key', 'fields': {
                'api_key': {'source': 'project_environment', 'key': 'MODEL_REVISION_KEY'}}}))
        await uow.session.flush()
        models = SQLAlchemyProviderModelRepository(uow.session)
        model = await models.save(ProviderModel(project_id=project, provider_credential_id=credential_id,
            name='First model', model='fixture-model', model_type='language', spec_version=1))
        assert model.definition_revision == 1
        model.name = 'Updated model definition'
        changed = await models.update(model)
        assert changed.definition_revision == 2 and changed.spec_version == 1
        await uow.session.execute(text('UPDATE agent.provider_models SET definition_revision=999 WHERE id=:id'), {'id': model.id})
        # A caller cannot spoof the revision independently from its definition.
        assert await uow.session.scalar(text('SELECT definition_revision FROM agent.provider_models WHERE id=:id'), {'id': model.id}) == 2


async def test_model_binding_freeze_is_metadata_only_and_detects_changed_definition_or_credential(engine, artifacts_database, monkeypatch):
    from sqlalchemy import event, text
    from modules.agent.entrypoint import build_operation_model_bindings
    from modules.agent.domain.entities import ProviderModel
    from modules.agent.infra.database.models import ProviderCredentialModel
    from modules.agent.infra.database.provider_model_repositories import SQLAlchemyProviderModelRepository
    from modules.core.infra.database import configuration_resolution as resolution
    project = UUID(artifacts_database['project_id'])
    credential_id = uuid4()
    async with ArtifactsUnitOfWork(engine) as uow:
        store = ConfigurationResolution(uow.session, encryption_key=ENCRYPTION_KEY)
        key_name = 'FROZEN_MODEL_' + uuid4().hex.upper()
        key = await store.declare(project_id=project, key=key_name)
        key_id = UUID(key['id'])
        await store.write_value(project_id=project, key_id=key_id, environment='staging', expected_revision=0, value=CANARY)
        uow.session.add(ProviderCredentialModel(id=credential_id, project_id=project, provider='openai',
            name='Frozen model fixture', authentication={'type': 'api_key', 'fields': {
                'api_key': {'source': 'project_environment', 'key': key_name}}}))
        await uow.session.flush()
        model = await SQLAlchemyProviderModelRepository(uow.session).save(ProviderModel(project_id=project,
            provider_credential_id=credential_id, name='Frozen text model', model='fixture-model', model_type='language'))
        await store.grant_use(project_id=project, key_id=key_id, consumer_kind='provider_credential',
            consumer_scope=str(credential_id), destination='https://api.openai.com/v1',
            environments=['staging'], field_paths=['/authentication/fields/api_key'], expected_revision=0, actor='fixture-owner')
    statements = []
    def observe(_connection, _cursor, statement, *args):
        statements.append(statement)
    def forbidden_decrypt(*args):
        pytest.fail('Binding metadata must never decrypt credentials')
    monkeypatch.setattr(resolution, 'decrypt_secret', forbidden_decrypt)
    event.listen(engine.sync_engine, 'before_cursor_execute', observe)
    try:
        async with ArtifactsUnitOfWork(engine) as uow:
            bindings = build_operation_model_bindings(uow.session,
                configuration=ConfigurationResolution(uow.session, encryption_key=ENCRYPTION_KEY))
            frozen = await bindings.freeze(project_id=project, environment='staging', model_id=model.id,
                model_revision=1, configuration_key_id=key_id, configuration_revision=1)
            assert frozen['definition']['model_revision'] == 1
            assert frozen['definition']['credential_id'] == str(credential_id)
            assert frozen['configuration']['pins'][0]['key_id'] == str(key_id)
            assert CANARY not in str(frozen)
            assert await bindings.verify(frozen, project_id=project) == frozen['definition']
    finally:
        event.remove(engine.sync_engine, 'before_cursor_execute', observe)
    assert all('encrypted_secret' not in statement and 'stored_value' not in statement for statement in statements)
    async with ArtifactsUnitOfWork(engine) as uow:
        await uow.session.execute(text("UPDATE agent.provider_models SET model='changed-model' WHERE id=:id"), {'id': model.id})
    async with ArtifactsUnitOfWork(engine) as uow:
        bindings = build_operation_model_bindings(uow.session,
            configuration=ConfigurationResolution(uow.session, encryption_key=ENCRYPTION_KEY))
        with pytest.raises(ConfigurationError) as failure:
            await bindings.verify(frozen, project_id=project)
        assert failure.value.code == 'CONFIG_REVISION_CONFLICT'


async def test_cached_operation_authority_is_checked_without_decrypt_and_allows_value_rotation(engine, artifacts_database, monkeypatch):
    from modules.core.infra.database import configuration_resolution as resolution
    project = UUID(artifacts_database['project_id'])
    snapshot, dep, key_id, policy = await operation_snapshot(engine, project)
    async with ArtifactsUnitOfWork(engine) as uow:
        store = ConfigurationResolution(uow.session, encryption_key=ENCRYPTION_KEY)
        await store.write_value(project_id=project, key_id=key_id, environment='staging',
            expected_revision=1, value='rotated-disposable-document-material')
    def forbidden_decrypt(*args):
        pytest.fail('Cached model authority verification must remain metadata only')
    monkeypatch.setattr(resolution, 'decrypt_secret', forbidden_decrypt)
    async with ArtifactsUnitOfWork(engine) as uow:
        store = ConfigurationResolution(uow.session, encryption_key=ENCRYPTION_KEY)
        assert await store.verify_operation_evidence(project_id=project, environment='staging', dependencies=[dep], evidence=snapshot)
        await store.revoke_use(project_id=project, policy_id=UUID(policy['id']), expected_revision=1, actor='fixture-owner')
    async with ArtifactsUnitOfWork(engine) as uow:
        with pytest.raises(ConfigurationError):
            await ConfigurationResolution(uow.session, encryption_key=ENCRYPTION_KEY).verify_operation_evidence(
                project_id=project, environment='staging', dependencies=[dep], evidence=snapshot)
