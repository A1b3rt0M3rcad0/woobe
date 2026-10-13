"""Canonical Contract schema identity, independent of native presentation defaults."""

from hashlib import sha256
import json


def contract_schema_hash(input_schema, output_schema):
    return sha256(
        json.dumps(
            {"input_schema": input_schema or {}, "output_schema": output_schema or {}},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
