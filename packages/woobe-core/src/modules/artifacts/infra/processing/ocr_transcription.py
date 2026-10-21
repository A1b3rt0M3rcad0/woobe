import csv
import json
import math
import os
import re
import subprocess

from PIL import Image

from modules.artifacts.domain.models import ArtifactError


def inverse_box(box, rotation):
    left, top, right, bottom = box
    if rotation == 90:
        return top, 1 - right, bottom, 1 - left
    if rotation == 180:
        return 1 - right, 1 - bottom, 1 - left, 1 - top
    if rotation == 270:
        return 1 - bottom, left, 1 - top, right
    return box


def transcribe(path, recipe, *, root, executable, directory, identity, source_region=(0, 0, 1, 1)):
    languages = recipe.parameters.languages or ('por', 'eng')
    if any(language not in {'por', 'eng'} for language in languages):
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Requested OCR language is not installed in the qualified profile')
    environment = {**os.environ, 'TESSDATA_PREFIX': str(directory)}
    orientation = {'applied_rotation': 0, 'suggested_rotation': None, 'confidence': None}
    diagnostics = ['ocr_reading_order_unverified', 'ocr_transcription_not_visual_understanding']
    osd_output = root / (identity + '.osd')
    with osd_output.open('wb') as output:
        result = subprocess.run([str(executable), str(path), 'stdout', '-l', 'osd', '--psm', '0'],
            env=environment, stdout=output, stderr=subprocess.DEVNULL, timeout=15, check=False)
    if osd_output.stat().st_size > 16_384:
        raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'OCR orientation diagnostics exceed their byte limit')
    if result.returncode == 0:
        value = osd_output.read_text(encoding='utf-8')
        rotation = re.search(r'^Rotate: (0|90|180|270)$', value, re.MULTILINE)
        confidence = re.search(r'^Orientation confidence: ([0-9.]+)$', value, re.MULTILINE)
        if rotation and confidence:
            score = float(confidence.group(1))
            if math.isfinite(score):
                orientation.update(suggested_rotation=int(rotation.group(1)), confidence=score)
                if score >= 5:
                    orientation['applied_rotation'] = int(rotation.group(1))
    if orientation['confidence'] is None:
        diagnostics.append('ocr_orientation_unavailable')
    elif orientation['confidence'] < 5:
        diagnostics.append('ocr_orientation_low_confidence_not_applied')
    input_path = path
    with Image.open(path) as original:
        width, height = original.size
        if orientation['applied_rotation']:
            input_path = root / (identity + '-oriented.png')
            rotated = original.rotate(-orientation['applied_rotation'], expand=True)
            try:
                rotated.save(input_path, format='PNG')
                width, height = rotated.size
            finally:
                rotated.close()
    output_base = root / (identity + '-recognition')
    result = subprocess.run([str(executable), str(input_path), str(output_base), '-l', '+'.join(languages), '--psm', '3', '-c', 'tessedit_create_tsv=1'],
        env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=recipe.limits.timeout_seconds, check=False)
    if result.returncode != 0:
        diagnostics.append('ocr_engine_could_not_recognize_page')
        return [], diagnostics, orientation
    tsv = output_base.with_suffix('.tsv')
    if not tsv.is_file() or tsv.stat().st_size > 67_108_864:
        raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'OCR word output exceeds its byte limit')
    groups, words = {}, 0
    with tsv.open(encoding='utf-8', newline='') as source:
        for row in csv.DictReader(source, delimiter='\t', quoting=csv.QUOTE_NONE):
            if row['level'] != '5' or not row['text'].strip():
                continue
            words += 1
            if words > min(500_000, recipe.limits.max_blocks * 32):
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'OCR exceeds its word limit')
            left, top, box_width, box_height = (int(row[name]) for name in ('left', 'top', 'width', 'height'))
            if min(left, top, box_width, box_height) < 0 or left + box_width > width or top + box_height > height:
                raise ArtifactError('DOCUMENT_CONVERSION_FAILED', 'OCR returned invalid source-image coordinates')
            box = inverse_box((left / width, top / height, (left + box_width) / width,
                               (top + box_height) / height), orientation['applied_rotation'])
            region_left, region_top, region_right, region_bottom = source_region
            box = (region_left + box[0] * (region_right - region_left),
                   region_top + box[1] * (region_bottom - region_top),
                   region_left + box[2] * (region_right - region_left),
                   region_top + box[3] * (region_bottom - region_top))
            score = float(row['conf'])
            confidence = score if math.isfinite(score) and 0 <= score <= 100 else None
            if confidence is None:
                diagnostics.append('ocr_word_confidence_unavailable')
            elif confidence < 50:
                diagnostics.append('ocr_low_confidence_words')
            key = tuple(row[name] for name in ('block_num', 'par_num', 'line_num'))
            groups.setdefault(key, []).append({'text': row['text'], 'confidence': confidence, 'bbox': box})
    lines = []
    for entries in groups.values():
        text = ' '.join(word['text'] for word in entries)
        if len(text) > recipe.parameters.max_line_chars or len(lines) >= recipe.limits.max_blocks:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'OCR exceeds its line or block limit')
        box = (min(word['bbox'][0] for word in entries), min(word['bbox'][1] for word in entries),
               max(word['bbox'][2] for word in entries), max(word['bbox'][3] for word in entries))
        data = json.dumps({'format': 'tesseract-tsv-line', 'engine': 'tesseract', 'engine_version': '5.5.0',
            'languages': list(languages), 'orientation': orientation, 'words': entries,
            'source_region_bbox': source_region, 'bbox_space': 'source_visual_normalized',
            'confidence_semantics': 'uncalibrated_engine_reported_word_scores'}, ensure_ascii=False)
        lines.append((text, box, data))
    if not lines:
        diagnostics.append('ocr_no_text_recognized')
    return lines, sorted(set(diagnostics)), orientation
