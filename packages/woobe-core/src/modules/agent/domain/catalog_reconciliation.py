"""Stable catalog evidence digests and revision conflict diagnostics."""

import hashlib
import json

from shared.contracts.errors import ConflictError


def catalog_digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


def reconciliation_conflict(code, message):
    error = ConflictError(message)
    error.code = code
    raise error
