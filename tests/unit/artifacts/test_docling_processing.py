import hashlib
import json

import pytest

from modules.artifacts.application.contracts.processing import ComponentReference, ProcessingRecipe
from modules.artifacts.application.document_codec import canonical_value, decode_canonical, json_chunks
from modules.artifacts.domain.models import ArtifactError, Coverage, Revision
from modules.artifacts.infra.processing.docling_manifest import docling_readiness
from modules.artifacts.infra.processing.docling_native import DOCX_MEDIA_TYPE, DoclingNativeProcessor


READY = docling_readiness()[0]


def inputs(content, media):
    revision = Revision('revision', 'artifact', 'objects/original', media, len(content), hashlib.sha256(content).hexdigest(), 'upload')
    recipe = ProcessingRecipe(mode='extract', processor=ComponentReference(name='docling-native', version='2.140.0'))
    async def stream():
        yield content
    return revision, stream(), recipe


@pytest.mark.skipif(not READY, reason='optional real Docling processing extra is not installed')
@pytest.mark.asyncio
async def test_real_docling_docx_preserves_headings_hierarchy_table_figure_and_unicode():
    from tests.fixtures.artifacts.docx_sources import synthetic_docx
    document = await DoclingNativeProcessor(memory_bytes=2_147_483_648).process(*inputs(synthetic_docx(), DOCX_MEDIA_TYPE))
    assert document.page_count is None and document.pages == ()
    assert document.coverage == Coverage.PARTIAL and 'figure_content_not_transcribed' in document.diagnostics
    headings = [b for b in document.blocks if b.kind == 'heading']
    assert [(b.text, b.heading_level) for b in headings] == [('Apostila de ação', 1), ('Tabela e figura', 2)]
    assert headings[1].parent_id == headings[0].id
    assert any('João e maçã' in b.text for b in document.blocks)
    assert any(b.parent_id is not None for b in document.blocks)
    table = next(b for b in document.blocks if b.kind == 'table')
    assert '12,50' in table.text
    assert json.loads(table.data_json)['item']['data']['num_rows'] == 2
    assert table.parent_id == headings[1].id
    assert any(b.kind == 'figure' for b in document.blocks)
    assert all(b.locator.page_index is None and b.locator.char_space == 'canonical_block_text' for b in document.blocks)
    assert decode_canonical(b''.join(json_chunks(canonical_value(document)))) == document


@pytest.mark.skipif(not READY, reason='optional real Docling processing extra is not installed')
@pytest.mark.asyncio
async def test_real_docling_multicolumn_pdf_preserves_boxes_physical_pages_and_explicit_partial_layout():
    from tests.fixtures.artifacts.pdf_sources import synthetic_pdf
    document = await DoclingNativeProcessor(memory_bytes=2_147_483_648).process(*inputs(synthetic_pdf(), 'application/pdf'))
    assert document.coverage == Coverage.PARTIAL and document.page_count == 12
    assert 'native_pdf_layout_not_inferred' in document.diagnostics
    assert document.pages[3].status == 'empty' and document.pages[4].status == 'needs_ocr'
    blocks = [b for b in document.blocks if b.locator.page_index == 5]
    assert any('Esquerda' in b.text for b in blocks) and any('Direita' in b.text for b in blocks)
    assert all(b.locator.bbox is not None and b.locator.page_number == 6 for b in blocks)
    assert any(b.kind == 'figure' for b in document.blocks)
    assert document.pages[0].label == 'i'


def test_missing_optional_docling_distribution_is_passively_unavailable(monkeypatch):
    from modules.artifacts.infra.processing import docling_manifest
    from modules.artifacts.infra.processing.native_registry import docling_native_descriptor
    monkeypatch.setattr(docling_manifest, 'probe_distribution', lambda name, expected: (False, 'dependency_not_installed'))
    descriptor = docling_native_descriptor()
    assert not descriptor.available and 'dependency_not_installed' in descriptor.diagnostic


def test_canonical_hierarchy_rejects_cycles_and_missing_parents():
    from modules.artifacts.domain.models import ArtifactRef, CanonicalDocument, DocumentBlock, Locator
    for blocks in [
        (DocumentBlock('a', 'paragraph', 'a', Locator(), parent_id='missing'),),
        (DocumentBlock('a', 'paragraph', 'a', Locator(), parent_id='b'),
         DocumentBlock('b', 'paragraph', 'b', Locator(), parent_id='a')),
    ]:
        with pytest.raises(ValueError, match='hierarchy'):
            CanonicalDocument(ArtifactRef('source', 'revision'), blocks, Coverage.COMPLETE)


@pytest.mark.skipif(not READY, reason='optional real Docling processing extra is not installed')
@pytest.mark.asyncio
async def test_docling_worker_rejects_a_stale_frozen_manifest_before_conversion():
    from modules.artifacts.application.contracts.processing import LibraryPin
    from tests.fixtures.artifacts.pdf_sources import synthetic_pdf
    revision, stream, recipe = inputs(synthetic_pdf(), 'application/pdf')
    recipe = recipe.model_copy(update={'libraries': (LibraryPin(name='docling-native-manifest', version='0' * 64),)})
    with pytest.raises(ArtifactError) as error:
        await DoclingNativeProcessor(memory_bytes=2_147_483_648).process(revision, stream, recipe)
    assert error.value.code == 'PROCESSOR_UNAVAILABLE'


@pytest.mark.skipif(not READY, reason='optional real Docling processing extra is not installed')
@pytest.mark.asyncio
async def test_docx_macros_and_external_images_are_rejected_before_conversion():
    import io
    import zipfile
    from tests.fixtures.artifacts.docx_sources import synthetic_docx
    for extra_name, content in [('word/vbaProject.bin', b'not executed'),
        ('word/_rels/external.rels', b'<Relationships><Relationship TargetMode="External" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="https://invalid.example/image.png"/></Relationships>')]:
        buffer = io.BytesIO(synthetic_docx())
        with zipfile.ZipFile(buffer, 'a') as archive:
            archive.writestr(extra_name, content)
        with pytest.raises(ArtifactError) as error:
            await DoclingNativeProcessor(memory_bytes=2_147_483_648).process(*inputs(buffer.getvalue(), DOCX_MEDIA_TYPE))
        assert error.value.code == 'DOCUMENT_CONVERSION_FAILED'
