"""Build a sealed, immutable publication plan; readiness belongs to job commit."""
from collections import deque
from dataclasses import asdict
import hashlib
import json
from uuid import NAMESPACE_URL, uuid5

from modules.artifacts.application.contracts.representations import BundlePhase, RecordProcessingObject, ReserveProcessingObject
from modules.artifacts.application.document_codec import decode_canonical, json_chunks, serialized_identity
from modules.artifacts.domain.models import ArtifactError
from shared.contracts.object_storage import read_bounded


def identity(generation, kind, value):
    return str(uuid5(NAMESPACE_URL, f'woobe:bundle:v1:{generation}:{kind}:{value}'))


def object_identity(workspace, key):
    return str(uuid5(NAMESPACE_URL, f'woobe:processing-object:v1:{workspace}:{key}'))


def parent_first_blocks(items):
    # Each metadata batch commits independently. A deferred parent FK must
    # therefore already resolve when that batch ends, including forward parents.
    by_id = {item['block_id']: item for item in items}
    children = {}
    ready = deque()
    for item in items:
        parent = item['parent_block_id']
        if parent is None:
            ready.append(item)
        elif parent not in by_id:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Canonical source parent is unavailable')
        else:
            children.setdefault(parent, []).append(item)
    result = []
    while ready:
        item = ready.popleft()
        result.append(item)
        ready.extend(children.get(item['block_id'], ()))
    if len(result) != len(items):
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Canonical source parent graph is cyclic')
    return result


async def put_output(context, key, chunks, size, digest, content_type, role):
    declaration = ReserveProcessingObject(context.lease, key, size, digest, content_type, role)
    if context.publication_phase is not None:
        await context.publication_phase('reserve_output', declaration)
    await context.reauthorize()
    metadata = await context.storage.put(key, chunks, size_bytes=size, sha256=digest, content_type=content_type)
    if context.publication_phase is not None:
        await context.publication_phase('record_output', RecordProcessingObject(declaration, metadata))
    return metadata


async def verified_read(context, receipt, maximum):
    metadata = await context.storage.stat(receipt['key'])
    if (metadata.sha256, metadata.size_bytes, metadata.version_id) != (
            receipt['sha256'], receipt['size_bytes'], receipt['version_id']):
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation object metadata changed')
    content = await read_bounded(context.storage, receipt['key'], max_bytes=maximum)
    if len(content) != receipt['size_bytes'] or hashlib.sha256(content).hexdigest() != receipt['sha256']:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation object content changed')
    return content


