import asyncio
import hashlib
import io
import json
import os
from pathlib import Path

from PIL import Image
import pytest

from modules.artifacts.application.contracts.processing import ComponentReference, ProcessingRecipe
from modules.artifacts.application.document_codec import canonical_value, decode_canonical, json_chunks
from modules.artifacts.application.processing_registry import ProcessingRegistry
from modules.artifacts.domain.models import ArtifactError, Coverage, Revision, SourceRef
from modules.artifacts.infra.processing.native_document import NativeDocumentProcessor
from modules.artifacts.infra.processing.native_registry import native_document_descriptor, tesseract_descriptor
from modules.artifacts.infra.processing.ocr_manifest import ocr_readiness


DATA = os.environ.get('WOOBE_ARTIFACT_TEST_OCR_DATA_DIR')
EXECUTABLE = os.environ.get('WOOBE_ARTIFACT_TEST_TESSERACT_EXECUTABLE', '/usr/bin/tesseract')
READY = ocr_readiness(DATA, EXECUTABLE)[0]
real_ocr = pytest.mark.skipif(not READY, reason='real qualified OCR engine/model installation is not configured')


def recipe(*, ocr=True, **options):
    value = ProcessingRecipe(mode='extract', processor=ComponentReference(name='native-document', version='1'),
        ocr=ComponentReference(name='native-tesseract', version='1') if ocr else None, **options)
    registry = ProcessingRegistry((native_document_descriptor(), tesseract_descriptor(DATA, EXECUTABLE)))
    return registry.normalize(value)


async def extract(content, media='image/png', *, definition=None, data_dir=DATA):
    source = Revision('revision', 'artifact', 'objects/original', media, len(content), hashlib.sha256(content).hexdigest(), 'upload')
    async def stream():
        for offset in range(0, len(content), 4096):
            yield content[offset:offset + 4096]
    assets = {}
    async def publish(asset, chunks):
        value = b''.join([chunk async for chunk in chunks])
        assert len(value) == asset.size_bytes and hashlib.sha256(value).hexdigest() == asset.sha256
        assets[asset.id] = value
    document = await NativeDocumentProcessor(ocr_data_dir=data_dir, tesseract_executable=EXECUTABLE).process(
        source, stream(), definition or recipe(), publish_asset=publish)
    assert decode_canonical(b''.join(json_chunks(canonical_value(document)))) == document
    return document, assets


@real_ocr
@pytest.mark.asyncio
@pytest.mark.parametrize('media', ['image/png', 'image/jpeg'])
async def test_real_portuguese_ocr_preserves_visuals_and_engine_reported_word_scores(media):
    from tests.fixtures.artifacts.ocr_sources import PORTUGUESE, portuguese_image, portuguese_jpeg_with_exif_rotation
    content = portuguese_image() if media == 'image/png' else portuguese_jpeg_with_exif_rotation()
    document, assets = await extract(content, media)
    lines = [block for block in document.blocks if block.extraction_method == 'ocr']
    assert [block.text for block in lines] == list(PORTUGUESE)
    assert document.coverage == Coverage.PARTIAL and document.page_count is None
    assert len(document.assets) == len(assets) == 1
    with Image.open(io.BytesIO(next(iter(assets.values())))) as visual:
        assert visual.size == (1800, 500) and not visual.info
    for block in lines:
        assert block.asset_ids == (document.assets[0].id,)
        assert block.locator.image_bbox is not None and block.locator.page_index is None
        assert block.locator.char_space == 'canonical_block_text'
        with pytest.raises(ValueError, match='generation'):
            SourceRef('artifact', 'revision', hashlib.sha256(content).hexdigest(), locator=block.locator)
        assert SourceRef('artifact', 'revision', hashlib.sha256(content).hexdigest(),
                         representation_set_id='generation', locator=block.locator).locator == block.locator
        metadata = json.loads(block.data_json)
        assert metadata['languages'] == ['por', 'eng'] and metadata['engine_version'] == '5.5.0'
        assert all(word['confidence'] is None or 0 <= word['confidence'] <= 100 for word in metadata['words'])
        assert 'probability' not in metadata and metadata['confidence_semantics'].startswith('uncalibrated')
    assert 'source_visuals_preserved_not_semantically_interpreted' in document.diagnostics


