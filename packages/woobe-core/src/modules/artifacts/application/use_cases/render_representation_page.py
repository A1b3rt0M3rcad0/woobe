from modules.artifacts.application.contracts.files import ReadFile
from modules.artifacts.application.contracts.processing import ProcessingRecipe
from modules.artifacts.application.contracts.representations import (
    ReadRepresentation,
    RenderRepresentationPage,
    RenderedRepresentationPage,
)
from modules.artifacts.application.ports.processing import PdfPageRenderer
from modules.artifacts.domain.models import ArtifactError


class RenderRepresentationPageUseCase:
    def __init__(self, representations, files, renderer: PdfPageRenderer):
        self._representations = representations
        self._files = files
        self._renderer = renderer

    async def execute(self, request: RenderRepresentationPage) -> RenderedRepresentationPage:
        snapshot = await self._representations.resolve(ReadRepresentation(
            request.principal,
            request.scope,
            request.workspace_id,
            request.artifact_id,
            request.revision_id,
            request.representation_set_id,
        ))
        public_view = snapshot.public_view
        if request.page_index >= public_view.page_count:
            raise ArtifactError(
                'ARTIFACT_INVALID_RANGE',
                'Physical page is out of range for this representation',
            )

        file_snapshot, stream = await self._files.open_content(ReadFile(
            request.principal,
            request.scope,
            request.workspace_id,
            request.artifact_id,
            request.revision_id,
        ))
        revision = file_snapshot.revision
        if revision is None or revision.content_type.split(';', 1)[0].strip().lower() != 'application/pdf':
            await stream.aclose()
            raise ArtifactError(
                'PROCESSOR_UNAVAILABLE',
                'Page images are available only for PDF revisions',
            )

        recipe = ProcessingRecipe.model_validate({
            'mode': 'extract',
            'processor': {'name': 'native-pdf', 'version': '1'},
            'limits': {
                'max_bytes': 536_870_912,
                'max_pages': public_view.page_count,
            },
        })
        try:
            content = await self._renderer.render(
                revision,
                stream,
                recipe,
                page_index=request.page_index,
                dpi=request.dpi,
                max_pixels=request.max_pixels,
            )
        finally:
            await stream.aclose()
        return RenderedRepresentationPage(content, public_view.source_sha256)
