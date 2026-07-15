"""Network bounded context."""

# Install database model extensions before application services import the
# additional mapped columns and Production activation model.
from modules.network.infra.database import schema_extensions as _schema_extensions  # noqa: F401

from modules.network.application.binding_compatibility import install_legacy_version_binding_compatibility
from modules.network.application.binding_concurrency import install_binding_concurrency_guards
from modules.network.application.binding_runtime import install_pinned_release_runtime_support
from modules.network.application.binding_service import ExplicitBindingNetworkService, install_explicit_binding_service
from modules.network.application.release_lifecycle import install_network_release_lifecycle
from modules.network.application.service import NetworkApplicationService
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
install_structured_output_persistence()
