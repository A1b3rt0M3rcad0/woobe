"""Bounded read-only history projections, parameterized by domain-owned models.

No lifecycle mutation or cross-domain model ownership lives here.
"""
import base64
from datetime import UTC, datetime
import json
import hmac
from hashlib import sha256
from uuid import UUID

from sqlalchemy import and_, or_, select, text

from shared.contracts.asac import asac_digest
from shared.contracts.errors import NotFoundError, ValidationError


def _utc(value):
    return value.replace(tzinfo=value.tzinfo or UTC).isoformat()


def _position(row):
    return [_utc(row.created_at), str(row.id)]


def _bound(model, value, *, after):
    time, identifier = datetime.fromisoformat(value[0]), UUID(value[1])
    compare = model.created_at > time if after else model.created_at < time
    ids = model.id > identifier if after else model.id <= identifier
    return or_(compare, and_(model.created_at == time, ids))


class ASaCHistoryReader:
    def __init__(self, sessions, *, kind, root, release, activation, owner,
                 resource_column, release_kind, render_release, render_activation, cursor_key):
        self.sessions, self.kind, self.root = sessions, kind, root
        self.release, self.activation, self.owner = release, activation, owner
        self.resource_column, self.release_kind = resource_column, release_kind
        self.render_release, self.render_activation = render_release, render_activation
        if not cursor_key:
            raise ValueError("History cursor signing key is required")
        self.cursor_key = cursor_key.encode() if isinstance(cursor_key, str) else cursor_key

    async def fetch(self, *, project_id, resource_id, principal, stream="releases",
                    cursor=None, limit=100):
        if stream not in {"releases", "deployments"} or not 1 <= limit <= 200:
            raise ValidationError("Invalid history stream or limit")
        scope = [str(project_id), self.kind, str(resource_id), stream]
        token = None
        if cursor:
            try:
                if len(cursor) > 2048:
                    raise ValueError("cursor exceeds bound")
                payload, signature = cursor.rsplit(".", 1)
                expected = hmac.new(self.cursor_key, payload.encode(), sha256).hexdigest()
                if not hmac.compare_digest(expected, signature):
                    raise ValueError("cursor signature mismatch")
                token = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
                if token["scope"] != scope or set(token) != {"scope", "after", "watermark"}:
                    raise ValueError("cursor scope mismatch")
                for position in (token["after"], token["watermark"]):
                    datetime.fromisoformat(position[0]); UUID(position[1])
            except (ValueError, TypeError, KeyError, IndexError) as exc:
                raise ValidationError("History cursor is invalid for this resource") from exc
        model = self.release if stream == "releases" else self.activation
        async with self.sessions.begin() as session:
            if session.bind.dialect.name == "postgresql":
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            await self.owner.inspect(session, project_id=project_id, principal=principal,
                                     kind=self.kind, resource_id=resource_id)
            conditions = [model.project_id == project_id,
                          getattr(model, self.resource_column) == resource_id]
            if stream == "releases":
                column, value = self.release_kind
                conditions.append(getattr(model, column) == value)
            query = select(model).where(*conditions)
            latest = await session.scalar(query.order_by(model.created_at.desc(), model.id.desc()).limit(1))
            watermark = token["watermark"] if token else _position(latest) if latest else None
            if watermark:
                query = query.where(_bound(model, watermark, after=False))
            if token:
                query = query.where(_bound(model, token["after"], after=True))
            rows = (await session.scalars(query.order_by(model.created_at, model.id).limit(limit + 1))).all()
            has_more, rows = len(rows) > limit, rows[:limit]
            render = self.render_release if stream == "releases" else self.render_activation
            records = []
            for row in rows:
                record = {"format": "woobe-history-receipt", "schema_version": "1.0",
                          "kind": self.kind, "stream": stream, "project_id": str(project_id),
                          "resource_id": str(resource_id), "id": str(row.id),
                          "created_at": _utc(row.created_at), "origin_status": "unknown_origin",
                          **render(row)}
                record["record_digest"] = asac_digest("history-receipt", record)
                records.append(record)
            next_cursor = None
            if has_more:
                value = {"scope": scope, "watermark": watermark, "after": _position(rows[-1])}
                payload = base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).decode().rstrip("=")
                next_cursor = payload + "." + hmac.new(self.cursor_key, payload.encode(), sha256).hexdigest()
            return {"schema_version": "1.0", "resource_id": str(resource_id), "kind": self.kind,
                    "stream": stream, "records": records, "watermark": watermark,
                    "next_cursor": next_cursor, "has_more": has_more, "complete": not has_more,
                    "coverage": "authorized_resource_metadata", "objects_available": "not_evaluated",
                    "runtime_executable": "not_evaluated"}

    async def current(self, *, project_id, resource_id, principal, environment):
        if environment not in {"draft", "staging", "production"}:
            raise ValidationError("Environment must be draft, staging or production")
        async with self.sessions.begin() as session:
            if session.bind.dialect.name == "postgresql":
                await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
            evidence = await self.owner.inspect(session, project_id=project_id, principal=principal,
                                                kind=self.kind, resource_id=resource_id)
            root = await session.get(self.root, resource_id)
            if root is None or root.project_id != project_id:
                raise NotFoundError("Resource is unavailable")
            if self.kind == "Agent":
                snapshot = await session.scalar(select(self.release).where(
                    self.release.project_id == project_id,
                    getattr(self.release, self.resource_column) == resource_id,
                    self.release.status == environment).order_by(self.release.updated_at.desc(), self.release.id.desc()).limit(1))
            else:
                identifier = getattr(root, environment + "_version_id", None)
                snapshot = await session.get(self.release, identifier) if identifier else None
            return {"schema_version": "1.0", "resource_id": str(resource_id), "kind": self.kind,
                    "environment": environment, "snapshot_id": str(snapshot.id) if snapshot else None,
                    "draft_generation": evidence["revision"],
                    "environment_generation": None, "generation_status": "legacy_unavailable",
                    "remote_status": "verified", "observed_at": datetime.now(UTC).isoformat(),
                    "snapshot": self.render_release(snapshot) if snapshot else None,
                    "capture_consistency": "transaction_snapshot", "complete": True}
