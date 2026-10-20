from dataclasses import asdict
import hashlib
import json
import math

from modules.artifacts.domain.models import ArtifactError, ArtifactRef, CanonicalDocument, Coverage, DocumentBlock, DocumentPage, Locator


CANONICAL_SCHEMA_VERSION = '1'


def canonical_value(document):
    return {'schema_version': CANONICAL_SCHEMA_VERSION, **asdict(document)}


def json_chunks(value):
    """Deterministic JSON without building a second whole-document string.

    String fragments have at most 8192 codepoints, keeping escaped UTF-8 chunks
    below 64 KiB even for control-character-heavy untrusted text.
    """
    if isinstance(value, str):
        yield b'"'
        for offset in range(0, len(value), 8192):
            yield json.dumps(value[offset:offset + 8192], ensure_ascii=False)[1:-1].encode('utf-8')
        yield b'"'
    elif isinstance(value, dict):
        yield b'{'
        for index, key in enumerate(sorted(value)):
            if not isinstance(key, str):
                raise ValueError('Canonical JSON object keys must be strings')
            if index:
                yield b','
            yield from json_chunks(key)
            yield b':'
            yield from json_chunks(value[key])
        yield b'}'
    elif isinstance(value, (list, tuple)):
        yield b'['
        for index, item in enumerate(value):
            if index:
                yield b','
            yield from json_chunks(item)
        yield b']'
    elif value is None or isinstance(value, (bool, int)):
        yield json.dumps(value).encode()
    elif isinstance(value, float) and math.isfinite(value):
        yield json.dumps(value, allow_nan=False).encode()
    else:
        raise ValueError('Unsupported canonical JSON value')


def serialized_identity(value, max_bytes):
    digest, size = hashlib.sha256(), 0
    for chunk in json_chunks(value):
        size += len(chunk)
        if size > max_bytes:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Canonical representation exceeds its byte limit')
        digest.update(chunk)
    return size, digest.hexdigest()


def decode_canonical(content):
    try:
        value = json.loads(content)
        if not isinstance(value, dict):
            raise ValueError('Canonical document must be an object')
        if value.pop('schema_version') != CANONICAL_SCHEMA_VERSION:
            raise ValueError('Unsupported canonical document version')
        revision = ArtifactRef(**value.pop('revision'))
        blocks = []
        for block in value.pop('blocks'):
            coordinates = block['locator']
            if coordinates.get('bbox') is not None:
                coordinates['bbox'] = tuple(coordinates['bbox'])
            block['locator'] = Locator(**coordinates)
            blocks.append(DocumentBlock(**block))
        value['diagnostics'] = tuple(value.get('diagnostics', ()))
        value['coverage'] = Coverage(value['coverage'])
        value['pages'] = tuple(DocumentPage(**{**page, 'diagnostics': tuple(page.get('diagnostics', ()))})
                               for page in value.get('pages', ()))
        return CanonicalDocument(revision, tuple(blocks), **value)
    except (KeyError, TypeError, ValueError, RecursionError) as error:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Stored canonical document is invalid') from error
