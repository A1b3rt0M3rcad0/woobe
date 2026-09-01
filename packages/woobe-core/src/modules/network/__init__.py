"""Network bounded context."""

# Install database model extensions before application services import the
# additional mapped columns and Production activation model.
from modules.network.infra.database import schema_extensions as _schema_extensions  # noqa: F401

from modules.network.application.binding_compatibility import install_legacy_version_binding_compatibility
from modules.network.application.binding_concurrency import install_binding_concurrency_guards
from modules.network.application.binding_runtime import install_pinned_release_runtime_support
from modules.network.application.binding_service import ExplicitBindingNetworkService, install_explicit_binding_service
from modules.network.application.release_atomic import install_atomic_network_promotion
from modules.network.application.release_environment_separation import install_detached_network_agent_releases
from modules.network.application.release_equivalent_binding_fix import install_equivalent_binding_result_fix
from modules.network.application.release_lifecycle import install_network_release_lifecycle
from modules.network.application.service import NetworkApplicationService
from modules.network.application.session_mode_runtime_guard import install_runtime_session_mode_guards
from modules.network.application.structured_output_persistence import install_structured_output_persistence


install_explicit_binding_service()

# Accessing a staticmethod through ``getattr`` returns its underlying function.
# The installer assigns those functions to NetworkApplicationService, where they
# would otherwise become bound instance methods and receive an unexpected self.
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

# The decorated planner intentionally passes the service instance to the base
# planner. Preserve the original function as a static descriptor so Python does
# not bind a second implicit ``self``.
NetworkApplicationService._network_release_base_plan = staticmethod(  # type: ignore[attr-defined]
    NetworkApplicationService._network_release_base_plan  # type: ignore[attr-defined]
)

install_atomic_network_promotion()
install_detached_network_agent_releases()
install_equivalent_binding_result_fix()
install_structured_output_persistence()
install_runtime_session_mode_guards()
