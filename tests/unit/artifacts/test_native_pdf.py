import asyncio
import hashlib
import io
import json
from pathlib import Path

from PIL import Image
import pytest

from modules.artifacts.application.contracts.processing import ComponentReference, ProcessingRecipe
from modules.artifacts.domain.models import ArtifactError, Coverage, Revision
from modules.artifacts.infra.processing.native_pdf import NativePdfProcessor
from tests.fixtures.artifacts.pdf_sources import synthetic_pdf


def inputs(content, **options):
    revision = Revision('revision', 'artifact', 'original.pdf', 'application/pdf', len(content),
                        hashlib.sha256(content).hexdigest(), 'upload')
    recipe = ProcessingRecipe(mode='extract', processor=ComponentReference(name='native-pdf', version='1'), **options)
    async def stream():
        for offset in range(0, len(content), 65_536):
            yield content[offset:offset + 65_536]
    return revision, stream(), recipe


@pytest.mark.asyncio
async def test_pdf_preserves_physical_pages_labels_missing_text_ligatures_and_columns():
    document = await NativePdfProcessor().process(*inputs(synthetic_pdf()))
    assert document.page_count == 12 and document.coverage == Coverage.PARTIAL
    golden = Path(__file__).resolve().parents[2] / 'fixtures/artifacts/pdf-pages.golden.json'
    assert [{'page_index': p.page_index, 'page_number': p.page_number, 'label': p.label, 'status': p.status}
            for p in document.pages] == json.loads(golden.read_text())
    assert [(p.page_index, p.page_number, p.label) for p in document.pages[:3]] == [(0, 1, 'i'), (1, 2, 'ii'), (2, 3, '1')]
    assert document.pages[3].status == 'empty'
    assert document.pages[4].status == 'needs_ocr'
    assert 'reading_order_may_be_degraded' in document.pages[5].diagnostics
    # The synthetic ToUnicode map contains U+FB01; PDFium expands the ligature.
    assert 'Ligatura final' in document.blocks[0].text
    assert 'Sumário' in document.blocks[0].text
    assert len([block for block in document.blocks if 'Capítulo contínuo' in block.text]) == 2
    last = next(block for block in document.blocks if block.locator.page_number == 12)
    assert last.locator.page_index == 11 and 'física 12' in last.text
    assert all(block.locator.byte_start is None and block.locator.char_space == 'page_extracted_text' for block in document.blocks)


@pytest.mark.asyncio
async def test_complete_textual_pdf_and_actual_page_rendering():
    content = synthetic_pdf(pages=2, empty_page=None, image_page=None, two_columns=None)
    document = await NativePdfProcessor().process(*inputs(content))
    assert document.coverage == Coverage.COMPLETE
    rendered = await NativePdfProcessor().render(*inputs(content), page_index=1, dpi=72)
    with Image.open(io.BytesIO(rendered)) as image:
        assert image.format == 'PNG' and image.size == (612, 792)
        assert image.convert('L').getextrema()[0] < 255


@pytest.mark.asyncio
@pytest.mark.parametrize('image,coverage,status', [(True, Coverage.NEEDS_OCR, 'needs_ocr'), (False, Coverage.UNSUPPORTED, 'empty')])
async def test_entirely_nontextual_pdf_never_claims_complete(image, coverage, status):
    content = synthetic_pdf(pages=1, empty_page=None if image else 0, image_page=0 if image else None, two_columns=None)
    document = await NativePdfProcessor().process(*inputs(content))
    assert document.coverage == coverage and document.blocks == ()
    assert document.pages[0].status == status


@pytest.mark.asyncio
@pytest.mark.parametrize('content,expected', [
    (b'not a PDF', 'PDF_INVALID_DOCUMENT'), (b'%PDF-1.7\nbroken', 'PDF_INVALID_DOCUMENT'),
    (synthetic_pdf(encrypted=True), 'PDF_PASSWORD_REQUIRED'),
])
async def test_pdf_corrupt_disguised_and_protected_sources_fail_precisely(content, expected):
    with pytest.raises(ArtifactError) as error:
        await NativePdfProcessor().process(*inputs(content))
    assert error.value.code == expected


@pytest.mark.asyncio
async def test_pdf_page_pixel_and_physical_range_limits():
    content = synthetic_pdf()
    with pytest.raises(ArtifactError, match='page limit'):
        await NativePdfProcessor().process(*inputs(content, limits={'max_pages': 2}))
    with pytest.raises(ArtifactError) as error:
        await NativePdfProcessor().render(*inputs(content), page_index=12)
    assert error.value.code == 'ARTIFACT_INVALID_RANGE'
    with pytest.raises(ArtifactError) as error:
        await NativePdfProcessor().render(*inputs(content), page_index=0, max_pixels=100)
    assert error.value.code == 'ARTIFACT_LIMIT_EXCEEDED'


@pytest.mark.asyncio
async def test_pdf_cancelled_render_reaps_real_child_and_private_scratch(monkeypatch):
    from pathlib import Path
    import tempfile
    from modules.artifacts.infra.processing import native_pdf

    real_spawn = asyncio.create_subprocess_exec
    spawned, paths, gate = [], [], asyncio.Event()
    async def delayed_spawn(*args, **kwargs):
        paths.append(Path(args[-1]))
        process = await real_spawn(native_pdf.sys.executable, '-c', 'import time; time.sleep(60)', **kwargs)
        spawned.append(process)
        gate.set()
        return process
    monkeypatch.setattr(native_pdf.asyncio, 'create_subprocess_exec', delayed_spawn)
    task = asyncio.create_task(NativePdfProcessor().render(*inputs(synthetic_pdf()), page_index=0))
    await asyncio.wait_for(gate.wait(), timeout=10)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert spawned[0].returncode is not None
    assert not paths[0].exists() and paths[0].parent == Path(tempfile.gettempdir())


@pytest.mark.asyncio
async def test_pdf_wall_timeout_reaps_child_and_leaves_no_private_source(monkeypatch):
    from pathlib import Path
    from modules.artifacts.infra.processing import native_pdf
    real_spawn = asyncio.create_subprocess_exec
    children, paths = [], []
    async def delayed_spawn(*args, **kwargs):
        paths.append(Path(args[-1]))
        child = await real_spawn(native_pdf.sys.executable, '-c', 'import time; time.sleep(60)', **kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(native_pdf.asyncio, 'create_subprocess_exec', delayed_spawn)
    with pytest.raises(TimeoutError):
        await NativePdfProcessor().process(*inputs(synthetic_pdf(), limits={'timeout_seconds': 1}))
    assert children[0].returncode is not None and not paths[0].exists()
