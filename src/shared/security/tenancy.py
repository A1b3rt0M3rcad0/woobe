"""Project tenancy authorization for Woobe Instance/Workspace boundaries."""

from shared.security.workspace_tenancy import (
    DIRECT_PROJECT_RESOURCES,
    INDIRECT_PROJECT_RESOURCE_QUERIES,
    TenantAuthorizer,
)

__all__ = [
    "DIRECT_PROJECT_RESOURCES",
    "INDIRECT_PROJECT_RESOURCE_QUERIES",
    "TenantAuthorizer",
]
