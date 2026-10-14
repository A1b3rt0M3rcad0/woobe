"""Move newly supplied global Tool header material into its central owner."""
from copy import deepcopy
from uuid import UUID

from modules.agent.application.interfaces.project_configuration import configuration_for_session
from modules.agent.application.interfaces.tool_types import is_http_tool_type, is_mcp_tool_type
from modules.agent.domain.tool_configuration import tool_authentication, tool_dependencies
from modules.agent.domain.tool_inline_configuration import extract_inline_tool_headers
from modules.agent.infra.adapters.secret_cipher import SecretCipherAdapter
from shared.contracts.project_configuration import ConfigurationError


async def centralize_tool_headers(session, tool, *, actor='legacy-tool-write'):
    if not (is_http_tool_type(tool.type) or is_mcp_tool_type(tool.type)):
        return
    config, material = extract_inline_tool_headers(tool.config)
    store = configuration_for_session(session)
    if material:
        if store is None:
            raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
        await store.lock_project(tool.project_id)
        projected = deepcopy(tool)
        projected.config = config
        config['authentication'] = {'type': 'headers', 'fields': {
            name: {'source': 'project_environment', 'key': 'PENDING'} for name in material}}
        dependencies = tool_dependencies(projected)
        cipher = SecretCipherAdapter()
        for dependency in dependencies:
            name = dependency.field_path.rsplit('/', 1)[-1]
            reference = await store.legacy_reference(project_id=tool.project_id, source_kind='tool',
                source_id=tool.id, field_path=dependency.field_path)
            encrypted = await cipher.encrypt(material[name])
            if reference is None:
                adopted = await store.adopt(project_id=tool.project_id, source_kind='tool', source_id=tool.id,
                    field_path=dependency.field_path, source_revision='legacy-tool-write:' + str(tool.id),
                    encrypted_value=encrypted, dependencies=[dependency], actor=actor)
                if adopted['phase'] not in {'cutover', 'completed'}:
                    raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
                reference = {'source': 'legacy_configuration', 'key': adopted['key'], 'alias_id': adopted['alias_id']}
            else:
                # Rotation does not grant a changed destination or resurrect a
                # revoked policy. Environment-split aliases reject ambiguity.
                await store.rotate_legacy(project_id=tool.project_id, alias_id=UUID(reference['alias_id']),
                    encrypted_value=encrypted, source_revision='legacy-tool-write:' + str(tool.updated_at),
                    actor=actor)
            config['authentication']['fields'][name] = reference
        tool.config = config

    # Only owner-produced aliases can be persisted in a Tool definition. This
    # is independent of the request DTO, including internal materializers.
    authentication = tool_authentication(tool.config or {}, allow_legacy=True)
    for name, reference in (authentication or {}).get('fields', {}).items():
        if reference['source'] != 'legacy_configuration':
            continue
        if store is None:
            raise ConfigurationError('CONFIG_STORE_UNAVAILABLE')
        owned = await store.legacy_reference(project_id=tool.project_id, source_kind='tool', source_id=tool.id,
            field_path='/config/authentication/fields/' + name)
        if owned != reference:
            raise ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')
