from shared.security.principal import AuthenticatedPrincipal, ControlPlanePrincipal, ProjectApiPrincipal


TYPES = {'user': AuthenticatedPrincipal, 'control': ControlPlanePrincipal, 'runtime': ProjectApiPrincipal}


def freeze_principal(principal):
    if isinstance(principal, AuthenticatedPrincipal):
        kind = 'user'
    elif isinstance(principal, ControlPlanePrincipal):
        kind = 'control'
    elif isinstance(principal, ProjectApiPrincipal) and principal.kind == 'runtime':
        kind = 'runtime'
    else:
        raise ValueError('Unsupported processing principal')
    return {'type': kind, 'principal': principal.model_dump(mode='json')}


def restore_principal(snapshot):
    return TYPES[snapshot['type']].model_validate(snapshot['principal'])
