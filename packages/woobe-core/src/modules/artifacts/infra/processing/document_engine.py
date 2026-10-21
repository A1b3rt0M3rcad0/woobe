from dataclasses import asdict, replace
import hashlib
import io
import json
import math

from PIL import Image, ImageOps
import pypdfium2 as pdfium

from modules.artifacts.domain.models import ArtifactError, ArtifactRef, CanonicalDocument, Coverage, DocumentAsset, DocumentBlock, Locator
from modules.artifacts.infra.processing.ocr_manifest import ocr_readiness, qualify_installation
from modules.artifacts.infra.processing.ocr_transcription import transcribe
from modules.artifacts.infra.processing.pdf_engine import extract_pdf, render_page_png


def _original_image(path, media):
    with Image.open(path) as source:
        if source.format != {'image/png': 'PNG', 'image/jpeg': 'JPEG'}[media] or getattr(source, 'n_frames', 1) != 1:
            raise ArtifactError('DOCUMENT_CONVERSION_FAILED', 'Image source format or frame count is unsupported')
        if not 0 < source.width * source.height <= 16_000_000:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Original image exceeds its pixel limit')
        oriented = ImageOps.exif_transpose(source)
        try:
            rgba = oriented.convert('RGBA')
            background = Image.new('RGBA', rgba.size, 'white')
            try:
                background.alpha_composite(rgba)
                image = background.convert('RGB')
            finally:
                rgba.close()
                background.close()
            try:
                image.info.clear()
                output = io.BytesIO()
                image.save(output, format='PNG')
                return output.getvalue()
            finally:
                image.close()
        finally:
            oriented.close()


def _hybrid_regions(page):
    """Qualify direct image rectangles with no existing native text.

    Nested Form XObjects keep their visual and partial diagnostic; their local
    transforms are not silently treated as physical page coordinates.
    """
    regions, diagnostics = [], []
    textpage = page.get_textpage()
    try:
        x0, y0, x1, y1 = page.get_bbox()
        for image in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE], max_depth=0):
            if len(regions) >= 128:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Hybrid page exceeds its OCR region limit')
            left, bottom, right, top = image.get_bounds()
            if not all(math.isfinite(value) for value in (left, bottom, right, top)):
                diagnostics.append('visual_region_bounds_unavailable')
                continue
            if textpage.get_text_bounded(left, bottom, right, top, errors='strict').strip():
                diagnostics.append('visual_region_native_text_preserved')
                continue
            box = (max(0, (left - x0) / (x1 - x0)), max(0, 1 - (top - y0) / (y1 - y0)),
                   min(1, (right - x0) / (x1 - x0)), min(1, 1 - (bottom - y0) / (y1 - y0)))
            if box[0] >= box[2] or box[1] >= box[3]:
                continue
            left_norm, top_norm, right_norm, bottom_norm = box
            rotation = page.get_rotation()
            if rotation == 90:
                box = (1 - bottom_norm, left_norm, 1 - top_norm, right_norm)
            elif rotation == 180:
                box = (1 - right_norm, 1 - bottom_norm, 1 - left_norm, 1 - top_norm)
            elif rotation == 270:
                box = (top_norm, 1 - right_norm, bottom_norm, 1 - left_norm)
            if any(min(box[2], old[2]) > max(box[0], old[0]) and min(box[3], old[3]) > max(box[1], old[1]) for old in regions):
                diagnostics.append('overlapping_visual_region_preserved_without_duplicate_ocr')
                continue
            regions.append(box)
    finally:
        textpage.close()
    return regions, diagnostics


