"""Network bounded context."""

from modules.network.application.binding_runtime import install_pinned_release_runtime_support
from modules.network.application.binding_service import install_explicit_binding_service

install_explicit_binding_service()
install_pinned_release_runtime_support()
