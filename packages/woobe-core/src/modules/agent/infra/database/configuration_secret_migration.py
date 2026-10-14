"""Metadata inventory and atomic cutover of recognized legacy Secret headers."""
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select, update
from modules.agent.application.interfaces.project_configuration import configuration_for_session
from modules.agent.domain.legacy_tool_configuration import bind_legacy_tool_headers, legacy_tool_secret_names
from modules.agent.domain.tool_configuration import tool_dependencies
from modules.agent.infra.database.models import AgentToolModel, AgentToolSecretModel, AgentReleaseModel
from modules.agent.infra.database.configuration_quiescence import assert_configuration_quiescent
from shared.contracts.project_configuration import ConfigurationError


async def _consumer_closures(session, *, project_id, names):
    reference = {'source': 'legacy_configuration', 'key': 'PENDING', 'alias_id': str(UUID(int=1))}
    captured, errors = {name: {} for name in names}, {}

    def inspect(identifier, config):
        for name in legacy_tool_secret_names(config) & names:
            if name in errors:
                continue
            try:
                tool = bind_legacy_tool_headers(SimpleNamespace(id=identifier, project_id=project_id, config=config), {name: reference})
                for dependency in tool_dependencies(tool):
                    if dependency.key == 'PENDING':
                        identity = (str(identifier), dependency.field_path, dependency.destination)
                        captured[name][identity] = dependency
            except (ConfigurationError, ValueError, TypeError) as error:
                errors[name] = error if isinstance(error, ConfigurationError) else ConfigurationError('LEGACY_FORMAT_UNSUPPORTED')

    # Keyset pages bound materialized author documents. One scan per inventory
    # page (not one scan for each Secret); no source ciphertext is selected.
    after = None
    while True:
        statement = select(AgentToolModel.id, AgentToolModel.config).where(AgentToolModel.project_id == project_id)
        if after is not None:
            statement = statement.where(AgentToolModel.id > after)
        page = (await session.execute(statement.order_by(AgentToolModel.id).limit(100))).all()
        for row in page:
            inspect(row.id, row.config or {})
        if len(page) < 100:
            break
        after = page[-1].id
    after = None
    while True:
        statement = select(AgentReleaseModel.id, AgentReleaseModel.runtime_config).where(AgentReleaseModel.project_id == project_id)
        if after is not None:
            statement = statement.where(AgentReleaseModel.id > after)
        page = (await session.execute(statement.order_by(AgentReleaseModel.id).limit(25))).all()
        for row in page:
            for raw in ((row.runtime_config or {}).get('tools') or {}).get('snapshots', []):
                if isinstance(raw, dict) and raw.get('id'):
                    try:
                        inspect(UUID(str(raw['id'])), raw.get('config') or {})
                    except (ValueError, TypeError):
                        for name in legacy_tool_secret_names(raw) & names:
                            errors[name] = ConfigurationError('LEGACY_FORMAT_UNSUPPORTED')
        if len(page) < 25:
            break
        after = page[-1].id
    return {name: errors.get(name) or (list(dependencies.values()),
        sha256(json.dumps(sorted(dependencies), separators=(',', ':')).encode()).hexdigest())
        for name, dependencies in captured.items()}


async def _consumers(session, *, project_id, name):
    result = (await _consumer_closures(session, project_id=project_id, names={name}))[name]
    if isinstance(result, ConfigurationError):
        raise result
    return result