def process_document(root, revision, recipe, *, executable, directory):
    media = revision.content_type.split(';', 1)[0].strip().lower()
    is_pdf = media == 'application/pdf'
    source = root / ('source.pdf' if is_pdf else 'source.png' if media == 'image/png' else 'source.jpg')
    if recipe.ocr is not None:
        if (recipe.ocr.name, recipe.ocr.version) != ('native-tesseract', '1'):
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Selected OCR implementation is unavailable')
        ready, diagnostic, receipt, manifest, digest = ocr_readiness(directory, executable)
        if not ready:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'OCR engine and pinned language files are not verified')
        actual = qualify_installation(directory, executable)
        if actual != receipt:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'OCR installation changed after qualification')
        if recipe.libraries:
            pins = {pin.name: pin.version for pin in recipe.libraries}
            if (pins.get('tesseract-data-manifest') != digest
                or pins.get('tesseract-binary') != receipt['executable_identity']['sha256']
                or pins.get('tesseract-build') != receipt['engine_build_sha256']):
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'OCR frozen recipe differs from the installed engine or model artifacts')
    native = extract_pdf(str(source), revision, recipe) if is_pdf else CanonicalDocument(
        ArtifactRef(revision.artifact_id, revision.id), (), Coverage.NEEDS_OCR, source_size_bytes=revision.size_bytes)
    blocks, pages, diagnostics = list(native.blocks), list(native.pages), list(native.diagnostics)
    assets, entries, total_bytes, missing = [], [], 0, 0
    visuals = root / 'visual-assets'
    visuals.mkdir()
    document = pdfium.PdfDocument(str(source)) if is_pdf else None
    try:
        indexes = range(native.page_count) if is_pdf else (None,)
        for index in indexes:
            page, has_image = None, True
            native_text = is_pdf and pages[index].status == 'text'
            regions = [(0, 0, 1, 1)]
            try:
                if is_pdf:
                    page = document[index]
                    has_image = any(obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE for obj in page.get_objects(max_depth=8))
                    if pages[index].status == 'text' and not has_image:
                        continue
                    if native_text:
                        regions, notes = _hybrid_regions(page)
                        diagnostics.extend(f'page:{index}:{note}' for note in notes)
                    png = render_page_png(page, dpi=recipe.parameters.ocr_dpi)
                else:
                    png = _original_image(source, media)
            finally:
                if page is not None:
                    page.close()
            if len(png) > 67_108_864:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Source visual exceeds its PNG byte limit')
            with Image.open(io.BytesIO(png)) as image:
                width, height = image.size
                gray = image.convert('L')
                try:
                    ink = gray.getextrema()[0] < 245
                finally:
                    gray.close()
            if is_pdf and not ink and not has_image:
                continue
            total_bytes += len(png)
            if total_bytes > min(536_870_912, recipe.limits.max_bytes * 16 + 1_048_576):
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Document visuals exceed their total byte budget')
            digest = hashlib.sha256(png).hexdigest()
            identity = 'asset-' + hashlib.sha256(f'{revision.sha256}:{index}:{digest}'.encode()).hexdigest()[:24]
            locator = Locator(page_index=index, page_number=index + 1, bbox=(0, 0, 1, 1)) if is_pdf else Locator(image_bbox=(0, 0, 1, 1))
            asset = DocumentAsset(identity, 'image/png', len(png), digest, width, height, locator)
            path = visuals / (identity + '.png')
            path.write_bytes(png)
            del png
            assets.append(asset)
            entries.append({'file': path.name, 'asset': asdict(asset)})
            figure_id = 'block-' + hashlib.sha256(f'{identity}:figure'.encode()).hexdigest()[:24]
            blocks.append(DocumentBlock(figure_id, 'figure', '', replace(locator, block_id=figure_id), asset_ids=(identity,)))
            if native_text:
                diagnostics.append(f'page:{index}:native_text_preserved_visual_available')
                if not regions:
                    diagnostics.append(f'page:{index}:visual_region_not_qualified_for_ocr')
                    continue
            if recipe.ocr is None:
                missing += 1
                diagnostics.append('visual_source_needs_ocr')
                if is_pdf and not native_text:
                    pages[index] = replace(pages[index], status='needs_ocr', diagnostics=('visual_source_needs_ocr',))
                continue
            lines, notes = [], []
            for region_index, region in enumerate(regions):
                input_path, source_region = path, region
                if region != (0, 0, 1, 1):
                    with Image.open(path) as image:
                        box = (int(region[0] * width), int(region[1] * height),
                               math.ceil(region[2] * width), math.ceil(region[3] * height))
                        if box[2] - box[0] < 32 or box[3] - box[1] < 32:
                            notes.append('visual_region_too_small_for_ocr')
                            continue
                        source_region = (box[0] / width, box[1] / height, box[2] / width, box[3] / height)
                        crop = image.crop(box)
                        try:
                            input_path = root / f'{identity}-region-{region_index}.png'
                            crop.save(input_path, format='PNG')
                        finally:
                            crop.close()
                region_lines, region_notes, orientation = transcribe(input_path, recipe, root=root,
                    executable=executable, directory=directory, identity=f'{identity}-region-{region_index}', source_region=source_region)
                lines.extend(region_lines)
                notes.extend(region_notes)
            diagnostics.extend(f'page:{index}:{note}' if is_pdf else note for note in notes)
            if is_pdf and not native_text:
                pages[index] = replace(pages[index], status='needs_ocr', diagnostics=tuple(notes))
            if not lines:
                missing += 1
                continue
            for ordinal, (text, box, data) in enumerate(lines):
                identity_text = f'{revision.sha256}:{identity}:{ordinal}:{text}'
                block_id = 'block-' + hashlib.sha256(identity_text.encode()).hexdigest()[:24]
                coordinates = {'block_id': block_id, 'char_start': 0, 'char_end': len(text), 'char_space': 'canonical_block_text'}
                if is_pdf:
                    coordinates.update(page_index=index, page_number=index + 1, bbox=box)
                else:
                    coordinates['image_bbox'] = box
                blocks.append(DocumentBlock(block_id, 'paragraph', text, Locator(**coordinates),
                    extraction_method='ocr', data_json=data, asset_ids=(asset.id,)))
                if len(blocks) > recipe.limits.max_blocks:
                    raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Document OCR exceeds its canonical block limit')
            if is_pdf:
                pages[index] = replace(pages[index], status='mixed' if native_text else 'ocr',
                    text_characters=(pages[index].text_characters if native_text else 0) + sum(len(line[0]) for line in lines),
                    diagnostics=tuple(notes))
                diagnostics = [note for note in diagnostics if note not in {
                    f'page:{index}:image_page_needs_ocr', f'page:{index}:no_extractable_text'}]
            if len(blocks) > recipe.limits.max_blocks:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Document OCR exceeds its canonical block limit')
    finally:
        if document is not None:
            document.close()
    if assets:
        diagnostics.append('source_visuals_preserved_not_semantically_interpreted')
    if not any(block.text.strip() for block in blocks):
        coverage = Coverage.NEEDS_OCR if assets else Coverage.UNSUPPORTED
    elif assets or diagnostics or missing:
        coverage = Coverage.PARTIAL
    else:
        coverage = Coverage.COMPLETE
    if len(blocks) > recipe.limits.max_blocks:
        raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Document exceeds its canonical block limit')
    (root / 'assets.json').write_text(json.dumps(entries))
    return CanonicalDocument(native.revision, tuple(blocks), coverage, tuple(sorted(set(diagnostics))),
        source_size_bytes=revision.size_bytes, page_count=native.page_count, pages=tuple(pages), assets=tuple(assets))
