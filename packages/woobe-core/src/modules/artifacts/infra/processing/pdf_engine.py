"""PDF parsing/rendering implementation, imported only inside an isolated child."""
import hashlib
import io
import math

from pypdf import PdfReader
from pypdf.errors import PdfReadError
import pypdfium2 as pdfium

from modules.artifacts.domain.models import ArtifactError, ArtifactRef, CanonicalDocument, Coverage, DocumentBlock, DocumentPage, Locator
from modules.artifacts.infra.processing.native_registry import PDFIUM_VERSION


def open_pdf(path, max_pages):
    if str(pdfium.PDFIUM_INFO) != PDFIUM_VERSION:
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Installed PDFium engine differs from its qualified build')
    with open(path, 'rb') as stream:
        if stream.read(5) != b'%PDF-':
            raise ArtifactError('PDF_INVALID_DOCUMENT', 'Original is not a PDF document')
    try:
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted:
            raise ArtifactError('PDF_PASSWORD_REQUIRED', 'Password-protected PDFs require an unprotected source revision')
        count = len(reader.pages)
        if not count:
            raise ArtifactError('PDF_INVALID_DOCUMENT', 'PDF contains no physical pages')
        if count > max_pages:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PDF exceeds its physical page limit')
        return reader
    except (PdfReadError, ValueError, KeyError, TypeError, RecursionError) as error:
        raise ArtifactError('PDF_INVALID_DOCUMENT', 'PDF structure is invalid') from error


def _degraded_layout(textpage, width):
    # Large gaps between consecutive glyphs on the same baseline can indicate
    # separate columns. This is a conservative warning, never a layout promise.
    previous = None
    for index in range(min(textpage.count_chars(), 200_000)):
        if chr(pdfium.raw.FPDFText_GetUnicode(textpage, index)).isspace():
            continue
        left, bottom, right, top = textpage.get_charbox(index)
        if previous is not None:
            old_left, old_bottom, old_right, old_top = previous
            if abs(top - old_top) < 3 and (left - old_right > width * .18 or left < old_left - width * .18):
                return True
        previous = (left, bottom, right, top)
    return False


def extract_pdf(path, revision, recipe):
    reader = open_pdf(path, recipe.limits.max_pages)
    try:
        labels = reader.page_labels
    except (ValueError, KeyError, TypeError, RecursionError):
        labels = [str(index + 1) for index in range(len(reader.pages))]
    pages, blocks, diagnostics = [], [], []
    characters = 0
    document = pdfium.PdfDocument(path)
    try:
        if len(document) != len(reader.pages):
            raise ArtifactError('PDF_INVALID_DOCUMENT', 'PDF parsers disagree on physical page count')
        for index in range(len(document)):
            page = document[index]
            textpage = None
            try:
                width, height = page.get_size()
                if not all(math.isfinite(value) and 0 < value <= 100_000 for value in (width, height)):
                    raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PDF page dimensions exceed the supported limit')
                textpage = page.get_textpage()
                if textpage.count_chars() > 2_000_000:
                    raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PDF page exceeds its text character limit')
                text = textpage.get_text_bounded(errors='strict').replace('\r\n', '\n').replace('\r', '\n')
                characters += len(text)
                if characters > min(20_000_000, recipe.limits.max_bytes * 16):
                    raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PDF exceeds its extracted text limit')
                page_diagnostics = []
                if text.strip():
                    status = 'text'
                    if textpage.count_chars() > 200_000:
                        page_diagnostics.append('reading_order_inspection_bounded')
                    if _degraded_layout(textpage, width):
                        page_diagnostics.append('reading_order_may_be_degraded')
                    if '\ufffd' in text:
                        page_diagnostics.append('unmapped_glyphs')
                    identity = 'block-' + hashlib.sha256(f'{revision.sha256}:pdf:{index}'.encode()).hexdigest()[:24]
                    blocks.append(DocumentBlock(identity, 'page', text, Locator(block_id=identity,
                        page_index=index, page_number=index + 1, char_start=0, char_end=len(text),
                        char_space='page_extracted_text', text_normalization='lf', bbox=(0, 0, 1, 1))))
                    if len(blocks) > recipe.limits.max_blocks:
                        raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PDF exceeds its canonical block limit')
                else:
                    # Inspect page objects without decoding embedded image bytes.
                    has_image = any(obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE for obj in page.get_objects(max_depth=8))
                    status = 'needs_ocr' if has_image else 'empty'
                    page_diagnostics.append('image_page_needs_ocr' if has_image else 'no_extractable_text')
                label = str(labels[index]) if index < len(labels) else str(index + 1)
                if len(label) > 128:
                    label = label[:128]
                    page_diagnostics.append('page_label_truncated')
                pages.append(DocumentPage(index, index + 1, label, width, height, len(text), status, tuple(page_diagnostics)))
                diagnostics.extend(f'page:{index}:{item}' for item in page_diagnostics)
            finally:
                if textpage is not None:
                    textpage.close()
                page.close()
    finally:
        document.close()
        reader.close()
    if not blocks:
        coverage = Coverage.NEEDS_OCR if any(p.status == 'needs_ocr' for p in pages) else Coverage.UNSUPPORTED
    else:
        coverage = Coverage.PARTIAL if diagnostics else Coverage.COMPLETE
    return CanonicalDocument(ArtifactRef(revision.artifact_id, revision.id), tuple(blocks), coverage,
        tuple(diagnostics), source_size_bytes=revision.size_bytes, text_normalization='lf',
        page_count=len(pages), pages=tuple(pages))


def render_pdf(path, *, page_index, max_pages, dpi=150, max_pixels=16_000_000):
    if not isinstance(page_index, int) or page_index < 0 or not 72 <= dpi <= 300:
        raise ArtifactError('ARTIFACT_INVALID_RANGE', 'Invalid PDF page or rendering resolution')
    reader = open_pdf(path, max_pages)
    try:
        if page_index >= len(reader.pages):
            raise ArtifactError('ARTIFACT_INVALID_RANGE', 'Physical PDF page is out of range')
    finally:
        reader.close()
    document = pdfium.PdfDocument(path)
    page = None
    try:
        page = document[page_index]
        return render_page_png(page, dpi=dpi, max_pixels=max_pixels)
    finally:
        if page is not None:
            page.close()
        document.close()


def render_page_png(page, *, dpi=150, max_pixels=16_000_000):
    bitmap = image = None
    try:
        width, height = page.get_size()
        if not all(math.isfinite(value) and 0 < value <= 100_000 for value in (width, height)):
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PDF page dimensions exceed the supported limit')
        scale = dpi / 72
        pixels = math.ceil(width * scale) * math.ceil(height * scale)
        if not math.isfinite(pixels) or pixels > max_pixels or pixels < 1:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Rendered PDF page exceeds its pixel limit')
        # Forms/actions/JavaScript are never initialized or executed.
        bitmap = page.render(scale=scale, may_draw_forms=False)
        image = bitmap.to_pil()
        output = io.BytesIO()
        image.save(output, format='PNG')
        if output.tell() > 67_108_864:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Rendered PDF PNG exceeds its byte limit')
        return output.getvalue()
    finally:
        if image is not None:
            image.close()
        if bitmap is not None:
            bitmap.close()
