from dataclasses import dataclass
from decimal import Decimal
import csv
import hashlib
import io
import json
import re

from markdown_it import MarkdownIt

from modules.artifacts.application.contracts.processing import ProcessingRecipe
from modules.artifacts.domain.models import ArtifactError, ArtifactRef, CanonicalDocument, Coverage, DocumentBlock, Locator, Revision
from modules.artifacts.domain.text_encoding import decode_source
from modules.artifacts.infra.processing.native_registry import MEDIA_TYPES
from shared.infra.object_storage.io import run_blocking


CSV_MAX_FIELD_CHARS = 131_072


@dataclass(frozen=True)
class SourceLine:
    number: int
    char_start: int
    byte_start: int
    text: str


class TextSource:
    def __init__(self, content, revision, recipe):
        decoded = decode_source(content, revision.content_type, recipe.parameters.encoding)
        self.text, self.encoding, self.bom = decoded.text, decoded.encoding, decoded.bom_bytes
        self.content_size, self.revision, self.recipe = len(content), revision, recipe
        self.lines = []
        byte_start = self.bom
        for match in re.finditer(r'[^\r\n]*(?:\r\n|\r|\n|$)', self.text):
            if match.start() == match.end():
                continue
            if len(self.lines) >= min(200_000, recipe.limits.max_blocks * 4):
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Document exceeds the bounded source-line limit')
            line = match.group()
            if len(line.rstrip('\r\n')) > recipe.parameters.max_line_chars:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Document exceeds its source-line character limit')
            self.lines.append(SourceLine(len(self.lines) + 1, match.start(), byte_start, line))
            byte_start += len(line.encode(self.encoding))
        if byte_start != len(content):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Decoded source byte mapping is inconsistent')

    def block(self, kind, start, stop, **metadata):
        first, last = self.lines[start], self.lines[stop - 1]
        begin, end = first.char_start, last.char_start + len(last.text)
        text = self.text[begin:end].replace('\r\n', '\n').replace('\r', '\n')
        identity = hashlib.sha256(f'{self.revision.sha256}:{kind}:{begin}:{end}'.encode()).hexdigest()[:24]
        locator = Locator(block_id='block-' + identity, line_start=first.number,
            line_end=last.number + 1, char_start=begin, char_end=end,
            byte_start=first.byte_start, byte_end=last.byte_start + len(last.text.encode(self.encoding)),
            source_encoding=self.encoding, text_normalization='lf')
        return DocumentBlock('block-' + identity, kind, text, locator, **metadata)

    def document(self, blocks, diagnostics=()):
        if len(blocks) > self.recipe.limits.max_blocks:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Document exceeds its canonical block limit')
        return CanonicalDocument(ArtifactRef(self.revision.artifact_id, self.revision.id), tuple(blocks),
            Coverage.COMPLETE if blocks else Coverage.UNSUPPORTED,
            tuple(diagnostics) if blocks else tuple(diagnostics) + ('empty_document',),
            source_encoding=self.encoding, source_size_bytes=self.content_size,
            source_character_count=len(self.text), text_normalization='lf')


def _plain(source):
    blocks, start = [], None
    for index, line in enumerate(source.lines):
        if line.text.strip():
            if start is None:
                start = index
        else:
            if start is not None:
                blocks.append(source.block('paragraph', start, index))
                start = None
            if source.recipe.parameters.preserve_blank_lines:
                blocks.append(source.block('paragraph', index, index + 1))
    if start is not None:
        blocks.append(source.block('paragraph', start, len(source.lines)))
    if not source.text.strip():
        return source.document(())
    return source.document(blocks)


def _inline_text(token):
    return ''.join(child.content if child.type in {'text', 'code_inline', 'image'} else '\n'
        if child.type in {'softbreak', 'hardbreak'} else '' for child in token.children or ())


def _markdown(source):
    if not source.text.strip():
        return source.document(())
    parser = MarkdownIt('commonmark', {'html': False, 'maxNesting': 20})
    tokens = parser.parse(source.text)
    if len(tokens) > source.recipe.limits.max_blocks * 32:
        raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Markdown exceeds its structural token limit')
    blocks, covered, diagnostics = [], set(), []
    kinds = {'heading_open': 'heading', 'paragraph_open': 'paragraph', 'fence': 'code',
             'code_block': 'code', 'bullet_list_open': 'list', 'ordered_list_open': 'list',
             'blockquote_open': 'paragraph', 'hr': 'paragraph'}
    for index, token in enumerate(tokens):
        if token.level != 0 or token.map is None or token.type not in kinds:
            continue
        start, stop = token.map
        covered.update(range(start, stop))
        metadata = {}
        if token.type == 'heading_open':
            level = int(token.tag[1:])
            if level > source.recipe.parameters.max_heading_depth:
                diagnostics.append('heading_depth_limit_preserved_as_paragraph')
                kind = 'paragraph'
            else:
                kind = 'heading'
                title = _inline_text(tokens[index + 1])
                metadata.update(heading_level=level, title=title[:512])
                if len(title) > 512:
                    diagnostics.append('heading_display_title_truncated')
        else:
            kind = kinds[token.type]
        if kind == 'code':
            language = token.info.strip().split(maxsplit=1)[0] if token.info.strip() else None
            metadata['language'] = language if language and re.fullmatch(r'[A-Za-z0-9_+.-]{1,64}', language) else None
        if kind == 'list':
            selected = []
            for child in tokens[index:]:
                if child is not token and child.level == 0:
                    if child.type in {'bullet_list_close', 'ordered_list_close'}:
                        selected.append({'type': child.type, 'tag': child.tag, 'nesting': child.nesting,
                                         'level': child.level, 'lines': child.map, 'content': child.content})
                    break
                selected.append({'type': child.type, 'tag': child.tag, 'nesting': child.nesting,
                                 'level': child.level, 'lines': child.map, 'content': child.content})
            metadata['data_json'] = json.dumps({'format': 'commonmark-list', 'tokens': selected}, ensure_ascii=False)
        blocks.append(source.block(kind, start, stop, **metadata))
    # Reference definitions and syntax outside recognized top-level blocks remain
    # literal source data. They cannot vanish or become fake inferred chapters.
    for index, line in enumerate(source.lines):
        if index not in covered and (line.text.strip() or source.recipe.parameters.preserve_blank_lines):
            blocks.append(source.block('paragraph', index, index + 1))
            if line.text.strip():
                diagnostics.append('markdown_unmapped_source_preserved')
    blocks.sort(key=lambda block: block.locator.char_start)
    return source.document(blocks, sorted(set(diagnostics)))


