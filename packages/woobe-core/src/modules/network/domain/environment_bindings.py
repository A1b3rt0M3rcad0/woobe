from __future__ import annotations

from modules.network.domain.entities import NetworkDefinition


class NetworkEnvironmentBindingError(ValueError):
    pass


def validate_network_environment_bindings(
    definition: NetworkDefinition,
    environment: str,
) -> None:
    allowed = {
        "draft": {"draft", "staging", "release"},
        "staging": {"staging", "release"},
        "production": {"release"},
        "candidate": {"candidate"},
    }.get(environment)
    if allowed is None:
        raise NetworkEnvironmentBindingError(
            f"Unsupported Network environment: {environment}"
        )
    for node in definition.nodes:
        if node.binding.source in allowed:
            continue
        if environment == "staging":
            raise NetworkEnvironmentBindingError(
                f"Agent {node.label} cannot use a Draft binding in Network Staging"
            )
        if environment == "production":
            raise NetworkEnvironmentBindingError(
                f"Agent {node.label} must use an immutable Agent Release in Network Production"
            )
        raise NetworkEnvironmentBindingError(
            f"Agent {node.label} uses an invalid binding for Network {environment.title()}"
        )
