"""Explicit public Artifacts types; concrete wiring is added with capabilities."""

from modules.artifacts.application.contracts.api import (
    ArtifactReference as ArtifactReference,
    CapabilityDescriptor as CapabilityDescriptor,
    ErrorEnvelope as ErrorEnvelope,
    SourceReference as SourceReference,
    UploadCreate as UploadCreate,
    WorkspaceCreate as WorkspaceCreate,
    WorkspaceUpdate as WorkspaceUpdate,
)
from modules.artifacts.domain.models import ArtifactError as ArtifactError


from modules.artifacts.composition.composers.create_workspace import create_workspace_composer as create_workspace_composer

from modules.artifacts.composition.composers.get_workspace import get_workspace_composer as get_workspace_composer

from modules.artifacts.composition.composers.resolve_workspace import resolve_workspace_composer as resolve_workspace_composer

from modules.artifacts.composition.composers.list_workspaces import list_workspaces_composer as list_workspaces_composer

from modules.artifacts.composition.composers.update_workspace import update_workspace_composer as update_workspace_composer

from modules.artifacts.composition.composers.create_workspace_grant import create_workspace_grant_composer as create_workspace_grant_composer

from modules.artifacts.composition.composers.revoke_workspace_grant import revoke_workspace_grant_composer as revoke_workspace_grant_composer

from modules.artifacts.application.contracts.workspaces import CreateWorkspace as CreateWorkspace

from modules.artifacts.application.contracts.workspaces import ReadWorkspace as ReadWorkspace

from modules.artifacts.application.contracts.workspaces import ResolveWorkspace as ResolveWorkspace

from modules.artifacts.application.contracts.workspaces import ListWorkspaces as ListWorkspaces

from modules.artifacts.application.contracts.workspaces import ChangeWorkspace as ChangeWorkspace

from modules.artifacts.application.contracts.workspaces import CreateWorkspaceGrant as CreateWorkspaceGrant

from modules.artifacts.application.contracts.workspaces import RevokeWorkspaceGrant as RevokeWorkspaceGrant


from modules.artifacts.composition.uploads import build_upload_service as build_upload_service
from modules.artifacts.application.contracts.uploads import (
    BeginUpload as BeginUpload, UploadRequest as UploadRequest, UploadPart as UploadPart, UploadView as UploadView,
)

from modules.artifacts.composition.files import build_file_service as build_file_service
from modules.artifacts.application.contracts.files import (
    ReadFile as ReadFile, CopyFile as CopyFile, ListFiles as ListFiles, MutateFile as MutateFile, WriteText as WriteText,
)

CONTRACT_VERSION = '1'
