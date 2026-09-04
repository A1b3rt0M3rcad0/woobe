"""Idempotent installation of legacy-compatible Network service extensions."""

_installed = False


def install_network_service_extensions() -> None:
    global _installed
    if _installed:
        return

    # Import database model extensions before services inspect the additional
    # mapped columns and Production activation model.
    from modules.network.infra.database import schema_extensions  # noqa: F401
    from modules.network.application.structured_output_persistence import (
        install_structured_output_persistence,
    )
    from modules.network.infra.services.binding_compatibility import (
        install_legacy_version_binding_compatibility,
    )
    from modules.network.infra.services.binding_concurrency import (
        install_binding_concurrency_guards,
    )
    from modules.network.infra.services.binding_runtime import (
        install_pinned_release_runtime_support,
    )
    from modules.network.infra.services.binding_service import (
        ExplicitBindingNetworkService,
        install_explicit_binding_service,
    )
    from modules.network.infra.services.release_atomic import (
        install_atomic_network_promotion,
    )
    from modules.network.infra.services.release_environment_separation import (
        install_detached_network_agent_releases,
    )
    from modules.network.infra.services.release_equivalent_binding_fix import (
        install_equivalent_binding_result_fix,
    )
    from modules.network.infra.services.release_lifecycle import (
        install_network_release_lifecycle,
    )
    from modules.network.infra.services.service import NetworkApplicationService
    from modules.network.infra.services.session_mode_runtime_guard import (
        install_runtime_session_mode_guards,
    )

    install_explicit_binding_service()
    NetworkApplicationService._same_agent_snapshot = staticmethod(  # type: ignore[attr-defined]
        ExplicitBindingNetworkService._same_agent_snapshot
    )
    NetworkApplicationService._snapshot_hash = staticmethod(  # type: ignore[attr-defined]
        ExplicitBindingNetworkService._snapshot_hash
    )
    install_legacy_version_binding_compatibility()
    install_binding_concurrency_guards()
    install_pinned_release_runtime_support()
    install_network_release_lifecycle()
    NetworkApplicationService._network_release_base_plan = staticmethod(  # type: ignore[attr-defined]
        NetworkApplicationService._network_release_base_plan  # type: ignore[attr-defined]
    )
    install_atomic_network_promotion()
    install_detached_network_agent_releases()
    install_equivalent_binding_result_fix()
    install_structured_output_persistence()
    install_runtime_session_mode_guards()
    _installed = True


__all__ = ["install_network_service_extensions"]
