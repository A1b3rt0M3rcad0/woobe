import hashlib
import json
from pathlib import Path

import pytest

from modules.artifacts.application.contracts.processing import ComponentReference, ProcessingRecipe
from modules.artifacts.application.document_codec import canonical_value, decode_canonical, json_chunks, serialized_identity
from modules.artifacts.domain.models import ArtifactError, Coverage, Revision
from modules.artifacts.infra.processing.native_text import NativeTextProcessor


async def extract(content, media='text/plain', **options):
    revision = Revision('revision', 'artifact', 'objects/original', media, len(content),
                        hashlib.sha256(content).hexdigest(), 'upload')
    recipe = ProcessingRecipe(mode='extract', processor=ComponentReference(name='native-text', version='1'), **options)
    async def stream():
        for offset in range(0, len(content), 3):
            yield content[offset:offset + 3]
    return await NativeTextProcessor().process(revision, stream(), recipe)


@pytest.mark.asyncio
@pytest.mark.parametrize('encoding,bom,media', [
    ('utf-8', b'', 'text/plain'), ('utf-8', b'\xef\xbb\xbf', 'text/plain'),
    ('utf-16-le', b'\xff\xfe', 'text/plain'), ('utf-16-be', b'\xfe\xff', 'text/plain'),
    ('latin-1', b'', 'text/plain; charset=iso-8859-1'),
])
async def test_original_byte_ranges_and_unicode_offsets_survive_encoding_and_crlf(encoding, bom, media):
    original = 'Olá, ação!\r\nSegunda linha.\r\n\r\nÚltimo parágrafo.\n'
    content = bom + original.encode(encoding)
    document = await extract(content, media)
    assert document.coverage == Coverage.COMPLETE
    assert document.page_count is None and document.trust_level == 'untrusted_source'
    assert document.source_character_count == len(original)
    for block in document.blocks:
        locator = block.locator
        raw = content[locator.byte_start:locator.byte_end].decode(encoding)
        assert raw == original[locator.char_start:locator.char_end]
        assert block.text == raw.replace('\r\n', '\n')
        assert locator.page_index is None and locator.page_number is None
    assert decode_canonical(b''.join(json_chunks(canonical_value(document)))) == document


@pytest.mark.asyncio
async def test_markdown_golden_structure_preserves_repeated_headings_code_and_nested_lists():
    fixtures = Path(__file__).resolve().parents[2] / 'fixtures/artifacts/native-text'
    content = (fixtures / 'portuguese.md').read_bytes()
    document = await extract(content, 'text/markdown', parameters={'preserve_blank_lines': False})
    assert [[b.kind, b.heading_level, b.title, b.language, b.locator.line_start, b.locator.line_end]
            for b in document.blocks] == json.loads((fixtures / 'portuguese.structure.json').read_text())
    assert document.blocks[0].id != document.blocks[-1].id
    assert json.loads(document.blocks[1].data_json)['tokens'][-1]['type'] == 'bullet_list_close'
    assert document == await extract(content, 'text/markdown', parameters={'preserve_blank_lines': False})
    for block in document.blocks:
        assert content[block.locator.byte_start:block.locator.byte_end].decode().replace('\r\n', '\n') == block.text


@pytest.mark.asyncio
async def test_json_precision_and_remote_references_remain_literal_data():
    content = b'{"amount":12345678901234567890.123456789,"$ref":"https://invalid.example/private"}'
    document = await extract(content, 'application/json')
    assert document.blocks[0].kind == 'json'
    assert document.blocks[0].data_json == content.decode()
    assert len(document.blocks) == 1


@pytest.mark.asyncio
async def test_csv_quoted_newlines_and_header_only_table():
    document = await extract('nome,nota\r\nJoão,"duas\r\nlinhas"\r\n'.encode(), 'text/csv')
    data = json.loads(document.blocks[0].data_json)
    assert data['columns'] == ['nome', 'nota']
    assert data['rows'] == [['João', 'duas\r\nlinhas']]
    empty_table = await extract(b'nome,nota\n', 'text/csv')
    assert json.loads(empty_table.blocks[0].data_json)['rows'] == []


@pytest.mark.asyncio
@pytest.mark.parametrize('content,media,options', [
    (b'\xff', 'text/plain', {}), (b'a\x00b', 'text/plain', {}),
    (b'{"a":1,"a":2}', 'application/json', {}), (b'{"a":NaN}', 'application/json', {}),
    (b'[[[1]]]', 'application/json', {'parameters': {'json_max_depth': 2}}),
    (b'a,b\n1\n', 'text/csv', {}), (b'a,b\n1,2', 'text/csv', {'parameters': {'csv_max_columns': 1}}),
    (b'too long', 'text/plain', {'parameters': {'max_line_chars': 3}}),
])
async def test_invalid_or_over_budget_sources_fail_explicitly(content, media, options):
    with pytest.raises(ArtifactError):
        await extract(content, media, **options)


@pytest.mark.asyncio
@pytest.mark.parametrize('media', ['text/plain', 'text/markdown', 'application/json', 'text/csv'])
async def test_empty_sources_never_claim_complete_coverage(media):
    document = await extract(b' \r\n', media)
    assert document.coverage == Coverage.UNSUPPORTED
    assert document.blocks == () and 'empty_document' in document.diagnostics


def test_canonical_stream_encoding_is_bounded_and_hash_matches_actual_bytes():
    value = {'text': '\x01🐍"\\' * 40_000}
    chunks = list(json_chunks(value))
    content = b''.join(chunks)
    assert max(map(len, chunks)) <= 65_536
    assert json.loads(content) == value
    assert serialized_identity(value, len(content)) == (len(content), hashlib.sha256(content).hexdigest())
    with pytest.raises(ArtifactError):
        serialized_identity(value, len(content) - 1)


@pytest.mark.asyncio
async def test_embedded_html_scripts_and_remote_images_are_untrusted_literal_data(monkeypatch):
    import socket
    def forbidden(*args, **kwargs):
        raise AssertionError('Native parsing must never fetch remote content')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    content = b'<script>throw new Error("run me")</script>\n\n![remote](https://invalid.example/image.png)\n'
    document = await extract(content, 'text/markdown')
    assert document.trust_level == 'untrusted_source'
    assert '<script>' in ''.join(block.text for block in document.blocks)
    assert 'https://invalid.example/image.png' in ''.join(block.text for block in document.blocks)


@pytest.mark.asyncio
async def test_integrity_failure_always_closes_original_stream():
    closed = []
    async def content():
        try:
            yield b'wrong'
        finally:
            closed.append(True)
    revision = Revision('r', 'a', 'original', 'text/plain', 5, hashlib.sha256(b'right').hexdigest(), 'upload')
    recipe = ProcessingRecipe(mode='extract', processor=ComponentReference(name='native-text', version='1'))
    with pytest.raises(ArtifactError):
        await NativeTextProcessor().process(revision, content(), recipe)
    assert closed == [True]
