import base64
import hashlib
import hmac
import json

from modules.artifacts.application.contracts.api import CursorEnvelope
from modules.artifacts.domain.models import ArtifactError


class CursorCodec:
    def __init__(self, secret: bytes):
        if len(secret) < 32:
            raise ValueError('Cursor signing needs an environment secret of at least 32 bytes')
        self._key = hmac.digest(secret, b'woobe:artifacts:cursor:v1', 'sha256')

    @staticmethod
    def fingerprint(context: dict) -> str:
        return hashlib.sha256(json.dumps(context, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

    def encode(self, cursor: CursorEnvelope) -> str:
        data = cursor.model_dump_json().encode()
        signature = hmac.digest(self._key, data, 'sha256')
        return '.'.join(base64.urlsafe_b64encode(part).decode().rstrip('=') for part in (data, signature))

    def decode(self, token: str, *, fingerprint: str, purpose: str) -> CursorEnvelope:
        try:
            if len(token) > 4096:
                raise ValueError('Cursor too long')
            parts = token.split('.')
            if len(parts) != 2:
                raise ValueError('Invalid cursor')
            data, signature = (base64.b64decode(part + '=' * (-len(part) % 4), altchars=b'-_', validate=True) for part in parts)
            if not hmac.compare_digest(hmac.digest(self._key, data, 'sha256'), signature):
                raise ValueError('Invalid cursor signature')
            cursor = CursorEnvelope.model_validate_json(data)
            if cursor.scope_fingerprint != fingerprint or cursor.purpose != purpose:
                raise ValueError('Cursor belongs to a different query or principal')
            return cursor
        except (ValueError, TypeError) as error:
            raise ArtifactError('ARTIFACT_INVALID_CURSOR', 'Artifact cursor is invalid for this query') from error
