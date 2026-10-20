"""Host-facing capability boundary for Artifacts."""

from modules.artifacts.composition.public_api import (
    CONTRACT_VERSION as CONTRACT_VERSION,
    ArtifactError as ArtifactError,
    ArtifactReference as ArtifactReference,
    CapabilityDescriptor as CapabilityDescriptor,
    ErrorEnvelope as ErrorEnvelope,
    SourceReference as SourceReference,
    UploadCreate as UploadCreate,
    WorkspaceCreate as WorkspaceCreate,
    WorkspaceUpdate as WorkspaceUpdate,
)

from modules.artifacts.composition.public_api import create_workspace_composer as create_workspace_composer

from modules.artifacts.composition.public_api import get_workspace_composer as get_workspace_composer

from modules.artifacts.composition.public_api import resolve_workspace_composer as resolve_workspace_composer

from modules.artifacts.composition.public_api import list_workspaces_composer as list_workspaces_composer

from modules.artifacts.composition.public_api import update_workspace_composer as update_workspace_composer

from modules.artifacts.composition.public_api import create_workspace_grant_composer as create_workspace_grant_composer

from modules.artifacts.composition.public_api import revoke_workspace_grant_composer as revoke_workspace_grant_composer

from modules.artifacts.composition.public_api import CreateWorkspace as CreateWorkspace

from modules.artifacts.composition.public_api import ReadWorkspace as ReadWorkspace

from modules.artifacts.composition.public_api import ResolveWorkspace as ResolveWorkspace

from modules.artifacts.composition.public_api import ListWorkspaces as ListWorkspaces

from modules.artifacts.composition.public_api import ChangeWorkspace as ChangeWorkspace

from modules.artifacts.composition.public_api import CreateWorkspaceGrant as CreateWorkspaceGrant

from modules.artifacts.composition.public_api import RevokeWorkspaceGrant as RevokeWorkspaceGrant

from modules.artifacts.composition.public_api import (
    build_upload_service as build_upload_service, BeginUpload as BeginUpload,
    UploadRequest as UploadRequest, UploadPart as UploadPart, UploadView as UploadView,
)

from modules.artifacts.composition.public_api import (
    build_file_service as build_file_service, ReadFile as ReadFile, CopyFile as CopyFile, ListFiles as ListFiles,
    MutateFile as MutateFile, WriteText as WriteText,
)

from modules.artifacts.composition.public_api import Scope as Scope, Environment as Environment, Action as Action

from modules.artifacts.composition.public_api import (
    WorkspaceView as WorkspaceView, ArtifactView as ArtifactView, RevisionView as RevisionView,
    UploadStatusView as UploadStatusView, WorkspacePage as WorkspacePage, ArtifactPage as ArtifactPage,
)
