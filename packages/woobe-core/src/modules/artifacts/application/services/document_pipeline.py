from dataclasses import asdict

from modules.artifacts.application.contracts.jobs import ProcessingJobResult
from modules.artifacts.application.contracts.representations import BundlePhase
from modules.artifacts.application.services.representation_bundle import build_bundle, put_output
from modules.artifacts.application.services.index_pipeline import build_index
from modules.artifacts.application.document_codec import canonical_value, json_chunks, serialized_identity
from modules.artifacts.application.ports.processing import ProcessingStage
from modules.artifacts.domain.models import ArtifactError
from shared.contracts.object_storage import ObjectStorageError


class DocumentPipeline:
    def __init__(self, processors, blocking_io):
        self._processors, self._blocking_io = processors, blocking_io

    async def initialize(self, context):
        if context.publication_phase is not None:
            context.transient['bundle'] = await context.publication_phase('prepare_bundle', BundlePhase(context.lease))

    def stages(self, recipe):
        if (recipe.mode not in {'extract', 'extract_index'} or recipe.processor is None or recipe.enricher is not None
            or (recipe.indexer is not None and (recipe.indexer.name, recipe.indexer.version) != ('structural', '1'))):
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Requested document pipeline stages are unavailable')
        processor = self._processors.get((recipe.processor.name, recipe.processor.version))
        if recipe.ocr is not None and not getattr(processor, 'supports_ocr', False):
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Selected document processor does not support selective OCR')
        stages = (ProcessingStage('extract', self._extract), ProcessingStage('build_bundle', self._build_bundle))
        if recipe.mode == 'extract_index':
            stages += (ProcessingStage('build_index', self._build_index),)
        return stages

    async def _extract(self, context):
        bundle = context.transient.get('bundle', {})
        if bundle.get('reused') or bundle.get('sealed'):
            return {'reuse_publication': True, **bundle}
        selected = context.lease.recipe.processor
        processor = self._processors.get((selected.name, selected.version))
        if processor is None:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Selected document processor is unavailable')
        published = {}
        lease = context.lease

        async def publish_asset(asset, chunks):
            if asset.id in published:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Visual asset identity was repeated')
            key = (f'projects/{lease.scope.project_id}/environments/{lease.scope.environment.value}/'
                   f'artifact-workspaces/{lease.workspace_id}/processing/{lease.id}/'
                   f'attempts/{lease.fencing_token}/visual-{asset.id}-{asset.sha256}.png')
            await context.reauthorize()
            metadata = await put_output(context, key, chunks, asset.size_bytes, asset.sha256, asset.content_type, 'figure')
            published[asset.id] = {'asset': asdict(asset), 'key': key, 'version_id': metadata.version_id}

        document = await processor.process(context.source, context.storage.open(context.source.object_key),
            context.lease.recipe, publish_asset=publish_asset)
        if {asset.id: asdict(asset) for asset in document.assets} != {identity: value['asset'] for identity, value in published.items()}:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Canonical document visual assets are incomplete')
        value = canonical_value(document)
        maximum = min(536_870_912, context.lease.recipe.limits.max_bytes * 16 + 1_048_576)
        size, digest = await self._blocking_io(serialized_identity, value, maximum)
        key = (f'projects/{lease.scope.project_id}/environments/{lease.scope.environment.value}/'
               f'artifact-workspaces/{lease.workspace_id}/processing/{lease.id}/'
               f'attempts/{lease.fencing_token}/canonical-{digest}.json')

        async def chunks():
            for chunk in json_chunks(value):
                yield chunk

        await context.reauthorize()
        try:
            metadata = await put_output(context, key, chunks(), size, digest, 'application/json', 'structure')
        except ObjectStorageError as error:
            raise ArtifactError('ARTIFACT_STORAGE_UNAVAILABLE', 'Canonical staging could not be stored', retryable=True) from error
        asset_manifest = None
        if published:
            asset_value = {'schema_version': '1', 'assets': list(published.values())}
            asset_size, asset_digest = await self._blocking_io(serialized_identity, asset_value, 4_194_304)
            asset_key = key.removesuffix('.json') + '-visual-assets.json'
            async def asset_chunks():
                for chunk in json_chunks(asset_value):
                    yield chunk
            await context.reauthorize()
            asset_metadata = await put_output(context, asset_key, asset_chunks(), asset_size, asset_digest, 'application/json', 'asset_manifest')
            asset_manifest = {'key': asset_key, 'sha256': asset_digest, 'size_bytes': asset_size,
                              'version_id': asset_metadata.version_id}
        return {'key': key, 'sha256': metadata.sha256, 'size_bytes': metadata.size_bytes,
                'content_type': metadata.content_type, 'version_id': metadata.version_id,
                'source_sha256': context.source.sha256, 'coverage': document.coverage.value,
                'block_count': len(document.blocks), 'page_count': document.page_count or 0,
                'diagnostics': list(document.diagnostics[:32]),
                'diagnostic_count': len(document.diagnostics), 'canonical_schema_version': '1',
                'asset_count': len(document.assets), 'asset_manifest': asset_manifest}

    async def _build_bundle(self, context):
        if context.publication_phase is None:
            return {'publication_enabled': False}
        return await build_bundle(context)

    async def _build_index(self, context):
        if context.publication_phase is None:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Structural index publication is unavailable')
        return await build_index(context, self._blocking_io)

    def result(self, context):
        canonical = context.checkpoints['extract']
        publication = context.transient.get('bundle', {})
        if not (publication.get('reused') or publication.get('sealed')):
            publication = context.checkpoints.get('build_bundle', {})
        if publication.get('representation_set_id'):
            publication = {**publication, **context.checkpoints.get('build_index', {})}
            context.transient['publication'] = publication
        return ProcessingJobResult(mode=context.lease.recipe.mode, processing_performed=True,
            source_sha256=context.source.sha256, coverage=canonical['coverage'],
            representation_set_id=publication.get('representation_set_id'),
            document_index_id=publication.get('document_index_id'),
            block_count=canonical['block_count'], page_count=canonical['page_count'],
            diagnostics=tuple(canonical['diagnostics'])[:32])
