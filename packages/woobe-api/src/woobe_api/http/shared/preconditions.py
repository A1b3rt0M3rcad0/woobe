from __future__ import annotations

import re
from uuid import UUID

from fastapi import HTTPException, Request


def expected_revision(request: Request, *, kind: str, resource_id: UUID) -> int:
    values = request.headers.getlist("if-match")
    value = values[0] if len(values) == 1 else None
    if not values:
        raise HTTPException(428, detail={"code": "PRECONDITION_REQUIRED", "message": "If-Match is required"})
    if value is None:
        raise HTTPException(412, detail={"code": "PRECONDITION_FAILED", "message": "Exactly one If-Match value is required"})
    match = re.fullmatch(r'"' + re.escape(f"{kind}:{resource_id}:") + r'([1-9][0-9]{0,9})"', value)
    if match is None or int(match.group(1)) > 2_147_483_647:
        raise HTTPException(412, detail={"code": "PRECONDITION_FAILED", "message": "A strong ETag for this resource is required"})
    return int(match.group(1))


def assignment_revision(request: Request, *, assignment_id: UUID) -> int:
    values = request.headers.getlist("if-none-match")
    if values:
        if values != ["*"] or request.headers.getlist("if-match"):
            raise HTTPException(412, detail={"code": "PRECONDITION_FAILED",
                "message": "Assignment creation requires only If-None-Match: *"})
        return 0
    return expected_revision(request, kind="assignment", resource_id=assignment_id)
