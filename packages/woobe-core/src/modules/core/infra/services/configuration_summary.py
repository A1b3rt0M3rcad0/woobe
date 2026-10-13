"""Selected-Environment projection; never resolves values or grants execution."""
from datetime import UTC, datetime
from shared.contracts.errors import NotFoundError, ValidationError, ConflictError
from shared.contracts.project_configuration import ConfigurationError


async def configuration_summary(session, *, project_id, environment, inventory, reader, inspect, authorize):
    page = await inventory(session, project_id=project_id, environment=environment, limit=50)
    # Authorize the complete bounded observation before deriving counts or
    # exposing identities. A partial authority must never get global counts.
    for target in page['targets']:
        await authorize(target)
    dependencies, unresolved, affected, unselected = {}, [], set(), 0
    notices = False
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
        result, _ = await inspect(project_id=project_id, environment=environment, dependencies=closure['dependencies'])
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
    unknown = bool(unresolved) or not page['complete']
    return {'environment': environment,
        'state': 'unknown' if unknown else 'blocked' if blocked else 'ready_with_notices' if notices else 'ready',
        'complete': page['complete'] and not unresolved, 'checked_at': datetime.now(UTC).isoformat(),
        'scope': 'current_selections', 'inspected_target_count': len(page['targets']),
        'unselected_target_count': unselected, 'affected_target_count': len(affected),
        'required_key_count': len({item['key'] for item in items if item['required']}),
        'missing_key_count': len({item['key'] for item in blocked if item['material']=='missing'}),
        'blocked_key_count': len({item['key'] for item in blocked}),
        'affected_consumer_count': len({(item['consumer_kind'],item['consumer_id']) for item in blocked})}
