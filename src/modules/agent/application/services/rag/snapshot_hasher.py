from __future__ import annotations

import hashlib
import json
from typing import Any


def compute_snapshot_hash(*, documents: list[dict[str, Any]], parameters: dict[str, Any]) -> str:
    payload = {
        "documents": sorted(documents, key=lambda item: str(item.get("document_id"))),
        "parameters": parameters,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
