from types import SimpleNamespace

import pytest

from modules.artifacts.application.contracts.representations import RenderRepresentationPage
from modules.artifacts.application.use_cases.render_representation_page import RenderRepresentationPageUseCase
from modules.artifacts.domain.models import ArtifactError, Revision


class ContentStream:
    def __init__(self):
        self.closed = False

    def __aiter__(self):
        async def chunks():
            yield b'%PDF'

        return chunks()

    async def aclose(self):
        self.closed = True


class RepresentationReader:
    def __init__(self, *, page_count=2):
        self.page_count = page_count
        self.request = None

    async def resolve(self, request):
        self.request = request
        return SimpleNamespace(public_view=SimpleNamespace(
            page_count=self.page_count,
            source_sha256='a' * 64,
        ))


class FileReader:
    def __init__(self, revision):
        self.revision = revision
        self.stream = ContentStream()
        self.request = None

    async def open_content(self, request):
        self.request = request
        return SimpleNamespace(revision=self.revision), self.stream


class Renderer:
    def __init__(self):
        self.arguments = None

    async def render(self, revision, content, recipe, **options):
        self.arguments = (revision, recipe, options)
        async for _ in content:
            pass
        return b'png-bytes'


def request(**overrides):
    values = {
        'principal': object(),
        'scope': object(),
        'workspace_id': 'workspace',
        'artifact_id': 'artifact',
        'revision_id': 'revision',
        'representation_set_id': 'representation',
        'page_index': 1,
        'dpi': 144,
        'max_pixels': 2_000_000,
    }
    values.update(overrides)
    return RenderRepresentationPage(**values)


@pytest.mark.asyncio
async def test_render_page_uses_snapshot_and_closes_source_stream():
    revision = Revision('revision', 'artifact', 'original.pdf', 'application/pdf', 4, 'b' * 64, 'upload')
    representations = RepresentationReader()
    files = FileReader(revision)
    renderer = Renderer()

    result = await RenderRepresentationPageUseCase(representations, files, renderer).execute(request())

    assert result.content == b'png-bytes'
    assert result.source_sha256 == 'a' * 64
    assert representations.request.representation_set_id == 'representation'
    assert files.request.revision_id == 'revision'
    assert renderer.arguments[0] is revision
    assert renderer.arguments[1].limits.max_pages == 2
    assert renderer.arguments[2] == {'page_index': 1, 'dpi': 144, 'max_pixels': 2_000_000}
    assert files.stream.closed


@pytest.mark.asyncio
async def test_render_page_rejects_out_of_range_before_opening_file():
    representations = RepresentationReader(page_count=1)
    files = FileReader(None)

    with pytest.raises(ArtifactError) as error:
        await RenderRepresentationPageUseCase(representations, files, Renderer()).execute(
            request(page_index=1),
        )

    assert error.value.code == 'ARTIFACT_INVALID_RANGE'
    assert files.request is None


@pytest.mark.asyncio
async def test_render_page_rejects_non_pdf_and_closes_stream():
    revision = Revision('revision', 'artifact', 'source.txt', 'text/plain', 4, 'b' * 64, 'upload')
    files = FileReader(revision)

    with pytest.raises(ArtifactError) as error:
        await RenderRepresentationPageUseCase(
            RepresentationReader(), files, Renderer(),
        ).execute(request())

    assert error.value.code == 'PROCESSOR_UNAVAILABLE'
    assert files.stream.closed
