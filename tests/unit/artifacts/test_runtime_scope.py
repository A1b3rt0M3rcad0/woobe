import pytest

from modules.artifacts.application.contracts.api import SourceReference
from modules.artifacts.application.contracts.representations import SourceReadDefinition, SourceReadView
from modules.artifacts.application.runtime_scope import RunArtifactContext
from modules.artifacts.domain.models import Action, ArtifactError, Environment, RuntimeArtifactBinding, Scope


def test_run_artifact_requests_are_pinned_to_acceptance_and_exact_outputs():
    binding = RuntimeArtifactBinding(
        workspace_id='workspace-runtime', scope=Scope('project-runtime', Environment.STAGING),
        catalog_version=42, actions=frozenset({Action.READ, Action.SEARCH}), binding_scope='session',
    )
    context = RunArtifactContext('principal', binding, 'run-runtime', output_node_ids=frozenset({'node-a'}))

    assert context.list_files(limit=7).catalog_version == 42
    search = context.search('chapter')
    assert search.catalog_version == 42 and search.run_id == 'run-runtime'
    read = context.read_file('artifact-runtime', 'revision-runtime')
    assert read.catalog_version == 42 and read.run_id == 'run-runtime'
    assert read.output_node_ids == frozenset({'node-a'})
    output = context.read_output('artifact-output', 'revision-output')
    assert output.catalog_version == 42 and output.run_id == 'run-runtime'
    assert output.output_node_ids == frozenset({'node-a'})

    source = SourceReference(
        artifact_id='artifact-runtime', revision_id='revision-runtime', source_sha256='a' * 64,
    )
    source_request = context.read_source(SourceReadDefinition(source=source))
    assert source_request.run_id == 'run-runtime'
    assert source_request.catalog_version == 42


def test_run_artifact_context_cannot_expand_missing_capabilities():
    binding = RuntimeArtifactBinding(
        workspace_id='workspace-search-only', scope=Scope('project-runtime', Environment.STAGING),
        catalog_version=2, actions=frozenset({Action.SEARCH}), binding_scope='run',
    )
    context = RunArtifactContext('principal', binding, 'run-runtime')
    assert context.search('chapter').catalog_version == 2
    with pytest.raises(ArtifactError) as denied:
        context.list_files()
    assert denied.value.code == 'ARTIFACT_ACCESS_DENIED'
    with pytest.raises(ValueError):
        RunArtifactContext('principal', binding, '../caller')


def test_transfer_requires_both_transfer_and_current_read_capabilities():
    scope = Scope('project-runtime', Environment.STAGING)
    read_only = RuntimeArtifactBinding(
        workspace_id='workspace-read-only', scope=scope, catalog_version=5,
        actions=frozenset({Action.READ}), binding_scope='run',
    )
    with pytest.raises(ArtifactError):
        RunArtifactContext('principal', read_only, 'run-transfer').transfer_file(
            'artifact-file', 'revision-file',
        )

    transfer_only = RuntimeArtifactBinding(
        workspace_id='workspace-transfer-only', scope=scope, catalog_version=5,
        actions=frozenset({Action.TRANSFER}), binding_scope='run',
    )
    with pytest.raises(ArtifactError):
        RunArtifactContext('principal', transfer_only, 'run-transfer').transfer_file(
            'artifact-file', 'revision-file',
        )

    authorized = RuntimeArtifactBinding(
        workspace_id='workspace-transfer', scope=scope, catalog_version=5,
        actions=frozenset({Action.READ, Action.TRANSFER}), binding_scope='run',
    )
    request = RunArtifactContext('principal', authorized, 'run-transfer').transfer_file(
        'artifact-file', 'revision-file',
    )
    assert request.artifact_id == 'artifact-file'
    assert request.revision_id == 'revision-file'
    assert request.catalog_version == 5


@pytest.mark.asyncio
async def test_source_reads_record_only_the_exact_reference_that_was_returned():
    from modules.artifacts.application.services.representations import RepresentationService

    binding = RuntimeArtifactBinding(
        workspace_id='workspace-source', scope=Scope('project-runtime', Environment.STAGING),
        catalog_version=9, actions=frozenset({Action.READ}), binding_scope='run',
    )
    source = SourceReference(artifact_id='artifact-source', revision_id='revision-source',
        source_sha256='c' * 64)
    definition = SourceReadDefinition(source=source)
    request = RunArtifactContext('principal', binding, 'run-source').read_source(definition)
    result = SourceReadView(source=source, text='used text', offset=0, next_offset=None,
        truncated=False, coverage='complete', page_label=None)
    recorded = []

    async def record(*args):
        recorded.append(args)

    service = RepresentationService(None, None, None, None, record_source_use=record)

    async def read(_request):
        return result

    service._read_source = read
    assert await service.read_source(request) == result
    assert len(recorded) == 1
    assert recorded[0] == (binding.scope, binding.workspace_id, 'run-source', 9, source)
