from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shared.contracts.errors import ConflictError, ValidationError
from shared.infra.admin_idempotency import AdministrativeIdempotency, canonical_digest
from shared.infra.database.admin_idempotency import AdministrativeOperationModel
from shared.security.principal import AuthenticatedPrincipal

KEY = "0" * 32  # Deliberately public fixture; never a deployment credential.


@pytest_asyncio.fixture
async def ledger():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def attach(connection, _):
        connection.execute("ATTACH DATABASE ':memory:' AS core")

    async with engine.begin() as connection:
        await connection.run_sync(
            lambda conn: AdministrativeOperationModel.__table__.create(conn)
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    actor = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    yield factory, actor, uuid4()
    await engine.dispose()


@pytest.mark.asyncio
async def test_secret_recovery_is_encrypted_and_replays_committed_identity(ledger):
    factory, actor, workspace_id = ledger
    args = dict(
        key="creation-1",
        actor=actor,
        workspace_id=workspace_id,
        operation="key.create",
        payload={"name": "test"},
    )
    response = {
        "id": str(uuid4()),
        "key": "woobe_control_only-the-caller-can-recover-this",
    }
    async with factory() as session:
        store = AdministrativeIdempotency(session, encryption_key=KEY)
        assert await store.begin(**args) is None
        await store.save(response)
        await session.commit()
    async with factory() as session:
        record = (
            await session.execute(select(AdministrativeOperationModel))
        ).scalar_one()
        assert response["key"] not in record.response_ciphertext
        assert record.key_digest != b"creation-1"
        replay = await AdministrativeIdempotency(session, encryption_key=KEY).begin(
            **args
        )
        assert replay == {**response, "idempotency_replayed": True}


@pytest.mark.asyncio
async def test_same_key_with_different_payload_fails_without_overwriting(ledger):
    factory, actor, workspace_id = ledger
    args = dict(
        key="request-1",
        actor=actor,
        workspace_id=workspace_id,
        operation="project.create",
    )
    async with factory() as session:
        store = AdministrativeIdempotency(session, encryption_key=KEY)
        await store.begin(**args, payload={"name": "original"})
        await store.save({"id": "original"})
        await session.commit()
    async with factory() as session:
        with pytest.raises(ConflictError, match="another payload"):
            await AdministrativeIdempotency(session, encryption_key=KEY).begin(
                **args, payload={"name": "changed"}
            )
        assert (
            await AdministrativeIdempotency(session, encryption_key=KEY).begin(
                **args, payload={"name": "original"}
            )
        )["id"] == "original"


@pytest.mark.asyncio
async def test_reservation_rolls_back_with_failed_mutation(ledger):
    factory, actor, workspace_id = ledger
    args = dict(
        key="rollback-1",
        actor=actor,
        workspace_id=workspace_id,
        operation="project.create",
        payload={},
    )
    async with factory() as session:
        store = AdministrativeIdempotency(session, encryption_key=KEY)
        await store.begin(**args)
        await store.save({"id": "never-committed"})
        await session.rollback()
    async with factory() as session:
        assert (
            await AdministrativeIdempotency(session, encryption_key=KEY).begin(**args)
            is None
        )


@pytest.mark.parametrize("dimension", ["actor", "workspace", "operation"])
@pytest.mark.asyncio
async def test_replay_is_scoped_to_actor_workspace_and_operation(ledger, dimension):
    factory, actor, workspace_id = ledger
    args = dict(
        key="same-client-key",
        actor=actor,
        workspace_id=workspace_id,
        operation="project.create",
        payload={},
    )
    async with factory() as session:
        store = AdministrativeIdempotency(session, encryption_key=KEY)
        await store.begin(**args)
        await store.save({"id": "first"})
        await session.commit()
    if dimension == "actor":
        args["actor"] = actor.model_copy(update={"user_id": uuid4()})
    elif dimension == "workspace":
        args["workspace_id"] = uuid4()
    else:
        args["operation"] = "agent.create"
    async with factory() as session:
        assert (
            await AdministrativeIdempotency(session, encryption_key=KEY).begin(**args)
            is None
        )


@pytest.mark.asyncio
async def test_expired_replay_cannot_recreate_mutation_and_ciphertext_can_be_purged(
    ledger,
):
    factory, actor, workspace_id = ledger
    args = dict(
        key="expired",
        actor=actor,
        workspace_id=workspace_id,
        operation="key.create",
        payload={},
    )
    async with factory() as session:
        store = AdministrativeIdempotency(session, encryption_key=KEY)
        await store.begin(**args)
        await store.save({"key": "secret"})
        store.record.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    async with factory() as session:
        store = AdministrativeIdempotency(session, encryption_key=KEY)
        with pytest.raises(ConflictError, match="retention expired"):
            await store.begin(**args)
        assert await store.purge_expired_secrets() == 1
        await session.commit()
        assert (
            await session.execute(
                select(AdministrativeOperationModel.response_ciphertext)
            )
        ).scalar_one() is None


@pytest.mark.parametrize("key", ["", "x" * 129, "key\nline", "key space"])
@pytest.mark.asyncio
async def test_invalid_keys_fail_before_reserving(ledger, key):
    factory, actor, workspace_id = ledger
    async with factory() as session:
        with pytest.raises(ValidationError):
            await AdministrativeIdempotency(session, encryption_key=KEY).begin(
                key=key,
                actor=actor,
                workspace_id=workspace_id,
                operation="create",
                payload={},
            )


def test_payload_hash_is_canonical_for_object_order():
    assert canonical_digest({"a": 1, "b": 2}) == canonical_digest({"b": 2, "a": 1})
    assert canonical_digest({"a": 1}) != canonical_digest({"a": 2})


@pytest.mark.asyncio
async def test_recovery_survives_control_rotation_but_not_a_different_lineage(ledger):
    from shared.security.principal import ControlPlanePrincipal
    factory, _, workspace_id = ledger
    actor = ControlPlanePrincipal(api_key_id=uuid4(), credential_id=uuid4(),
        workspace_id=workspace_id, key_prefix="fixture", authenticated_at=datetime.now(UTC))
    args = dict(key="rotation-recovery", actor=actor, workspace_id=workspace_id,
                operation="control_key.rotate", payload={"target": "same"})
    async with factory() as session:
        store = AdministrativeIdempotency(session, encryption_key=KEY)
        await store.begin(**args)
        await store.save({"id": "one-accepted-write", "key": "retained-secret"})
        await session.commit()
    rotated_actor = actor.model_copy(update={"api_key_id": uuid4()})
    async with factory() as session:
        replay = await AdministrativeIdempotency(session, encryption_key=KEY).begin(
            **{**args, "actor": rotated_actor})
        assert replay["id"] == "one-accepted-write"
        assert replay["key"] == "retained-secret"
        assert replay["idempotency_replayed"]
    different_lineage = rotated_actor.model_copy(update={"credential_id": uuid4()})
    async with factory() as session:
        assert await AdministrativeIdempotency(session, encryption_key=KEY).begin(
            **{**args, "actor": different_lineage}) is None
