from dataclasses import dataclass
import re

from modules.artifacts.domain.models import ArtifactError


ALIASES = {'utf-8': 'utf-8', 'utf8': 'utf-8', 'utf-8-sig': 'utf-8',
           'utf-16': 'utf-16', 'utf16': 'utf-16', 'utf-16le': 'utf-16-le',
           'utf-16-le': 'utf-16-le', 'utf-16be': 'utf-16-be', 'utf-16-be': 'utf-16-be',
           'latin-1': 'latin-1', 'latin1': 'latin-1', 'iso-8859-1': 'latin-1'}


@dataclass(frozen=True)
class DecodedSource:
    text: str
    encoding: str
    bom_bytes: int


def text_encoding(prefix: bytes, content_type: str, requested='auto'):
    charsets = re.findall(r'(?:^|;)\s*charset\s*=\s*"?([^;"\s]+)', content_type, re.IGNORECASE)
    if len(charsets) > 1:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Text content has conflicting charset declarations')
    declared = ALIASES.get(charsets[0].lower()) if charsets else None
    if charsets and declared is None:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Declared text charset is unsupported')
    detected, skip = None, 0
    for mark, codec in ((b'\xef\xbb\xbf', 'utf-8'), (b'\xff\xfe', 'utf-16-le'), (b'\xfe\xff', 'utf-16-be')):
        if prefix.startswith(mark):
            detected, skip = codec, len(mark)
            break
    selected = declared if requested == 'auto' else ALIASES.get(requested)
    if requested != 'auto' and selected is None:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Requested text encoding is unsupported')
    if detected:
        if selected is not None and selected != detected and not (selected == 'utf-16' and detected.startswith('utf-16-')):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Text encoding conflicts with its byte order mark')
        return detected, skip
    if selected == 'utf-16':
        if declared in {'utf-16-le', 'utf-16-be'}:
            return declared, 0
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'UTF-16 text requires a byte order or declared endian charset')
    return selected or 'utf-8', 0


def decode_source(content: bytes, content_type: str, requested='auto'):
    encoding, skip = text_encoding(content, content_type, requested)
    try:
        text = content[skip:].decode(encoding, errors='strict')
    except UnicodeError as error:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Original text is invalid for its selected encoding') from error
    if '\x00' in text:
        raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Text contains unsupported NUL characters')
    return DecodedSource(text, encoding, skip)