async def inventory_secret_configuration(session, *, project_id, after_id=None, limit=100):
    statement = select(AgentToolSecretModel.id, AgentToolSecretModel.name, AgentToolSecretModel.type,
        AgentToolSecretModel.updated_at).where(AgentToolSecretModel.project_id == project_id,
        AgentToolSecretModel.configuration_reference.is_(None))
    if after_id is not None:
        statement = statement.where(AgentToolSecretModel.id > after_id)
    rows = (await session.execute(statement.order_by(AgentToolSecretModel.id).limit(limit + 1))).all()
    items = []
    closures = await _consumer_closures(session, project_id=project_id, names={row.name for row in rows[:limit]}) if rows else {}
    for row in rows[:limit]:
        item = {'kind': 'secret', 'id': str(row.id), 'revision': row.updated_at.isoformat(), 'state': 'eligible', 'destinations': []}
        try:
            if row.type not in {'api_key', 'custom'}:
                raise ConfigurationError('LEGACY_FORMAT_UNSUPPORTED')
            result = closures[row.name]
            if isinstance(result, ConfigurationError):
                raise result
            dependencies, closure = result
            item.update(closure=closure, consumers=len(dependencies), destinations=sorted({dep.destination for dep in dependencies}))
        except (ConfigurationError, ValueError, TypeError) as error:
            item.update(state='blocked', code=error.code if isinstance(error, ConfigurationError) else 'LEGACY_FORMAT_UNSUPPORTED')
        items.append(item)
    return {'items': items, 'next_after': str(rows[limit - 1].id) if len(rows) > limit else None}


async def migrate_secret_configuration(session, *, project_id, secret_id, expected_revision, expected_closure,
                                       required_processes, actor):
    port = configuration_for_session(session)
    if port is None:
        raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
    await port.lock_project(project_id)
    await port.require_bridge(required_processes=required_processes)
    await assert_configuration_quiescent(session, project_id=project_id)
    row = await session.scalar(select(AgentToolSecretModel).where(AgentToolSecretModel.id == secret_id,
        AgentToolSecretModel.project_id == project_id).with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise ConfigurationError('CONFIG_REFERENCE_NOT_FOUND')
    if row.configuration_reference is not None:
        return await port.legacy_source_state(project_id=project_id, source_kind='secret', source_id=row.id, field_path='/value')
    if row.updated_at.isoformat() != expected_revision:
        raise ConfigurationError('CONFIG_REVISION_CONFLICT')
    if row.type not in {'api_key', 'custom'}:
        raise ConfigurationError('LEGACY_FORMAT_UNSUPPORTED')
    dependencies, closure = await _consumers(session, project_id=project_id, name=row.name)
    if closure != expected_closure:
        raise ConfigurationError('CONFIG_REVISION_CONFLICT')
    result = await port.adopt(project_id=project_id, source_kind='secret', source_id=row.id,
        field_path='/value', source_revision=expected_revision, encrypted_value=row.encrypted_value,
        dependencies=dependencies, actor=actor)
    reference = {'source': 'legacy_configuration', 'key': result['key'], 'alias_id': result['alias_id']}
    await session.execute(update(AgentToolSecretModel).where(AgentToolSecretModel.id == row.id).values(
        configuration_reference=reference, encrypted_value=None, updated_at=row.updated_at))
    await session.flush()
    return {'id': str(row.id), 'state': result['phase'], 'material': result['state'], 'unchanged': False}


async def inventory_configuration_sources(session, *, project_id, source_kind='provider_credential', after_id=None, limit=100):
    if source_kind == 'provider_credential':
        from modules.agent.infra.database.configuration_provider_migration import inventory_provider_configuration
        return await inventory_provider_configuration(session, project_id=project_id, after_id=after_id, limit=limit)
    if source_kind == 'secret':
        return await inventory_secret_configuration(session, project_id=project_id, after_id=after_id, limit=limit)
    if source_kind == 'tool':
        from modules.agent.infra.database.configuration_tool_migration import inventory_tool_configuration
        return await inventory_tool_configuration(session, project_id=project_id, after_id=after_id, limit=limit)
    raise ConfigurationError('CONFIG_DEFINITION_INVALID')


async def migrate_configuration_source(session, **arguments):
    if 'tool_id' in arguments:
        from modules.agent.infra.database.configuration_tool_migration import migrate_tool_configuration
        return await migrate_tool_configuration(session, **arguments)
    if 'secret_id' in arguments:
        return await migrate_secret_configuration(session, **arguments)
    from modules.agent.infra.database.configuration_provider_migration import migrate_provider_configuration
    return await migrate_provider_configuration(session, **arguments)
