from collections import Counter
import hashlib

from modules.artifacts.application.contracts.indexes import IndexPhase
from modules.artifacts.application.document_codec import decode_canonical, json_chunks, serialized_identity
from modules.artifacts.application.services.representation_bundle import object_identity, put_output, verified_read
from modules.artifacts.application.services.structural_index import build_structural_index
from modules.artifacts.domain.models import ArtifactError


async def build_index(context, blocking_io, indexers=None):
    bundle = context.checkpoints['build_bundle']
    prepared = await context.publication_phase('prepare_index', IndexPhase(context.lease, bundle['representation_set_id']))
    if prepared.get('sealed') or prepared.get('reused'):
        return {name: prepared[name] for name in ('document_index_id', 'representation_set_id', 'index_manifest_sha256')}
    index_id = prepared['document_index_id']
    maximum = min(536_870_912, context.lease.recipe.limits.max_bytes * 16 + 1_048_576)
    document = context.transient.get('canonical_document')
    if document is None:
        document = decode_canonical(await verified_read(context, prepared['canonical'], maximum))
    if (document.revision.artifact_id, document.revision.revision_id) != (context.source.artifact_id, context.source.id):
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Structural index canonical revision differs')
    selected = context.lease.recipe.indexer
    fallback = context.lease.recipe.parameters.indexer_fallback == 'structural'
    if selected is None:
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Indexed processing requires an indexer')
    if (selected.name, selected.version) == ('structural', '1'):
        tree = await blocking_io(build_structural_index, document, index_id, bundle['representation_set_id'])
    else:
        indexer = (indexers or {}).get((selected.name, selected.version))
        try:
            if indexer is None:
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Selected document indexer is unavailable')
            await context.reauthorize()
            content = context.storage.open(context.source.object_key)
            try:
                tree = await indexer.index(document, index_id=index_id,
                    representation_set_id=bundle['representation_set_id'], profile=context.lease.recipe,
                    revision=context.source, content=content, model=None)
            finally:
                close = getattr(content, 'aclose', None)
                if close is not None:
                    await close()
        except ArtifactError as error:
            fallback_errors = {'PROCESSOR_UNAVAILABLE', 'ARTIFACT_LIMIT_EXCEEDED',
                'PDF_INVALID_DOCUMENT', 'PDF_PASSWORD_REQUIRED'}
            if not fallback or error.code.value not in fallback_errors:
                raise
            tree = await blocking_io(build_structural_index, document, index_id, bundle['representation_set_id'])
    counts = Counter(node.parent_id for node in tree.nodes if node.parent_id is not None)
    nodes = [{'id': node.id, 'workspace_id': context.lease.workspace_id,
        'representation_set_id': tree.representation_set_id, 'document_index_id': tree.id,
        'parent_id': node.parent_id, 'title': node.title, 'kind': node.kind, 'ordinal': node.ordinal,
        'depth': node.depth, 'children_count': counts[node.id],
        'source_ranges': [list(interval) for interval in node.source_ranges],
        'block_id': node.block_ids[0] if node.block_ids else None,
        'block_sha256': node.block_sha256, 'page_index': node.page_index} for node in tree.nodes]
    _, metadata_digest = await blocking_io(serialized_identity, sorted(nodes, key=lambda node: node['id']), 536_870_912)
    # Parent FKs resolve at the end of every short transaction, including when
    # the canonical hierarchy contains forward parent references.
    ordered = sorted(nodes, key=lambda node: (node['depth'], node['ordinal']))
    for offset in range(0, len(ordered), 100):
        await context.publication_phase('metadata_index', IndexPhase(context.lease, tree.representation_set_id,
            tree.id, {'nodes': ordered[offset:offset + 100]}))
    public_nodes = [{name: value for name, value in node.items() if name not in {'workspace_id'}} for node in nodes]
    manifest = {'schema_version': '1', 'document_index_id': tree.id,
        'representation_set_id': tree.representation_set_id, 'artifact_id': context.source.artifact_id,
        'revision_id': context.source.id, 'source_sha256': context.source.sha256,
        'engine': tree.engine, 'engine_version': tree.engine_version, 'tree_kind': tree.tree_kind,
        'coverage': tree.coverage.value, 'source_block_count': tree.source_block_count,
        'metadata_fingerprint': metadata_digest, 'nodes': public_nodes}
    size, digest = await blocking_io(serialized_identity, manifest, maximum)
    lease = context.lease
    key = (f'projects/{lease.scope.project_id}/environments/{lease.scope.environment.value}/'
           f'artifact-workspaces/{lease.workspace_id}/processing/{lease.id}/attempts/{lease.fencing_token}/'
           f'document-index-{digest}.json')
    async def chunks():
        for chunk in json_chunks(manifest):
            yield chunk
    metadata = await put_output(context, key, chunks(), size, digest, 'application/json', 'document_index')
    actual = await context.storage.stat(key)
    if (actual.sha256, actual.size_bytes, actual.version_id) != (digest, size, metadata.version_id):
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document index manifest storage receipt differs')
    stream, verified_size, verified_digest = context.storage.open(key), 0, hashlib.sha256()
    try:
        async for chunk in stream:
            verified_size += len(chunk)
            if verified_size > size:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document index manifest exceeds its declared size')
            verified_digest.update(chunk)
    finally:
        await stream.aclose()
    if verified_size != size or verified_digest.hexdigest() != digest:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Document index manifest bytes differ')
    return await context.publication_phase('seal_index', IndexPhase(lease, tree.representation_set_id, tree.id,
        {'manifest_object_id': object_identity(lease.workspace_id, key), 'manifest_sha256': digest,
         'metadata_fingerprint': metadata_digest, 'node_count': len(nodes),
         'max_depth': max(node.depth for node in tree.nodes), 'tree_kind': tree.tree_kind,
         'engine': tree.engine, 'engine_version': tree.engine_version}))
