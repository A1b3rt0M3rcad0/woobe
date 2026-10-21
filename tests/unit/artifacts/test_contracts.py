from dataclasses import FrozenInstanceError
import importlib
import json
from pathlib import Path
import sys

import jsonschema
import pytest
from pydantic import ValidationError

from modules.artifacts.application.contracts.api import SourceReference, UploadCreate, WorkspaceCreate
from modules.artifacts.domain.models import (
    ArtifactRef, CanonicalDocument, Coverage, DocumentIndex, DocumentNode,
    Locator, Page, Scope, SourceRef, Workspace, logical_path,
    Action, UploadIntent, WorkspaceGrant,
)


ROOT = Path(__file__).resolve().parents[3]


def test_committed_wire_schemas_match_all_canonical_contracts():
    from scripts.generate_artifact_schemas import generate
    generate(check=True)


@pytest.mark.parametrize('path', ['', '/etc/passwd', '../secret', 'a/../b',
                                  'a//b', 'a\\b', 'a\x00b', 'e\u0301.txt', 'a/'])
def test_ambiguous_logical_paths_are_rejected(path):
    with pytest.raises(ValueError):
        logical_path(path)


def test_valid_references_are_immutable_and_identifiers_are_not_host_paths():
    ref = ArtifactRef('artifact-1', 'revision-1')
    with pytest.raises(FrozenInstanceError):
        ref.revision_id = 'changed'
    with pytest.raises(ValueError):
        ArtifactRef('../other', 'revision-1')
    assert logical_path('chapter/ação.md') == 'chapter/ação.md'


def test_workspace_does_not_depend_on_session_and_quota_is_coherent():
    ws = Workspace('workspace-1', Scope('project-1', 'draft'), 'app', 'external', 'Files')
    assert ws.catalog_version == 0 and ws.scope.environment == 'draft'
    with pytest.raises(ValueError):
        Workspace('workspace-1', ws.scope, 'app', 'external', 'Files', quota_bytes=1, used_bytes=2)


def test_source_locator_and_exact_representation_generation_are_required():
    ref = SourceRef('artifact-1', 'revision-1', 'a' * 64, locator=Locator(page_index=0, page_number=1))
    assert ref.locator.page_number == 1
    for kwargs in [{'page_index': -1}, {'page_number': 1}, {'page_index': 0, 'page_number': 2},
                   {'line_start': 2, 'line_end': 1}, {'bbox': (0, 0, 1, 1)}]:
        with pytest.raises(ValueError):
            Locator(**kwargs)
    with pytest.raises(ValueError):
        SourceRef('artifact-1', 'revision-1', 'a' * 64, node_id='node-1')


def test_index_rejects_cycles_and_absent_parents_and_false_complete_extraction():
    for nodes in [(DocumentNode('a', 'A', (), 'missing'),),
                  (DocumentNode('a', 'A', (), 'b'), DocumentNode('b', 'B', (), 'a'))]:
        with pytest.raises(ValueError):
            DocumentIndex('index-1', 'set-1', 'structural', '1', nodes)
    with pytest.raises(ValueError):
        CanonicalDocument(ArtifactRef('a', 'r'), (), Coverage.COMPLETE)
    with pytest.raises(ValueError):
        Page((), has_more=True)


def test_canonical_schemas_and_cross_language_fixtures():
    directory = ROOT / 'contracts/artifacts/v1'
    for filename in ('workspace-create', 'upload-create', 'source-reference'):
        schema = json.loads((directory / f'{filename}.schema.json').read_text())
        fixtures = json.loads((directory / f'{filename}.fixtures.json').read_text())
        validator = jsonschema.Draft202012Validator(schema)
        for value in fixtures['valid']:
            validator.validate(value)
        for value in fixtures['invalid']:
            assert list(validator.iter_errors(value)), value


def test_dtos_reject_semantically_invalid_combinations_and_unknown_versions():
    with pytest.raises(ValidationError):
        WorkspaceCreate(environment='draft', external_namespace='app', external_key='x', name='X', schema_version='2')
    with pytest.raises(ValidationError):
        UploadCreate(operation_id='op', path='a', size_bytes=1, sha256='a' * 64,
                     content_type='text/plain', artifact_id='a')
    with pytest.raises(ValidationError):
        SourceReference(artifact_id='a', revision_id='r', source_sha256='a' * 64,
                        document_index_id='i')


def test_public_import_has_no_optional_processing_framework_side_effect():
    before = set(sys.modules)
    module = importlib.import_module('modules.artifacts.entrypoint')
    assert module.CONTRACT_VERSION == '1'
    assert not ({'docling', 'pageindex', 'torch', 'fastapi'} & (set(sys.modules) - before))


def test_grants_require_one_selector_and_committed_uploads_require_receipts():
    scope = Scope('project', 'draft')
    with pytest.raises(ValueError):
        WorkspaceGrant('grant', 'principal', scope, frozenset({Action.READ}))
    grant = WorkspaceGrant('grant', 'principal', scope, frozenset({Action.READ}), workspace_id='ws')
    assert grant.actions == frozenset({Action.READ})
    with pytest.raises(ValueError):
        UploadIntent('intent', 'ws', 'operation', 'a' * 64, 12, 'b' * 64,
                     'text/plain', offset=13)
    with pytest.raises(ValueError):
        UploadIntent('intent', 'ws', 'operation', 'a' * 64, 12, 'b' * 64,
                     'text/plain', status='committed')
