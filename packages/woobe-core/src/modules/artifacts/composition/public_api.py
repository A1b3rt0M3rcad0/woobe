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

from modules.artifacts.domain.models import Scope as Scope, Environment as Environment, Action as Action

from modules.artifacts.application.contracts.api import (
    WorkspaceView as WorkspaceView, ArtifactView as ArtifactView, RevisionView as RevisionView,
    UploadStatusView as UploadStatusView, WorkspacePage as WorkspacePage, ArtifactPage as ArtifactPage,
)

from modules.artifacts.application.contracts.processing import (
    ProcessingRecipe as ProcessingRecipe, ProfileCreate as ProfileCreate, ProfileDefault as ProfileDefault, ProfileView as ProfileView,
)
from modules.artifacts.application.contracts.profiles import (
    CreateProcessingProfile as CreateProcessingProfile, ReadProcessingProfile as ReadProcessingProfile,
    ListProcessingProfiles as ListProcessingProfiles, BindProcessingProfile as BindProcessingProfile,
    SelectProcessingProfile as SelectProcessingProfile,
)
from modules.artifacts.composition.composers.create_processing_profile import create_processing_profile_composer as create_processing_profile_composer
from modules.artifacts.composition.composers.get_processing_profile import get_processing_profile_composer as get_processing_profile_composer
from modules.artifacts.composition.composers.list_processing_profiles import list_processing_profiles_composer as list_processing_profiles_composer
from modules.artifacts.composition.composers.bind_processing_profile import bind_processing_profile_composer as bind_processing_profile_composer
from modules.artifacts.composition.composers.select_processing_profile import select_processing_profile_composer as select_processing_profile_composer

from modules.artifacts.application.contracts.processing import ProfilePage as ProfilePage, ProcessingSelection as ProcessingSelection


from modules.artifacts.application.contracts.jobs import (
    ProcessingRequest as ProcessingRequest, ProcessingJobView as ProcessingJobView,
    RequestProcessing as RequestProcessing, ReadProcessingJob as ReadProcessingJob,
)
from modules.artifacts.composition.composers.request_processing import request_processing_composer as request_processing_composer
from modules.artifacts.composition.composers.get_processing_job import get_processing_job_composer as get_processing_job_composer
from modules.artifacts.composition.composers.cancel_processing_job import cancel_processing_job_composer as cancel_processing_job_composer

from modules.artifacts.composition.processing_profiles import processing_component_capabilities as processing_component_capabilities

CONTRACT_VERSION = '1'
