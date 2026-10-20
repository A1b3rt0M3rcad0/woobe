"""Generate the public version 1 Artifacts DTO schemas from canonical contracts."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/woobe-core/src'))

from modules.artifacts.application.contracts.api import (  # noqa: E402
    ArtifactReference, CapabilityDescriptor, CursorEnvelope, ErrorEnvelope,
    SourceReference, UploadCreate, WorkspaceCreate, WorkspaceUpdate, WorkspaceView,
    ArtifactView, RevisionView, UploadStatusView, WorkspacePage, ArtifactPage,
)

from modules.artifacts.application.contracts.processing import (  # noqa: E402
    ProcessingRecipe, ProfileCreate, ProfileDefault, ProfileView, ProfilePage, ProcessingSelection,
)

from modules.artifacts.application.contracts.jobs import ProcessingRequest, ProcessingJobView  # noqa: E402


def generate():
    destination = ROOT / 'contracts/artifacts/v1'
    destination.mkdir(parents=True, exist_ok=True)
    for filename, model in {
        'artifact-reference': ArtifactReference,
        'source-reference': SourceReference,
        'workspace-create': WorkspaceCreate,
        'workspace-update': WorkspaceUpdate,
        'upload-create': UploadCreate,
        'error': ErrorEnvelope,
        'cursor': CursorEnvelope,
        'capabilities': CapabilityDescriptor,
        'workspace': WorkspaceView,
        'artifact': ArtifactView,
        'revision': RevisionView,
        'upload-status': UploadStatusView,
        'workspace-page': WorkspacePage,
        'artifact-page': ArtifactPage,
        'processing-recipe': ProcessingRecipe,
        'profile-create': ProfileCreate,
        'profile-default': ProfileDefault,
        'profile': ProfileView,
        'profile-page': ProfilePage,
        'processing-selection': ProcessingSelection,
        'processing-request': ProcessingRequest,
        'processing-job': ProcessingJobView,
    }.items():
        schema = model.model_json_schema()
        schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
        schema['$id'] = f'urn:woobe:artifacts:v1:{filename}'
        (destination / f'{filename}.schema.json').write_text(
            json.dumps(schema, indent=2, sort_keys=True) + '\n'
        )


if __name__ == '__main__':
    generate()
