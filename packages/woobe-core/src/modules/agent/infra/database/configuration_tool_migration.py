"""Bounded cutover for mutable, unretained global Tool header sources."""
from types import SimpleNamespace

from sqlalchemy import select, update

from modules.agent.application.interfaces.project_configuration import configuration_for_session
from modules.agent.application.interfaces.tool_types import HTTP_COMPATIBLE_TYPES, MCP_COMPATIBLE_TYPES
from modules.agent.domain.tool_configuration import tool_dependencies, validate_tool_authentication
from modules.agent.domain.tool_inline_configuration import extract_inline_tool_headers
from modules.agent.infra.database.configuration_quiescence import assert_configuration_quiescent
from modules.agent.infra.database.configuration_tool_writer import centralize_tool_headers
from modules.agent.infra.database.mappers import model_to_tool
from modules.agent.infra.database.models import AgentReleaseModel, AgentToolModel
from shared.contracts.project_configuration import ConfigurationError


def _source(row, project_id):
    config, material = extract_inline_tool_headers(row.config or {})
    # OAuth and route-local material require different authority boundaries.
    if config.get('oauth') or any(extract_inline_tool_headers(route)[1] for route in config.get('routes', [])):
        raise ConfigurationError('LEGACY_FORMAT_UNSUPPORTED')
    if not material:
        return []
    config['authentication'] = {'type': 'headers', 'fields': {
        field: {'source': 'project_environment', 'key': 'PENDING'} for field in material}}
    validate_tool_authentication(config)
    return tool_dependencies(SimpleNamespace(id=row.id, project_id=project_id, config=config))


async def _require_no_retained_source(session, *, project_id, tool_id):
    # Moving a current definition alone must not certify contraction while an
    # old signed snapshot still treats its literal as executable authority.
    retained = await session.scalar(select(AgentReleaseModel.id).where(
        AgentReleaseModel.project_id == project_id,
        AgentReleaseModel.runtime_config['tools']['snapshots'].contains([{'id': str(tool_id)}]),
    ).limit(1))
    if retained is not None:
        raise ConfigurationError('LEGACY_FORMAT_UNSUPPORTED')


async def inventory_tool_configuration(session, *, project_id, after_id=None, limit=100):
    statement = select(AgentToolModel.id, AgentToolModel.type, AgentToolModel.config, AgentToolModel.updated_at).where(
        AgentToolModel.project_id == project_id,
        AgentToolModel.type.in_(sorted(HTTP_COMPATIBLE_TYPES | MCP_COMPATIBLE_TYPES)))
    if after_id is not None:
        statement = statement.where(AgentToolModel.id > after_id)
    rows = (await session.execute(statement.order_by(AgentToolModel.id).limit(limit + 1))).all()
    items = []
    for row in rows[:limit]:
        item = {'kind': 'tool', 'id': str(row.id), 'revision': row.updated_at.isoformat(),
                'state': 'eligible', 'destinations': []}
        try:
            dependencies = _source(row, project_id)
            if not dependencies:
                continue
            await _require_no_retained_source(session, project_id=project_id, tool_id=row.id)
            item['destinations'] = sorted({dependency.destination for dependency in dependencies})
        except (ConfigurationError, ValueError, TypeError):
            item.update(state='blocked', code='LEGACY_FORMAT_UNSUPPORTED')
        items.append(item)
    return {'items': items, 'next_after': str(rows[limit - 1].id) if len(rows) > limit else None}


async def migrate_tool_configuration(session, *, project_id, tool_id, expected_revision, destinations,
                                     required_processes, actor):
    store = configuration_for_session(session)
    if store is None:
        raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
    await store.lock_project(project_id)
    await store.require_bridge(required_processes=required_processes)
    await assert_configuration_quiescent(session, project_id=project_id)
    row = await session.scalar(select(AgentToolModel).where(AgentToolModel.project_id == project_id,
        AgentToolModel.id == tool_id).with_for_update().execution_options(populate_existing=True))
    if row is None:
        raise ConfigurationError('CONFIG_REFERENCE_NOT_FOUND')
    dependencies = _source(row, project_id)
    if not dependencies:
        await centralize_tool_headers(session, model_to_tool(row), actor=actor)
        authentication = (row.config or {}).get('authentication') or {}
        fields = authentication.get('fields') or {}
        if not fields or any(ref.get('source') != 'legacy_configuration' for ref in fields.values()):
            raise ConfigurationError('CONFIG_REVISION_CONFLICT')
        states = [await store.legacy_source_state(project_id=project_id, source_kind='tool', source_id=row.id,
            field_path='/config/authentication/fields/' + field) for field in fields]
        return {'id': str(row.id), 'state': 'completed', 'material': 'unchanged', 'unchanged': True} if all(
            state['material'] == 'present' for state in states) else {'id': str(row.id), 'state': 'cutover', 'material': 'unavailable'}
    if row.updated_at.isoformat() != expected_revision or sorted({dep.destination for dep in dependencies}) != sorted(destinations):
        raise ConfigurationError('CONFIG_REVISION_CONFLICT')
    await _require_no_retained_source(session, project_id=project_id, tool_id=row.id)
    tool = model_to_tool(row)
    await centralize_tool_headers(session, tool, actor=actor)
    await store.register_references(tool_dependencies(tool))
    await session.execute(update(AgentToolModel).where(AgentToolModel.id == row.id).values(
        config=tool.config, updated_at=row.updated_at))
    await session.flush()
    return {'id': str(row.id), 'state': 'cutover', 'material': 'present', 'unchanged': False}
