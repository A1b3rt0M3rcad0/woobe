"""Scoped, immutable revision metadata traversal under owner authorization."""

import base64
import hmac
import json
from hashlib import sha256

from sqlalchemy import select, text

from shared.contracts.asac_requests import ASaCRevision
from shared.contracts.errors import ConflictError, ValidationError
from shared.infra.asac_history_reader import _bound, _position


class ASaCRevisionCatalog:
    def __init__(self, store, cursor_key):
        self.store = store
        self.key = cursor_key.encode() if isinstance(cursor_key, str) else cursor_key

    async def fetch(
        self, *, project_id, resource_id, principal, cursor=None, limit=100
    ):
        if not self.key:
            raise RuntimeError("Revision cursor signing key is required")
        if not 1 <= limit <= 200:
            raise ValidationError(
                "ASAC_REVISION_LIMIT: limit must be between 1 and 200"
            )
        scope = [str(project_id), self.store.kind, str(resource_id), "revisions"]
        token = None
        if cursor:
            try:
                if len(cursor) > 2048:
                    raise ValueError("oversized cursor")
                payload, signature = cursor.rsplit(".", 1)
                expected = hmac.new(self.key, payload.encode(), sha256).hexdigest()
                if not hmac.compare_digest(expected, signature):
                    raise ValueError("invalid signature")
                token = json.loads(
                    base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
                )
                if (
                    set(token) != {"scope", "watermark", "after"}
                    or token["scope"] != scope
                ):
                    raise ValueError("invalid scope")
                # Parse/validate both positions before opening an owner scope.
                _bound(self.store.revisions, token["watermark"], after=False)
                _bound(self.store.revisions, token["after"], after=True)
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                raise ValidationError(
                    "ASAC_REVISION_CURSOR_INVALID: cursor differs from this resource"
                ) from exc
        model = self.store.revisions
        async with self.store._read() as session:
            if session.bind.dialect.name == "postgresql":
                await session.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                )
            await self.store._authorize(session, project_id, resource_id, principal)
            query = select(model).where(
                model.project_id == project_id, model.resource_id == resource_id
            )
            latest = await session.scalar(
                query.order_by(model.created_at.desc(), model.id.desc()).limit(1)
            )
            watermark = (
                token["watermark"] if token else _position(latest) if latest else None
            )
            if watermark:
                query = query.where(_bound(model, watermark, after=False))
            if token:
                query = query.where(_bound(model, token["after"], after=True))
            rows = (
                await session.scalars(
                    query.order_by(model.created_at, model.id).limit(limit + 1)
                )
            ).all()
            has_more, rows = len(rows) > limit, rows[:limit]
            records = []
            for row in rows:
                try:
                    record = ASaCRevision.model_validate(row.document).model_dump(
                        exclude_none=True
                    )
                    if (
                        record["kind"] != self.store.kind
                        or record["revision_id"] != row.revision_id
                        or record["resource_uid"] != str(row.resource_uid)
                    ):
                        raise ValueError("stored identity mismatch")
                except (ValueError, TypeError) as exc:
                    raise ConflictError(
                        "ASAC_INTEGRITY_CONFLICT: retained revision metadata is inconsistent"
                    ) from exc
                records.append(
                    {
                        "record": record,
                        "artifact_id": str(row.artifact_id),
                        "author_artifact_status": "declared_not_retained"
                        if record.get("author_artifact_digest")
                        else "unavailable",
                    }
                )
            next_cursor = None
            if has_more:
                token = {
                    "scope": scope,
                    "watermark": watermark,
                    "after": _position(rows[-1]),
                }
                payload = (
                    base64.urlsafe_b64encode(
                        json.dumps(token, separators=(",", ":")).encode()
                    )
                    .decode()
                    .rstrip("=")
                )
                next_cursor = (
                    payload
                    + "."
                    + hmac.new(self.key, payload.encode(), sha256).hexdigest()
                )
            return {
                "schema_version": "1.0",
                "kind": self.store.kind,
                "resource_id": str(resource_id),
                "stream": "revisions",
                "records": records,
                "watermark": watermark,
                "next_cursor": next_cursor,
                "has_more": has_more,
                "complete": not has_more,
                "coverage": "authorized_resource_metadata",
                "objects_available": "not_evaluated",
            }
