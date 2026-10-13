"""Host-wired acceptance port sharing the authoritative Network transaction."""
_accept = None


def configure_configuration_acceptance(accept):
    global _accept
    _accept = accept


async def accept_configuration(session, *, project_id, run_id, environment, bindings):
    if _accept is not None:
        return await _accept(session, project_id=project_id, run_id=run_id,
                             environment=environment, bindings=bindings)
    return []
