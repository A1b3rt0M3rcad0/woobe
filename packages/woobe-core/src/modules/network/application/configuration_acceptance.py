"""Host-wired acceptance port sharing the authoritative Network transaction."""
_accept = None


def configure_configuration_acceptance(accept):
    global _accept
    _accept = accept


async def lock_configuration(session, *, project_id):
    # Configuration-aware hosts lock Project before Network/Session rows. The
    # final prepare/accept call remains the authority check, not this ordering aid.
    if _accept is not None:
        await _accept.lock(session, project_id=project_id)


async def accept_configuration(session, *, project_id, run_id, environment, bindings):
    if _accept is not None:
        return await _accept(session, project_id=project_id, run_id=run_id,
                             environment=environment, bindings=bindings)
    return []


async def prepare_configuration(session, *, project_id, environment, bindings):
    from shared.contracts.project_configuration import ConfigurationError
    if _accept is None:
        raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
    return await _accept.prepare(session, project_id=project_id,
        environment=environment, bindings=bindings)


async def configuration_status(session, *, project_id, environment, bindings):
    from shared.contracts.project_configuration import ConfigurationError
    if _accept is None:
        raise ConfigurationError("CONFIG_STORE_UNAVAILABLE")
    return await _accept.status(session, project_id=project_id,
        environment=environment, bindings=bindings)
