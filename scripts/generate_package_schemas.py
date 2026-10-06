#!/usr/bin/env python3
"""Generate the canonical public Package 1.0 schemas; --check detects drift."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from modules.package.application.dtos import DOCUMENT_MODELS


def strict_objects(value):
    if isinstance(value, dict):
        if value.get("type") == "object" and "properties" in value:
            value["additionalProperties"] = False
        for child in value.values():
            strict_objects(child)
    elif isinstance(value, list):
        for child in value:
            strict_objects(child)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    target = root / "specs/package/v1"
    catalog = {}
    for kind, model in DOCUMENT_MODELS.items():
        schema = model.model_json_schema(by_alias=True)
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        strict_objects(schema)
        catalog[kind] = schema
    data = (
        json.dumps(catalog, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()
    outputs = {
        target / "catalog.json": data,
        target / "catalog.sha256": (sha256(data).hexdigest() + "\n").encode(),
        root
        / "packages/woobe-core/src/modules/package/domain/schemas/catalog.json": data,
    }
    for path, contents in outputs.items():
        if args.check:
            if not path.exists() or path.read_bytes() != contents:
                raise SystemExit(f"Package schema drift: {path.relative_to(root)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(contents)


if __name__ == "__main__":
    main()
