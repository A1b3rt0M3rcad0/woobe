"""Generate the public version 1 Artifacts DTO schemas from canonical contracts."""

import argparse
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


from modules.artifacts.application.contracts.representations import (  # noqa: E402
    RepresentationSetView, RepresentationEntryView, RepresentationEntryPage,
    SourceReadDefinition, SourceReadView, SourceResolveBatchDefinition, SourceResolveBatchView,
    CopyRepresentationDefinition,
)


from modules.artifacts.application.contracts.indexes import DocumentIndexView, DocumentNodeView, DocumentNodePage  # noqa: E402
from modules.artifacts.application.contracts.search import ArtifactSearchPage  # noqa: E402


def generate(*, check=False):
    destination = ROOT / 'contracts/artifacts/v1'
    if not check:
        destination.mkdir(parents=True, exist_ok=True)
    for filename, model in {
        'document-index': DocumentIndexView,
        'search-page': ArtifactSearchPage,
        'document-node': DocumentNodeView,
        'document-node-page': DocumentNodePage,
        'representation-set': RepresentationSetView,
        'representation-entry': RepresentationEntryView,
        'representation-entry-page': RepresentationEntryPage,
        'source-read': SourceReadDefinition,
        'source-read-result': SourceReadView,
        'source-resolve': SourceResolveBatchDefinition,
        'source-resolve-result': SourceResolveBatchView,
        'representation-copy': CopyRepresentationDefinition,
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
        target = destination / f'{filename}.schema.json'
        expected = json.dumps(schema, indent=2, sort_keys=True) + '\n'
        if check:
            if not target.is_file() or target.read_text() != expected:
                raise ValueError(f'Committed Artifacts schema is stale: {filename}')
        else:
            target.write_text(expected)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify committed schemas without changing files')
    generate(check=parser.parse_args().check)