def _json_preflight(text, recipe):
    depth, nodes, quoted, escaped = 0, 0, False, False
    for char in text:
        if quoted:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
            nodes += 1
        elif char in '[{':
            depth += 1
            nodes += 1
            if depth > recipe.parameters.json_max_depth:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'JSON exceeds its nesting limit')
        elif char in ']}':
            depth -= 1
        elif char in ',:':
            nodes += 1
        if nodes > recipe.limits.max_blocks * 16:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'JSON exceeds its structural item limit')


def _json(source):
    if not source.text.strip():
        return source.document(())
    _json_preflight(source.text, source.recipe)

    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError('Duplicate JSON keys are ambiguous')
            value[key] = item
        return value

    def reject_constant(value):
        raise ValueError('JSON constants must be finite numeric literals')

    try:
        json.loads(source.text, parse_int=Decimal, parse_float=Decimal,
                   parse_constant=reject_constant, object_pairs_hook=pairs)
    except (ValueError, RecursionError) as error:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Original JSON is invalid or ambiguous') from error
    # Preserve exact numeric/string tokens instead of coercing arbitrary precision
    # numbers through binary floats. The tagged payload is still valid JSON data.
    data = source.text.replace('\r\n', '\n').replace('\r', '\n')
    return source.document([source.block('json', 0, len(source.lines), data_json=data)])


def _csv(source):
    if not source.text.strip():
        return source.document(())
    reader = csv.reader(io.StringIO(source.text, newline=''), dialect=source.recipe.parameters.csv_dialect, strict=True)
    rows = []
    try:
        for row in reader:
            if len(rows) >= source.recipe.limits.max_blocks:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'CSV exceeds its row limit')
            if len(row) > source.recipe.parameters.csv_max_columns:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'CSV exceeds its column limit')
            if any(len(cell) > min(CSV_MAX_FIELD_CHARS, source.recipe.parameters.max_line_chars) for cell in row):
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'CSV exceeds its cell character limit')
            if rows and len(row) != len(rows[0]):
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'CSV rows have inconsistent column counts')
            rows.append(row)
    except csv.Error as error:
        if str(error).startswith('field larger than field limit'):
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'CSV exceeds the adapter field-size limit') from error
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Original CSV is invalid or exceeds the adapter field limit') from error
    if not rows or not rows[0]:
        return source.document(())
    data = json.dumps({'format': 'csv', 'header_policy': 'first_row', 'columns': rows[0],
                       'rows': rows[1:], 'dialect': source.recipe.parameters.csv_dialect}, ensure_ascii=False)
    return source.document([source.block('table', 0, len(source.lines), data_json=data)])


class NativeTextProcessor:
    name, version = 'native-text', '1'
    media_types = MEDIA_TYPES

    async def process(self, revision: Revision, content, profile: ProcessingRecipe):
        if revision.size_bytes > profile.limits.max_bytes:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Original exceeds the text processor byte limit')
        buffer, digest = bytearray(), hashlib.sha256()
        try:
            async for chunk in content:
                if not isinstance(chunk, bytes) or len(buffer) + len(chunk) > min(revision.size_bytes, profile.limits.max_bytes):
                    raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Original text stream exceeds its expected size')
                buffer.extend(chunk)
                digest.update(chunk)
        finally:
            close = getattr(content, 'aclose', None)
            if close is not None:
                await close()
        if len(buffer) != revision.size_bytes or digest.hexdigest() != revision.sha256:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Original text stream failed integrity verification')
        media = revision.content_type.split(';', 1)[0].strip().lower()
        if media not in MEDIA_TYPES:
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Native text processor does not support this media type')
        return await run_blocking(self._parse, bytes(buffer), revision, profile, media)

    @staticmethod
    def _parse(content, revision, profile, media):
        source = TextSource(content, revision, profile)
        if media in {'text/markdown', 'text/x-markdown'}:
            return _markdown(source)
        if media in {'application/json', 'text/json'}:
            return _json(source)
        if media in {'text/csv', 'application/csv'}:
            return _csv(source)
        return _plain(source)
