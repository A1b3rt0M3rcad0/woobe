"""Retained author custody is bounded, actor scoped on upload, and reauthorized."""
from copy import deepcopy
from datetime import UTC, datetime, timedelta
import gzip
import io
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from modules.package.domain.errors import PackageError
from modules.package.infra.author_artifact_repository import validate_author, PackageAuthorArtifactRepository
from modules.package.infra.artifact_storage import LocalPackageArtifactStorage
from modules.package.infra.models import PackageAuthorArtifactModel
from shared.security.principal import AuthenticatedPrincipal
from shared.contracts.asac import asac_digest


def source():
    uid = str(uuid4())
    value = {"format": "woobe-author-object", "schema_version": "1.0", "compiler_recipe": "woobe-development-compiler@2.0", "resource_uid": uid,
        "components": {uid: {"resource": {"uid": uid, "kind": "Agent", "key": "support", "alias": "support", "path": "agents/support", "frozen": False},
            "document": {"kind": "Agent"}, "raw": "# Exact comment\nkind: Agent\n", "supports": {}}}}
    return value


def pack(value):
    return gzip.compress(json.dumps(value, ensure_ascii=False).encode(), mtime=0)


def test_author_shape_preserves_exact_comment_and_canonical_hash():
    value = source()
    evidence = validate_author(pack(value))
    assert evidence["author_digest"] == asac_digest("author-object", value)
    changed = deepcopy(value)
    changed["components"][value["resource_uid"]]["raw"] += "# comment only\n"
    assert validate_author(pack(changed))["author_digest"] != evidence["author_digest"]


@pytest.mark.parametrize("mutation", ["escape", "duplicate", "unsupported", "wrong_uid", "oversized_descriptor", "unsafe_support", "bad_support"])
def test_author_source_rejects_invalid_closure(mutation):
    value = source()
    uid = value["resource_uid"]
    item = value["components"][uid]
    if mutation == "escape": item["resource"]["path"] = "../outside"
    if mutation == "duplicate":
        other = str(uuid4()); value["components"][other] = deepcopy(item); value["components"][other]["resource"]["uid"] = other
    if mutation == "unsupported": value["compiler_recipe"] = "future"
    if mutation == "wrong_uid": item["resource"]["uid"] = str(uuid4())
    if mutation == "oversized_descriptor": item["raw"] = "x" * ((8 << 20) + 1)
    if mutation == "unsafe_support": item["supports"] = {"../secret": "eA=="}
    if mutation == "bad_support": item["supports"] = {"file.txt": "not-base64"}
    with pytest.raises(PackageError, match="bounded portable contract"):
        validate_author(pack(value))


def test_author_rejects_duplicate_json_and_compression_corruption():
    with pytest.raises(PackageError): validate_author(gzip.compress(b'{"format":"a","format":"b"}'))
    with pytest.raises(PackageError): validate_author(b"not compressed")


@pytest.mark.asyncio
async def test_upload_actor_expiry_and_retained_history_reader(tmp_path, monkeypatch):
    import modules.package.infra.author_artifact_repository as module
    calls = []
    async def authorize(session, principal, project, permission):
        calls.append((principal.user_id, project, permission))
    monkeypatch.setattr(module, "authorize_phase", authorize)
    engine = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"package": None}})
    async with engine.begin() as connection:
        await connection.run_sync(PackageAuthorArtifactModel.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    repository = PackageAuthorArtifactRepository(sessions, LocalPackageArtifactStorage(tmp_path))
    actor = AuthenticatedPrincipal(user_id=uuid4(), session_id=uuid4(), issued_at=datetime.now(UTC), expires_at=datetime.now(UTC)+timedelta(hours=1))
    other = actor.model_copy(update={"user_id": uuid4()})
    project = uuid4(); value = source(); uid = value["resource_uid"]
    receipt = await repository.upload(project_id=project, principal=actor, stream=io.BytesIO(pack(value)))
    record = {"author_artifact_digest": receipt["author_digest"], "resource_uid": uid, "kind": "Agent"}
    args = dict(project_id=project, upload_id=receipt["author_upload_id"], record=record, identities={uid: "support"})
    with pytest.raises(PackageError): await repository.retain(**args, principal=other)
    retained = await repository.retain(**args, principal=actor)
    async with sessions.begin() as session:
        row = await session.get(PackageAuthorArtifactModel, retained)
        row.expires_at = datetime.now(UTC)-timedelta(days=1)
    with pytest.raises(PackageError): await repository.retain(**args, principal=actor)
    # A Root-owned retained link authorizes transfer independently of ticket actor/expiry.
    evidence, content = await repository.transfer(project_id=project, principal=other, artifact_id=retained)
    assert evidence["author_digest"] == record["author_artifact_digest"] and content == pack(value)
    assert calls[-1][0] == other.user_id
    with pytest.raises(PackageError): await repository.transfer(project_id=uuid4(), principal=other, artifact_id=retained)
    await engine.dispose()


def test_author_extreme_numeric_exponent_is_a_bounded_rejection():
    value = source()
    raw = json.dumps(value).replace('"document": {"kind": "Agent"}', '"document": {"kind": "Agent", "number": 1e999999999999999999999999}')
    with pytest.raises(PackageError, match="bounded portable contract"):
        validate_author(gzip.compress(raw.encode()))
