"""Bounded author-source custody. Custody is not a compiler attestation."""
import asyncio
import base64
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import gzip
from hashlib import sha256
import io
import json
from pathlib import PurePosixPath
from uuid import UUID, uuid4
import zlib

from modules.package.domain.errors import PackageError
from modules.package.infra.models import PackageAuthorArtifactModel
from modules.package.infra.operation_repository import as_utc
from modules.package.infra.receipts import authorize_phase
from shared.contracts.asac import asac_digest
from shared.infra.admin_idempotency import principal_identity

MAX_BYTES = 128 << 20
KINDS = {"Agent", "Network", "Provider", "Model", "Tool", "Skill", "Knowledge", "Prompt", "Contract", "Surface", "Snapshot"}


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def _path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\x00" in value:
        raise ValueError("invalid source path")
    parts = PurePosixPath(value).parts
    if PurePosixPath(value).is_absolute() or ".." in parts or value != str(PurePosixPath(value)):
        raise ValueError("invalid source path")


def validate_author(content):
    """Validate transport, canonical identity and bounded portable source shape."""
    try:
        if len(content) > MAX_BYTES:
            raise ValueError("transport limit")
        with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream:
            raw = stream.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("source limit")
        document = json.loads(raw, object_pairs_hook=_pairs, parse_float=Decimal,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite number")))
        if not isinstance(document, dict) or set(document) - {"format", "schema_version", "resource_uid", "compiler_recipe", "components"}:
            raise ValueError("source shape")
        if document["format"] != "woobe-author-object" or document["schema_version"] != "1.0":
            raise ValueError("source format")
        if document.get("compiler_recipe", "") not in {"", "woobe-development-compiler@2.0"}:
            raise ValueError("compiler recipe")
        uid = str(UUID(document["resource_uid"]))
        components = document["components"]
        if not isinstance(components, dict) or not 1 <= len(components) <= 1024 or uid not in components:
            raise ValueError("source closure")
        identities, keys, paths, total = {}, set(), set(), 0
        for component_uid, component in components.items():
            if str(UUID(component_uid)) != component_uid or set(component) != {"resource", "document", "raw", "supports"}:
                raise ValueError("source component")
            resource = component["resource"]
            if resource["uid"] != component_uid or resource["kind"] not in KINDS or not isinstance(resource["key"], str):
                raise ValueError("component identity")
            _path(resource["path"])
            if resource["key"] in keys or resource["path"] in paths:
                raise ValueError("duplicate resource")
            keys.add(resource["key"])
            paths.add(resource["path"])
            if not isinstance(component["document"], dict) or not isinstance(component["raw"], str) or len(component["raw"].encode()) > 8 << 20:
                raise ValueError("descriptor limit")
            if resource["kind"] == "Provider":
                spec = component["document"].get("spec", {})
                if not isinstance(spec, dict):
                    raise ValueError("invalid Provider descriptor")
                credential = spec.get("credential_ref")
                if isinstance(credential, str):
                    try:
                        UUID(credential)
                    except ValueError:
                        pass
                    else:
                        raise ValueError("private credential UUID in source")
            total += len(component["raw"].encode())
            supports = component["supports"]
            if not isinstance(supports, dict) or len(supports) > 1024:
                raise ValueError("support shape")
            for name, encoded in supports.items():
                _path(name)
                data = base64.b64decode(encoded, validate=True)
                if len(data) > 64 << 20:
                    raise ValueError("support limit")
                total += len(data)
            if total > 90 << 20:
                raise ValueError("closure limit")
            identities[component_uid] = {"kind": resource["kind"], "key": resource["key"]}
        if identities[uid]["kind"] not in {"Agent", "Network"}:
            raise ValueError("root kind")
        return {"author_digest": asac_digest("author-object", document), "resource_uid": uid, "components": identities}
    except (ValueError, TypeError, KeyError, OSError, EOFError, RecursionError, ArithmeticError, zlib.error) as exc:
        raise PackageError("ASAC_AUTHOR_INVALID", "Author source does not match its bounded portable contract") from exc


class PackageAuthorArtifactRepository:
    def __init__(self, sessions, storage):
        self.sessions, self.storage = sessions, storage

    async def authorize(self, project_id, principal):
        async with self.sessions() as session:
            await authorize_phase(session, principal, project_id, "project:read")

    async def upload(self, *, project_id, principal, stream):
        await self.authorize(project_id, principal)
        content = await asyncio.to_thread(stream.read, MAX_BYTES + 1)
        evidence = await asyncio.to_thread(validate_author, content)
        identifier = uuid4()
        key = f"projects/{project_id}/uploads/{identifier}.tar.gz"
        stored = await asyncio.to_thread(self.storage.put, key, io.BytesIO(content))
        async with self.sessions.begin() as session:
            await authorize_phase(session, principal, project_id, "project:read")
            session.add(PackageAuthorArtifactModel(id=identifier, project_id=project_id,
                actor=principal_identity(principal), **{**evidence, "resource_uid": UUID(evidence["resource_uid"])},
                storage_key=key, transport_digest=sha256(content).hexdigest(), size_bytes=stored["size_bytes"],
                expires_at=datetime.now(UTC) + timedelta(days=1)))
        return {"package_schema_version": "1.0", "project_id": str(project_id), "author_upload_id": str(identifier), **evidence, "size_bytes": len(content), "complete": True,
            "verification": "canonical_source_custody"}

    async def retain(self, *, project_id, principal, upload_id, record, identities):
        async with self.sessions() as session:
            await authorize_phase(session, principal, project_id, "project:read")
            row = await session.get(PackageAuthorArtifactModel, UUID(str(upload_id)))
            if row is None or row.project_id != project_id or row.actor != principal_identity(principal) or as_utc(row.expires_at) <= datetime.now(UTC):
                raise PackageError("ASAC_AUTHOR_UNAVAILABLE", "Author upload is unavailable or expired")
            if row.author_digest != record.get("author_artifact_digest") or str(row.resource_uid) != record["resource_uid"] or {uid: item["key"] for uid, item in row.components.items()} != identities or row.components[str(row.resource_uid)]["kind"] != record["kind"]:
                raise PackageError("ASAC_AUTHOR_MISMATCH", "Author source differs from the revision identity")
            return row.id

    async def transfer(self, *, project_id, principal, artifact_id):
        await self.authorize(project_id, principal)
        async with self.sessions() as session:
            row = await session.get(PackageAuthorArtifactModel, UUID(str(artifact_id)))
            if row is None or row.project_id != project_id:
                raise PackageError("ASAC_AUTHOR_UNAVAILABLE", "Author source is not retained")
        def read():
            try:
                with self.storage.open(row.storage_key) as stream:
                    content = stream.read(MAX_BYTES + 1)
            except OSError as exc:
                raise PackageError("ASAC_AUTHOR_UNAVAILABLE", "Retained author source is unavailable") from exc
            evidence = validate_author(content)
            if len(content) != row.size_bytes or sha256(content).hexdigest() != row.transport_digest or evidence["author_digest"] != row.author_digest or evidence["components"] != row.components:
                raise PackageError("ASAC_AUTHOR_MISMATCH", "Retained author source failed integrity verification")
            return evidence, content
        evidence, content = await asyncio.to_thread(read)
        await self.authorize(project_id, principal)
        return {**evidence, "transport_digest": row.transport_digest, "size_bytes": row.size_bytes,
            "verification": "canonical_source_custody"}, content