@real_ocr
@pytest.mark.asyncio
async def test_hybrid_pdf_ocr_keeps_native_text_and_skips_native_and_blank_pages():
    from tests.fixtures.artifacts.ocr_sources import PORTUGUESE, hybrid_pdf
    document, assets = await extract(hybrid_pdf(), 'application/pdf')
    assert document.page_count == 3
    assert [page.status for page in document.pages] == ['text', 'ocr', 'empty']
    assert len(assets) == 1 and document.assets[0].locator.page_index == 1
    native = [block for block in document.blocks if block.extraction_method == 'native' and block.text.strip()]
    assert len(native) == 1 and 'Sumário' in native[0].text
    ocr = [block for block in document.blocks if block.extraction_method == 'ocr']
    assert [block.text for block in ocr] == list(PORTUGUESE)
    assert all(block.locator.page_index == 1 and block.locator.page_number == 2 for block in ocr)
    assert document.coverage == Coverage.PARTIAL


@real_ocr
@pytest.mark.asyncio
async def test_hybrid_page_recognizes_only_embedded_image_regions_without_duplicating_native_text():
    from tests.fixtures.artifacts.ocr_sources import PORTUGUESE, hybrid_page_pdf
    document, assets = await extract(hybrid_page_pdf(), 'application/pdf')
    assert document.pages[0].status == 'mixed' and document.coverage == Coverage.PARTIAL
    native = [block for block in document.blocks if block.extraction_method == 'native' and block.text.strip()]
    assert len(native) == 1 and 'Sumário' in native[0].text
    ocr = [block for block in document.blocks if block.extraction_method == 'ocr']
    assert [block.text for block in ocr] == list(PORTUGUESE)
    assert len(assets) == 1
    for block in ocr:
        assert block.locator.page_index == 0 and block.locator.bbox[1] > .2
        region = json.loads(block.data_json)['source_region_bbox']
        assert region != [0, 0, 1, 1] and region[0] <= block.locator.bbox[0] <= region[2]


@real_ocr
@pytest.mark.asyncio
async def test_rotated_scan_retains_actual_orientation_evidence_and_source_boxes():
    from tests.fixtures.artifacts.ocr_sources import portuguese_image
    document, assets = await extract(portuguese_image(rotate=90, dense=True))
    lines = [block for block in document.blocks if block.extraction_method == 'ocr']
    assert document.coverage == Coverage.PARTIAL and assets
    assert any('João' in block.text for block in lines)
    orientation = json.loads(lines[0].data_json)['orientation']
    assert orientation['applied_rotation'] in {90, 270} and orientation['confidence'] >= 5
    for block in lines:
        assert all(0 <= coordinate <= 1 for coordinate in block.locator.image_bbox)


@real_ocr
@pytest.mark.asyncio
async def test_known_poor_scan_never_claims_complete_or_discards_its_source_visual():
    from tests.fixtures.artifacts.ocr_sources import portuguese_image
    document, assets = await extract(portuguese_image(poor=True))
    assert document.coverage in {Coverage.PARTIAL, Coverage.NEEDS_OCR} and assets
    assert any('ocr_no_text_recognized' in note or 'ocr_low_confidence_words' in note for note in document.diagnostics)


@pytest.mark.asyncio
async def test_image_without_ocr_preserves_pixels_without_fabricating_text_or_pages():
    image = Image.new('RGBA', (120, 80), (10, 20, 30, 0))
    source = io.BytesIO()
    image.save(source, format='PNG')
    image.close()
    document, assets = await extract(source.getvalue(), definition=recipe(ocr=False), data_dir=None)
    assert document.coverage == Coverage.NEEDS_OCR and document.page_count is None
    assert len(document.blocks) == 1 and document.blocks[0].kind == 'figure' and document.blocks[0].text == ''
    with Image.open(io.BytesIO(next(iter(assets.values())))) as normalized:
        assert normalized.size == (120, 80) and normalized.getpixel((0, 0)) == (255, 255, 255)
        assert not normalized.info


