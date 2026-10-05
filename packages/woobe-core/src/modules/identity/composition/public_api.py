"""Explicit transport-neutral public surface for Identity hosts."""

from modules.identity.infra.services.authentication_service import AuthenticationService
from modules.identity.application.dtos import (
    CreateWorkspaceInput,
    LoginInput,
    RegisterInput,
)
from modules.identity.infra.services.instance_service import InstanceService
from modules.identity.composition.services import (
    build_authority_service,
    build_access_token_codec,
    build_authentication_service,
    build_instance_service,
    build_workspace_access_service,
)
from modules.identity.composition.composers.get_user_composer import get_user_composer
from modules.identity.composition.composers.get_workspace_composer import (
    get_workspace_composer,
)
from modules.identity.composition.composers.update_workspace_composer import (
    update_workspace_composer,
)
from modules.identity.domain.enums import MemberRole

__all__ = [
    "build_authority_service",
    "AuthenticationService",
    "CreateWorkspaceInput",
    "InstanceService",
    "build_access_token_codec",
    "build_authentication_service",
    "build_instance_service",
    "build_workspace_access_service",
    "LoginInput",
    "MemberRole",
    "RegisterInput",
    "get_user_composer",
    "get_workspace_composer",
    "update_workspace_composer",
]
