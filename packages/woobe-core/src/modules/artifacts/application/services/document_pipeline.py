from modules.artifacts.application.contracts.jobs import ProcessingJobResult
from modules.artifacts.application.document_codec import canonical_value, json_chunks, serialized_identity
from modules.artifacts.application.ports.processing import ProcessingStage
from modules.artifacts.domain.models import ArtifactError
from shared.contracts.object_storage import ObjectStorageError


class DocumentPipeline:
    def __init__(self, processors, blocking_io):
        self._processors, self._blocking_io = processors, blocking_io

    def stages(self, recipe):
        if recipe.mode != 'extract' or recipe.processor is None or any((recipe.indexer, recipe.ocr, recipe.enricher)):
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Requested document pipeline stages are unavailable')
        return (ProcessingStage('extract', self._extract),)

    async def _extract(self, context):
        selected = context.lease.recipe.processor
        processor = self._processors.get((selected.name, selected.version))
        if processor is None:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Selected document processor is unavailable')
        document = await processor.process(context.source, context.storage.open(context.source.object_key), context.lease.recipe)
        value = canonical_value(document)
        maximum = min(536_870_912, context.lease.recipe.limits.max_bytes * 16 + 1_048_576)
        size, digest = await self._blocking_io(serialized_identity, value, maximum)
        lease = context.lease
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
        return {'key': key, 'sha256': metadata.sha256, 'size_bytes': metadata.size_bytes,
                'content_type': metadata.content_type, 'version_id': metadata.version_id,
                'source_sha256': context.source.sha256, 'coverage': document.coverage.value,
                'block_count': len(document.blocks), 'page_count': document.page_count or 0,
                'diagnostics': list(document.diagnostics[:32]),
                'diagnostic_count': len(document.diagnostics), 'canonical_schema_version': '1'}

    def result(self, context):
        canonical = context.checkpoints['extract']
        return ProcessingJobResult(mode=context.lease.recipe.mode, processing_performed=True,
            source_sha256=context.source.sha256, coverage=canonical['coverage'],
            block_count=canonical['block_count'], page_count=canonical['page_count'],
            diagnostics=tuple(canonical['diagnostics'])[:32])
