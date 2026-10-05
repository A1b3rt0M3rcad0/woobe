from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, Request


def expected_revision(request: Request, *, kind: str, resource_id: UUID) -> int:
    value = request.headers.get("if-match")
    if value is None:
        raise HTTPException(428, detail={"code": "PRECONDITION_REQUIRED", "message": "If-Match is required"})
    match = re.fullmatch(r'"' + re.escape(f"{kind}:{resource_id}:") + r'([1-9][0-9]{0,9})"', value)
    if match is None or int(match.group(1)) > 2_147_483_647:
        raise HTTPException(412, detail={"code": "PRECONDITION_FAILED", "message": "A strong ETag for this resource is required"})
    return int(match.group(1))
