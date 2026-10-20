"""Offline Docling adapter. Imported only inside its owned conversion child."""
import hashlib
import json
from pathlib import PurePosixPath
import zipfile

from defusedxml import ElementTree
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import ConvertPipelineOptions, NativePdfPipelineOptions
from docling.document_converter import DocumentConverter, NativePdfFormatOption, WordFormatOption
from docling.backend.msword_backend import MsWordDocumentBackend

from modules.artifacts.domain.models import ArtifactError, ArtifactRef, CanonicalDocument, Coverage, DocumentBlock, Locator
from modules.artifacts.infra.processing.pdf_engine import extract_pdf


class OfflineWordBackend(MsWordDocumentBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The upstream fallback can discover LibreOffice for legacy drawings.
        # Disable its lazy initialization in this dedicated per-document backend.
        self.docx_to_pdf_converter = None
        self.docx_to_pdf_converter_init = True


def validate_docx(path, recipe):
    diagnostics, expanded = [], 0
    try:
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > 10_000 or len({entry.filename for entry in entries}) != len(entries):
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Office package exceeds its entry limit or repeats entries')
            for entry in entries:
                name = PurePosixPath(entry.filename)
                if name.is_absolute() or '..' in name.parts or '\\' in entry.filename or entry.flag_bits & 1:
                    raise ArtifactError('DOCUMENT_CONVERSION_FAILED', 'Office package contains an unsupported part')
                expanded += entry.file_size
                if expanded > min(536_870_912, recipe.limits.max_bytes * 16) or entry.file_size > 67_108_864:
                    raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Office package exceeds its expanded byte limit')
                lower = entry.filename.lower()
                if any(part in lower for part in ('vbaproject', 'vba/', 'activex/', 'embeddings/')):
                    raise ArtifactError('DOCUMENT_CONVERSION_FAILED', 'Office macros and embedded executable objects are unsupported')
                if lower.endswith(('.wmf', '.emf', '.vml')):
                    diagnostics.append('office_legacy_drawing_not_rendered')
                if lower.endswith(('.xml', '.rels')):
                    value = archive.read(entry)
                    root = ElementTree.fromstring(value)
                    for node in root.iter():
                        if node.attrib.get('TargetMode') == 'External' and not node.attrib.get('Type', '').endswith('/hyperlink'):
                            raise ArtifactError('DOCUMENT_CONVERSION_FAILED', 'Office external resource relationships are unsupported')
                        if node.tag.rsplit('}', 1)[-1].lower() in {'object', 'oleobject', 'altchunk', 'fldchar', 'instrtext'}:
                            diagnostics.append('office_active_field_not_evaluated')
            if '[Content_Types].xml' not in archive.namelist() or 'word/document.xml' not in archive.namelist():
                raise ArtifactError('DOCUMENT_CONVERSION_FAILED', 'Original is not an Office document package')
    except (zipfile.BadZipFile, ValueError, ElementTree.ParseError) as error:
        raise ArtifactError('DOCUMENT_CONVERSION_FAILED', 'Office package is invalid') from error
    return diagnostics


def _block_text(item, document):
    label = str(item.label)
    if label == 'table':
        return item.export_to_markdown(doc=document)
    if label == 'picture':
        return item.caption_text(doc=document)
    return getattr(item, 'text', '')


def convert_docling(path, revision, recipe, *, threads):
    is_pdf = revision.content_type.split(';', 1)[0].strip().lower() == 'application/pdf'
    native_pdf = extract_pdf(str(path), revision, recipe) if is_pdf else None
    diagnostics = ['native_pdf_layout_not_inferred'] if is_pdf else validate_docx(path, recipe)
    pdf_options = NativePdfPipelineOptions(parser_threads=threads, generate_page_images=False,
        generate_picture_images=False, enable_remote_services=False, allow_external_plugins=False,
        document_timeout=recipe.limits.timeout_seconds)
    word_options = ConvertPipelineOptions(enable_remote_services=False, allow_external_plugins=False,
        document_timeout=recipe.limits.timeout_seconds, do_picture_classification=False,
        do_picture_description=False, do_chart_extraction=False)
    converter = DocumentConverter(allowed_formats=[InputFormat.PDF, InputFormat.DOCX], format_options={
        InputFormat.PDF: NativePdfFormatOption(pipeline_options=pdf_options),
        InputFormat.DOCX: WordFormatOption(pipeline_options=word_options, backend=OfflineWordBackend)})
    result = converter.convert(path, raises_on_error=False, max_num_pages=recipe.limits.max_pages,
                               max_file_size=recipe.limits.max_bytes)
    if result.status not in {ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS}:
        raise ArtifactError('DOCUMENT_CONVERSION_FAILED', 'Docling could not convert the original document')
    if result.status == ConversionStatus.PARTIAL_SUCCESS or result.errors:
        diagnostics.append('docling_partial_conversion')
    blocks, stack, characters = [], [], 0
    for item, level in result.document.iterate_items():
        if len(blocks) >= recipe.limits.max_blocks:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Docling exceeds its canonical block limit')
        label = str(item.label)
        text = _block_text(item, result.document)
        characters += len(text)
        if characters > min(20_000_000, recipe.limits.max_bytes * 16):
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Docling exceeds its extracted character limit')
        kind = {'section_header': 'heading', 'title': 'heading', 'table': 'table',
                'picture': 'figure', 'list_item': 'list', 'code': 'code'}.get(label, 'paragraph')
        identity = 'block-' + hashlib.sha256(f'{revision.sha256}:docling:{item.self_ref}'.encode()).hexdigest()[:24]
        metadata = {}
        if kind == 'heading':
            heading = getattr(item, 'level', 1)
            if heading > recipe.parameters.max_heading_depth:
                kind = 'paragraph'
                diagnostics.append('heading_depth_limit_preserved_as_paragraph')
            else:
                metadata.update(heading_level=max(1, min(6, heading)), title=text[:512])
        if kind == 'figure':
            diagnostics.append('figure_content_not_transcribed')
        evidence = item.model_dump(mode='json', exclude_none=True, exclude={'image'})
        data = json.dumps({'format': 'docling-item', 'docling_version': '2.140.0',
                           'hierarchy_depth': level, 'item': evidence}, ensure_ascii=False)
        coordinates = {'block_id': identity, 'char_start': 0, 'char_end': len(text),
                       'char_space': 'canonical_block_text'}
        if is_pdf and item.prov:
            provenance = item.prov[0]
            page_index = provenance.page_no - 1
            if not 0 <= page_index < native_pdf.page_count:
                raise ArtifactError('DOCUMENT_CONVERSION_FAILED', 'Docling returned invalid physical page provenance')
            page = native_pdf.pages[page_index]
            box = provenance.bbox.to_top_left_origin(page.height_points)
            coordinates.update(page_index=page_index, page_number=page_index + 1,
                bbox=(max(0, min(1, box.l / page.width_points)), max(0, min(1, box.t / page.height_points)),
                      max(0, min(1, box.r / page.width_points)), max(0, min(1, box.b / page.height_points))))
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else None
        blocks.append(DocumentBlock(identity, kind, text, Locator(**coordinates),
            data_json=data, parent_id=parent, **metadata))
        stack.append((level, identity))
    if native_pdf is not None:
        diagnostics.extend(native_pdf.diagnostics)
    coverage = Coverage.PARTIAL if diagnostics else Coverage.COMPLETE
    if not blocks:
        coverage = native_pdf.coverage if native_pdf is not None else Coverage.UNSUPPORTED
        diagnostics.append('empty_document')
    return CanonicalDocument(ArtifactRef(revision.artifact_id, revision.id), tuple(blocks), coverage,
        tuple(sorted(set(diagnostics))), source_size_bytes=revision.size_bytes,
        page_count=native_pdf.page_count if native_pdf is not None else None,
        pages=native_pdf.pages if native_pdf is not None else ())
