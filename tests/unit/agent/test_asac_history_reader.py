from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from shared.contracts.asac import asac_digest
from shared.contracts.errors import AuthorizationError, ValidationError
from shared.infra.asac_history_reader import ASaCHistoryReader


class HistoryBase(DeclarativeBase):
    pass


class Root(HistoryBase):
    __tablename__ = "roots"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    revision: Mapped[int] = mapped_column(Integer)


class Release(HistoryBase):
    __tablename__ = "releases"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    project_id: Mapped[UUID]
    agent_id: Mapped[UUID]
    snapshot_kind: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


@pytest.fixture
async def history():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(HistoryBase.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner = SimpleNamespace(inspect=AsyncMock(return_value={"revision": 4}))
    reader = ASaCHistoryReader(sessions, kind="Agent", root=Root, release=Release,
        activation=Release, owner=owner, resource_column="agent_id",
        release_kind=("snapshot_kind", "release"), cursor_key="test-only-cursor-key",
        render_release=lambda row: {"version": row.version},
        render_activation=lambda row: {"version": row.version})
    project, resource = uuid4(), uuid4()
    async with sessions.begin() as session:
        session.add(Root(id=resource, project_id=project, revision=4))
        for i in range(3):
            time = datetime(2026, 10, 8, tzinfo=UTC) + timedelta(seconds=i)
            session.add(Release(id=uuid4(), project_id=project, agent_id=resource,
                snapshot_kind="release", status="production" if i == 1 else "release",
                version=str(i), created_at=time, updated_at=time))
        session.add(Release(id=uuid4(), project_id=uuid4(), agent_id=resource,
            snapshot_kind="release", status="release", version="foreign",
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))
    yield reader, sessions, project, resource
    await engine.dispose()


@pytest.mark.asyncio
async def test_history_watermark_scope_and_integrity(history):
    reader, sessions, project, resource = history
    args = dict(project_id=project, resource_id=resource, principal=object(), limit=1)
    first = await reader.fetch(**args)
    assert first["has_more"] and not first["complete"]
    async with sessions.begin() as session:
        session.add(Release(id=uuid4(), project_id=project, agent_id=resource,
            snapshot_kind="release", status="release", version="later",
            created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))
    records = first["records"]
    cursor = first["next_cursor"]
    while cursor:
        page = await reader.fetch(**args, cursor=cursor)
        assert page["watermark"] == first["watermark"]
        records.extend(page["records"])
        cursor = page["next_cursor"]
    assert [record["version"] for record in records] == ["0", "1", "2"]
    for record in records:
        digest = record.pop("record_digest")
        assert digest == asac_digest("history-receipt", record)
        assert record["origin_status"] == "unknown_origin"
    with pytest.raises(ValidationError):
        await reader.fetch(**{**args, "resource_id": uuid4()}, cursor=first["next_cursor"])
    with pytest.raises(ValidationError):
        await reader.fetch(**args, cursor=first["next_cursor"] + "bad")


@pytest.mark.asyncio
async def test_current_uses_actual_selection_not_latest_release(history):
    reader, _, project, resource = history
    result = await reader.current(project_id=project, resource_id=resource,
                                  principal=object(), environment="production")
    assert result["snapshot"]["version"] == "1"
    assert result["draft_generation"] == 4
    assert result["environment_generation"] is None
    assert result["generation_status"] == "legacy_unavailable"


@pytest.mark.asyncio
async def test_history_authority_refusal_precedes_projection(history):
    reader, _, project, resource = history
    reader.owner.inspect.side_effect = AuthorizationError("denied")
    with pytest.raises(AuthorizationError):
        await reader.fetch(project_id=project, resource_id=resource, principal=object())
