"""Long-lived Identity service factories for process hosts."""

from modules.identity.infra.services.authentication_service import AuthenticationService
from modules.identity.infra.services.instance_service import InstanceService
from modules.identity.composition.resources import DATABASE_ENGINE, SETTINGS
from shared.composition_resources import SESSION_FACTORY
from shared.security.access_tokens import AccessTokenCodec
from shared.security.workspace_access import WorkspaceAccessService


def build_access_token_codec() -> AccessTokenCodec:
    return AccessTokenCodec(
        signing_key=SETTINGS.secret_key,
        issuer=SETTINGS.auth_issuer,
        audience=SETTINGS.auth_audience,
        ttl_seconds=SETTINGS.access_token_ttl_seconds,
        leeway_seconds=SETTINGS.auth_clock_skew_seconds,
    )


def build_authentication_service() -> AuthenticationService:
    return AuthenticationService(
        DATABASE_ENGINE,
        build_access_token_codec(),
        SETTINGS,
    )


def build_instance_service() -> InstanceService:
    return InstanceService(
        DATABASE_ENGINE,
        build_access_token_codec(),
        SETTINGS,
    )


def build_workspace_access_service() -> WorkspaceAccessService:
    return WorkspaceAccessService(SESSION_FACTORY)


__all__ = [
    "build_access_token_codec",
    "build_authentication_service",
    "build_instance_service",
    "build_workspace_access_service",
]
