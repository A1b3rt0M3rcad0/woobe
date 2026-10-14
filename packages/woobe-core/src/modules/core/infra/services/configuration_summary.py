"""Selected-Environment projection; never resolves values or grants execution."""
from datetime import UTC, datetime
from shared.contracts.errors import NotFoundError, ValidationError, ConflictError
from shared.contracts.project_configuration import ConfigurationError


async def configuration_summary(session, *, project_id, environment, inventory, reader, inspect_many, authorize, limit=50, cursor=None):
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ConfigurationError('CONFIG_DEFINITION_INVALID')
    page = await inventory(session, project_id=project_id, environment=environment, limit=limit, cursor=cursor)
    # Authorize the complete bounded observation before deriving counts or
    # exposing identities. A partial authority must never get global counts.
    for target in page.get('authorization_targets', page['targets']):
        await authorize(target)
    dependencies, unresolved, affected, unselected = {}, [], set(), 0
    notices = False
    closures = []
    for target in page['targets']:
        identity = (target['kind'], str(target['id']))
        if not target['selected']:
            unselected += 1
            continue
        try:
            closure = await reader(session, project_id=project_id, target_kind=target['kind'],
                target_id=target['id'], environment=environment)
        except ConfigurationError as error:
            unresolved.append(error.code)
            affected.add(identity)
            continue
        except (NotFoundError, ValidationError, ConflictError):
            unresolved.append('CONFIG_DEPENDENCY_UNRESOLVED')
            affected.add(identity)
            continue
        closures.append((identity, closure))
    results = await inspect_many(project_id=project_id, environment=environment,
        groups=[closure['dependencies'] for _, closure in closures])
    for (identity, closure), (result, _) in zip(closures, results, strict=True):
        if closure['unresolved'] or result['state'] == 'unknown':
            unresolved.append('CONFIG_DEPENDENCY_UNRESOLVED')
        notices = notices or result['state'] == 'ready_with_notices'
        if closure['unresolved'] or result['state'] in {'unknown','blocked'}:
            affected.add(identity)
        for item in result['dependencies']:
            key = (item['key'], item['consumer_kind'], item['consumer_id'], item['field_path'], item['required'], item['code'], item['material'])
            dependencies[key] = item
    items = list(dependencies.values())
    blocked = [item for item in items if item['required'] and item.get('code')]
    unknown = bool(unresolved) or not page['complete'] or cursor is not None
    page_state = 'unknown' if unresolved else 'blocked' if blocked else 'ready_with_notices' if notices else 'ready'
    return {'environment': environment,
        'state': 'unknown' if unknown else 'blocked' if blocked else 'ready_with_notices' if notices else 'ready',
        'complete': not unknown, 'checked_at': datetime.now(UTC).isoformat(),
        'scope': 'current_selections_page' if cursor is not None or not page['complete'] else 'current_selections',
        'page_state': page_state, 'page_complete': not unresolved, 'has_next': not page['complete'],
        'next_cursor': page.get('next_cursor'), 'limit': limit,
        'inspected_target_count': len(page['targets']),
        'unselected_target_count': unselected, 'affected_target_count': len(affected),
        'required_key_count': len({item['key'] for item in items if item['required']}),
        'missing_key_count': len({item['key'] for item in blocked if item['material']=='missing'}),
        'blocked_key_count': len({item['key'] for item in blocked}),
        'affected_consumer_count': len({(item['consumer_kind'],item['consumer_id']) for item in blocked})}