async def build_bundle(context):
    plan = context.transient['bundle']
    if plan.get('reused') or plan.get('sealed'):
        return plan
    generation, workspace = plan['representation_set_id'], context.lease.workspace_id
    extracted = context.checkpoints['extract']
    maximum = min(536_870_912, context.lease.recipe.limits.max_bytes * 16 + 1_048_576)
    document = decode_canonical(await verified_read(context, extracted, maximum))
    if document.revision.artifact_id != context.source.artifact_id or document.revision.revision_id != context.source.id:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Canonical representation source differs')
    prefix = (f'projects/{context.lease.scope.project_id}/environments/{context.lease.scope.environment.value}/'
              f'artifact-workspaces/{workspace}/processing/{context.lease.id}/attempts/{context.lease.fencing_token}/')
    entries, blocks, segments = [], [], []
    receipts = {}

    def entry(path, role, receipt, *, visible=True, asset_id=None):
        item = {'id': identity(generation, 'entry', path), 'workspace_id': workspace,
                'representation_set_id': generation, 'object_id': object_identity(workspace, receipt['key']),
                'path': path, 'role': role, 'visible': visible, 'asset_id': asset_id}
        receipts[item['object_id']] = receipt
        entries.append(item)
        return item

    async def output(path, role, value, *, content_type='application/json', visible=True):
        size, digest = serialized_identity(value, maximum)
        key = prefix + role + '-' + digest + '.json'
        async def chunks():
            for chunk in json_chunks(value):
                yield chunk
        metadata = await put_output(context, key, chunks(), size, digest, content_type, role)
        receipt = {'key': key, 'size_bytes': size, 'sha256': digest, 'version_id': metadata.version_id}
        entry(path, role, receipt, visible=visible)
        return receipt

    entry('structure.json', 'structure', extracted)
    assets = {}
    if extracted.get('asset_manifest'):
        receipt = extracted['asset_manifest']
        asset_value = json.loads(await verified_read(context, receipt, 4_194_304))
        assets = {item['asset']['id']: item for item in asset_value['assets']}
        if len(assets) != len(asset_value['assets']):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Repeated visual asset in manifest')
        entry('_internal/assets.json', 'asset_manifest', receipt, visible=False)
    if set(assets) != {asset.id for asset in document.assets}:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Visual asset manifest is incomplete')
    for asset in document.assets:
        value = assets[asset.id]
        if value['asset'] != json.loads(json.dumps(asdict(asset))):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Visual asset declaration differs')
        metadata = await context.storage.stat(value['key'])
        if (metadata.sha256, metadata.size_bytes, metadata.content_type, metadata.version_id) != (
                asset.sha256, asset.size_bytes, asset.content_type, value['version_id']):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Visual asset is unavailable or changed')
        entry(f'figures/{asset.id}.png', 'figure', {**value, 'size_bytes': asset.size_bytes, 'sha256': asset.sha256}, asset_id=asset.id)
    for block in document.blocks:
        if block.kind == 'figure' and not block.asset_ids:
            raise ArtifactError('REPRESENTATION_NOT_READY', 'Figure has no verified visual asset')

    # Chunk text independently from structure so a bounded SourceRef read never
    # needs to deserialize a whole canonical document.
    group, group_size, group_number, group_rows = [], 0, 0, []
    async def flush_text():
        nonlocal group, group_size, group_number, group_rows
        if not group:
            return
        size, digest = group_size, hashlib.sha256(b''.join(group)).hexdigest()
        key = prefix + f'block-text-{group_number}-{digest}.txt'
        async def chunks():
            for part in group:
                yield part
        stored = await put_output(context, key, chunks(), size, digest, 'text/plain; charset=utf-8', 'block_text')
        receipt = {'key': key, 'size_bytes': size, 'sha256': digest, 'version_id': stored.version_id}
        entry(f'_internal/text-{group_number}.txt', 'block_text', receipt, visible=False)
        object_id = object_identity(workspace, key)
        for block in group_rows:
            block['object_id'] = object_id
        group, group_size, group_number, group_rows = [], 0, group_number + 1, []

    source_map, outline = [], []
    markdown = []
    for ordinal, block in enumerate(document.blocks):
        encoded = block.text.encode('utf-8')
        if group_size and group_size + len(encoded) > 262_144:
            await flush_text()
        start = group_size
        group.append(encoded)
        group_size += len(encoded)
        locator = asdict(block.locator)
        row = {'id': identity(generation, 'block', block.id), 'workspace_id': workspace,
               'representation_set_id': generation, 'block_id': block.id, 'ordinal': ordinal,
               'kind': block.kind, 'parent_block_id': block.parent_id, 'source_locator': locator,
               'extraction_method': block.extraction_method, 'inferred': block.inferred,
               'asset_ids': list(block.asset_ids), 'object_id': f'pending-{group_number}',
               'byte_start': start, 'byte_end': group_size, 'char_length': len(block.text),
               'sha256': hashlib.sha256(encoded).hexdigest()}
        blocks.append(row)
        group_rows.append(row)
        byte_offset = start
        for offset in range(0, len(block.text), 4096):
            segment = block.text[offset:offset + 4096].encode('utf-8')
            segments.append({'id': identity(generation, 'segment', f'{block.id}:{offset}'),
                'workspace_id': workspace, 'representation_set_id': generation, 'block_id': block.id,
                'char_start': offset, 'char_end': min(len(block.text), offset + 4096),
                'byte_start': byte_offset, 'byte_end': byte_offset + len(segment),
                'sha256': hashlib.sha256(segment).hexdigest()})
            byte_offset += len(segment)
        ref = {'artifact_id': context.source.artifact_id, 'revision_id': context.source.id,
            'source_sha256': context.source.sha256, 'representation_set_id': generation,
            'locator': {**locator, 'block_id': block.id}, 'excerpt_sha256': row['sha256']}
        source_map.append({'block_id': block.id, 'source': ref, 'inferred': block.inferred,
                           'extraction_method': block.extraction_method, 'asset_ids': list(block.asset_ids)})
        if block.kind == 'heading':
            outline.append({'block_id': block.id, 'title': block.text, 'level': block.heading_level, 'source': ref})
            markdown.append('#' * (block.heading_level or 1) + ' ' + block.text)
        elif block.kind == 'figure':
            markdown.extend(f'![Figure](figures/{asset}.png)' for asset in block.asset_ids)
        else:
            markdown.append(block.text)
        if block.kind == 'table':
            await output(f'tables/{block.id}.json', 'table', {'block_id': block.id, 'text': block.text,
                'data_json': block.data_json, 'source': ref, 'inferred': block.inferred})
    await flush_text()
    await output('source-map.json', 'source_map', {'schema_version': '1', 'sources': source_map})
    await output('outline.json', 'outline', {'schema_version': '1', 'headings': outline,
        'pages': [asdict(page) for page in document.pages]})
    # Markdown is a derived untrusted download; HTML is never rendered here.
    text = '\n\n'.join(markdown).encode('utf-8')
    digest = hashlib.sha256(text).hexdigest()
    async def markdown_chunks():
        for offset in range(0, len(text), 65_536):
            yield text[offset:offset + 65_536]
    metadata = await put_output(context, prefix + 'markdown-' + digest + '.md', markdown_chunks(),
                                len(text), digest, 'text/markdown; charset=utf-8', 'markdown')
    entry('document.md', 'markdown', {'key': metadata.key, 'size_bytes': metadata.size_bytes,
        'sha256': metadata.sha256, 'version_id': metadata.version_id})
    metadata_value = {kind: sorted(items, key=lambda item: item['id'])
                      for kind, items in (('entries', entries), ('blocks', blocks), ('segments', segments))}
    _, metadata_digest = serialized_identity(metadata_value, maximum * 4)
    for kind, items in metadata_value.items():
        if kind == 'blocks':
            items = parent_first_blocks(items)
        for offset in range(0, len(items), 100):
            await context.publication_phase('metadata_bundle', BundlePhase(context.lease, generation,
                {'kind': kind, 'items': items[offset:offset + 100]}))
    # Verify all bytes before sealing. Storage I/O remains outside SQL phases.
    for receipt in receipts.values():
        await context.reauthorize()
        actual = await context.storage.stat(receipt['key'])
        if (actual.sha256, actual.size_bytes, actual.version_id) != (
                receipt['sha256'], receipt['size_bytes'], receipt['version_id']):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation object receipt differs before sealing')
        stream = context.storage.open(receipt['key'])
        digest, size = hashlib.sha256(), 0
        try:
            async for chunk in stream:
                size += len(chunk)
                if size > receipt['size_bytes']:
                    raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation object exceeds its receipt')
                digest.update(chunk)
        finally:
            await stream.aclose()
        if size != receipt['size_bytes'] or digest.hexdigest() != receipt['sha256']:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Representation object bytes differ before sealing')
    public_entries = []
    for item in entries:
        # Receipts in the public manifest contain neither storage keys nor backend versions.
        if item['visible']:
            receipt = receipts[item['object_id']]
            public_entries.append({**{name: item[name] for name in ('id', 'path', 'role', 'asset_id')},
                'sha256': receipt['sha256'], 'size_bytes': receipt['size_bytes']})
    manifest = {'schema_version': '1', 'representation_set_id': generation,
        'artifact_id': context.source.artifact_id, 'revision_id': context.source.id,
        'source_sha256': context.source.sha256, 'coverage': document.coverage.value,
        'metadata_fingerprint': metadata_digest, 'entries': public_entries,
        'block_count': len(blocks), 'segment_count': len(segments), 'page_count': document.page_count or 0}
    # The manifest is not an entry in its own recursive manifest.
    size, digest = serialized_identity(manifest, maximum)
    key = prefix + 'manifest-' + digest + '.json'
    async def manifest_chunks():
        for chunk in json_chunks(manifest):
            yield chunk
    await put_output(context, key, manifest_chunks(), size, digest, 'application/json', 'manifest')
    return await context.publication_phase('seal_bundle', BundlePhase(context.lease, generation,
        {'manifest_object_id': object_identity(workspace, key), 'manifest_sha256': digest,
         'metadata_fingerprint': metadata_digest, 'entry_count': len(entries), 'block_count': len(blocks),
         'segment_count': len(segments), 'page_count': document.page_count or 0,
         'pages': [asdict(page) for page in document.pages], 'coverage': document.coverage.value,
         'diagnostics': list(document.diagnostics)}))