@pytest.mark.asyncio
async def test_missing_ocr_models_are_unavailable_and_never_empty_success(tmp_path):
    descriptor = tesseract_descriptor(tmp_path, EXECUTABLE)
    registry = ProcessingRegistry((native_document_descriptor(), descriptor))
    assert not descriptor.available
    component = next(c for c in registry.capabilities() if c['role'] == 'ocr')
    assert component['media_types'] == component['languages'] == []
    image = Image.new('RGB', (32, 32), 'white')
    source = io.BytesIO()
    image.save(source, format='PNG')
    image.close()
    with pytest.raises(ArtifactError) as error:
        await extract(source.getvalue(), definition=recipe(), data_dir=tmp_path)
    assert error.value.code == 'PROCESSOR_UNAVAILABLE'


@real_ocr
def test_uninstalled_language_is_explicitly_unready():
    registry = ProcessingRegistry((native_document_descriptor(), tesseract_descriptor(DATA, EXECUTABLE)))
    definition = recipe(parameters={'languages': ['fra']})
    readiness = registry.readiness(definition, content_type='image/png')
    assert not readiness['ready'] and 'ocr:unsupported_language' in readiness['diagnostics']


@real_ocr
def test_model_receipt_survives_filesystem_copy_but_rejects_same_size_corruption(tmp_path):
    import shutil
    copied = tmp_path / 'copied-models'
    shutil.copytree(DATA, copied)
    assert ocr_readiness(copied, EXECUTABLE)[0]
    model = copied / 'por.traineddata'
    with model.open('r+b') as value:
        first = value.read(1)
        value.seek(0)
        value.write(bytes([first[0] ^ 1]))
    assert not ocr_readiness(copied, EXECUTABLE)[0]


@pytest.mark.asyncio
async def test_image_pixel_limit_fails_before_visual_publication():
    image = Image.new('RGB', (4001, 4000), 'white')
    output = io.BytesIO()
    image.save(output, format='PNG')
    image.close()
    with pytest.raises(ArtifactError) as error:
        await extract(output.getvalue(), definition=recipe(ocr=False))
    assert error.value.code == 'ARTIFACT_LIMIT_EXCEEDED'


@real_ocr
@pytest.mark.asyncio
async def test_cancellation_reaps_real_tesseract_grandchild_before_removing_scratch(monkeypatch):
    from modules.artifacts.infra.processing import native_pdf
    from tests.fixtures.artifacts.ocr_sources import portuguese_image

    real_spawn = asyncio.create_subprocess_exec
    children, scratch = [], []
    async def record_spawn(*args, **kwargs):
        process = await real_spawn(*args, **kwargs)
        children.append(process)
        scratch.append(Path(args[-1]))
        return process
    monkeypatch.setattr(native_pdf.asyncio, 'create_subprocess_exec', record_spawn)
    stopping = asyncio.Event()
    real_stop = native_pdf.NativePdfProcessor._stop_process_group
    async def stop(cls, process):
        stopping.set()
        await asyncio.sleep(.05)
        await real_stop(process)
    monkeypatch.setattr(native_pdf.NativePdfProcessor, '_stop_process_group', classmethod(stop))
    task = asyncio.create_task(extract(portuguese_image(dense=True)))
    async def actual_recognition_started():
        while True:
            if task.done():
                await task
                raise AssertionError('OCR completed before its live engine could be observed')
            if children:
                for entry in Path('/proc').iterdir():
                    if not entry.name.isdigit():
                        continue
                    try:
                        fields = (entry / 'stat').read_bytes().rsplit(b') ', 1)[1].split()
                        if int(fields[2]) != children[0].pid:
                            continue
                        command = (entry / 'cmdline').read_bytes()
                        if b'tessedit_create_tsv=1' in command:
                            return int(entry.name)
                    except (OSError, IndexError, ValueError):
                        continue
            await asyncio.sleep(.01)
    try:
        engine_pid = await asyncio.wait_for(actual_recognition_started(), timeout=20)
        task.cancel()
        await asyncio.wait_for(stopping.wait(), timeout=5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not native_pdf.NativePdfProcessor._group_is_live(children[0].pid)
        assert children[0].returncode is not None and not scratch[0].exists()
        state = Path(f'/proc/{engine_pid}/stat')
        assert not state.exists() or state.read_bytes().rsplit(b') ', 1)[1].split()[0] == b'Z'
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
