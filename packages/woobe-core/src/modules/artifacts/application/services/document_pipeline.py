from dataclasses import asdict

from modules.artifacts.application.contracts.jobs import ProcessingJobResult
from modules.artifacts.application.document_codec import canonical_value, json_chunks, serialized_identity
from modules.artifacts.application.ports.processing import ProcessingStage
from modules.artifacts.domain.models import ArtifactError
from shared.contracts.object_storage import ObjectStorageError


class DocumentPipeline:
    def __init__(self, processors, blocking_io):
        self._processors, self._blocking_io = processors, blocking_io

    def stages(self, recipe):
        if recipe.mode != 'extract' or recipe.processor is None or any((recipe.indexer, recipe.enricher)):
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Requested document pipeline stages are unavailable')
        processor = self._processors.get((recipe.processor.name, recipe.processor.version))
        if recipe.ocr is not None and not getattr(processor, 'supports_ocr', False):
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Selected document processor does not support selective OCR')
        return (ProcessingStage('extract', self._extract),)

    async def _extract(self, context):
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
            metadata = await context.storage.put(key, chunks, size_bytes=asset.size_bytes,
                sha256=asset.sha256, content_type=asset.content_type)
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
            metadata = await context.storage.put(key, chunks(), size_bytes=size,
                sha256=digest, content_type='application/json')
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
            asset_metadata = await context.storage.put(asset_key, asset_chunks(), size_bytes=asset_size,
                sha256=asset_digest, content_type='application/json')
            asset_manifest = {'key': asset_key, 'sha256': asset_digest, 'size_bytes': asset_size,
                              'version_id': asset_metadata.version_id}
        return {'key': key, 'sha256': metadata.sha256, 'size_bytes': metadata.size_bytes,
                'content_type': metadata.content_type, 'version_id': metadata.version_id,
                'source_sha256': context.source.sha256, 'coverage': document.coverage.value,
                'block_count': len(document.blocks), 'page_count': document.page_count or 0,
                'diagnostics': list(document.diagnostics[:32]),
                'diagnostic_count': len(document.diagnostics), 'canonical_schema_version': '1',
                'asset_count': len(document.assets), 'asset_manifest': asset_manifest}

    def result(self, context):
        canonical = context.checkpoints['extract']
        return ProcessingJobResult(mode=context.lease.recipe.mode, processing_performed=True,
            source_sha256=context.source.sha256, coverage=canonical['coverage'],
            block_count=canonical['block_count'], page_count=canonical['page_count'],
            diagnostics=tuple(canonical['diagnostics'])[:32])
