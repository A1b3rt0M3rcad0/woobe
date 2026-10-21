"""Inferred summaries cite server-constructed exact canonical source intervals."""
from dataclasses import asdict
import hashlib

from modules.artifacts.application.contracts.document_models import DocumentModelCall, DocumentModelFragment
from modules.artifacts.application.document_codec import decode_canonical, json_chunks, serialized_identity
from modules.artifacts.application.services.representation_bundle import put_output, verified_read
from modules.artifacts.domain.models import ArtifactError


async def enrich_document(context, gateway):
    plan = context.transient['bundle']
    if plan.get('reused') or plan.get('sealed'):
        return {'reuse_publication': True}
    lease = context.lease
    maximum = min(536_870_912, lease.recipe.limits.max_bytes * 16 + 1_048_576)
    document = decode_canonical(await verified_read(context, context.checkpoints['extract'], maximum))
    if (document.revision.artifact_id, document.revision.revision_id) != (context.source.artifact_id, context.source.id):
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Model enrichment canonical source differs')
    fragments, complete = [], True
    nonempty = [block for block in document.blocks if block.text.strip()]
    for block in nonempty:
        if len(fragments) == 8:
            complete = False
            break
        start = next(index for index, character in enumerate(block.text) if not character.isspace())
        text = block.text[start:start + 512]
        complete = complete and start == 0 and len(text) == len(block.text)
        locator = {**asdict(block.locator), 'block_id': block.id,
            'char_space': 'canonical_block_text', 'char_start': start, 'char_end': start + len(text)}
        fragments.append(DocumentModelFragment(id=block.id, text=text, source={
            'artifact_id': context.source.artifact_id, 'revision_id': context.source.id,
            'source_sha256': context.source.sha256, 'representation_set_id': plan['representation_set_id'],
            'locator': locator, 'excerpt_sha256': hashlib.sha256(text.encode()).hexdigest()}))
    if not fragments:
        raise ArtifactError('MODEL_OUTPUT_INVALID', 'No verified textual source is available for model enrichment')
    response = await gateway.invoke(DocumentModelCall(lease, 'summary-v1', 'summarize', tuple(fragments),
        min(4096, lease.recipe.limits.max_output_tokens), min(60, lease.recipe.limits.timeout_seconds)))
    sources = {fragment.id: fragment.source.model_dump(mode='json') for fragment in fragments}
    value = {'schema_version': '1', 'inferred': True, 'trust': 'untrusted_model_derivative',
        'source_sha256': context.source.sha256, 'representation_set_id': plan['representation_set_id'],
        'binding_fingerprint': response.binding_fingerprint,
        'coverage': 'complete' if complete else 'partial', 'source_block_count': len(nonempty),
        'included_block_count': len(fragments), 'summaries': [
            {'text': summary.text, 'inferred': True, 'sources': [sources[name] for name in summary.fragment_ids]}
            for summary in response.output.summaries]}
    size, digest = serialized_identity(value, 262144)
    key = (f'projects/{lease.scope.project_id}/environments/{lease.scope.environment.value}/'
        f'artifact-workspaces/{lease.workspace_id}/processing/{lease.id}/attempts/{lease.fencing_token}/summary-{digest}.json')
    async def chunks():
        for chunk in json_chunks(value):
            yield chunk
    metadata = await put_output(context, key, chunks(), size, digest, 'application/json', 'summary')
    return {'key': key, 'sha256': digest, 'size_bytes': size, 'version_id': metadata.version_id,
        'inferred': True, 'coverage': value['coverage'], 'binding_fingerprint': response.binding_fingerprint}
