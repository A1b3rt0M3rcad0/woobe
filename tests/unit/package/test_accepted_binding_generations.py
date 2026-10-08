"""Keep accepted content/generation together even if a later reader sees edits."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.package.domain.errors import PackageError
from modules.package.infra.development_registry import DevelopmentRegistry
from modules.package.infra.models import (
    PackageEffectModel,
    PackageOperationModel,
    PackagePlanModel,
    PackageResourceBindingModel,
)
from modules.package.infra.receipts import PackageTransactionReceipt
from shared.infra.admin_idempotency import principal_identity
from shared.infra.database.base import Base
from shared.presentation.contracts import (
    OperationRequest,
    OperationResult,
    OperationOutcome,
)
from shared.security.principal import AuthenticatedPrincipal


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,action",
    [
        ("Agent", "finalize_agent_draft"),
        ("Network", "save_network_draft"),
        ("Model", "resolve_model"),
        ("Tool", "materialize_tool"),
        ("Skill", "materialize_skill_version"),
        ("Knowledge", "verify_vector_snapshot"),
        ("Prompt", "create_prompt_version"),
        ("Contract", "create_contract_version"),
    ],
)
async def test_accepted_generation_commits_with_phase_not_later_current_read(
    monkeypatch, kind, action
):
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        execution_options={"schema_translate_map": {"package": None}},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    tables = [
        m.__table__
        for m in (
            PackageEffectModel,
            PackageOperationModel,
            PackagePlanModel,
            PackageResourceBindingModel,
        )
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))
    monkeypatch.setattr("modules.package.infra.receipts.authorize_phase", AsyncMock())
    monkeypatch.setattr(
        "modules.package.infra.development_registry.authorize_phase", AsyncMock()
    )
    now = datetime.now(UTC)
    actor = AuthenticatedPrincipal(
        user_id=uuid4(),
        session_id=uuid4(),
        issued_at=now,
        expires_at=now + timedelta(hours=1),
    )
    project, registry, uid, native, op_id, plan_id = (uuid4() for _ in range(6))
    async with factory.begin() as session:
        session.add(
            PackagePlanModel(
                id=plan_id,
                project_id=project,
                actor=principal_identity(actor),
                upload_id=uuid4(),
                artifact_digest="a" * 64,
                plan_digest="b" * 64,
                document={
                    "registry_id": str(registry),
                    "resource_bindings": {
                        "support": {
                            "resource_uid": str(uid),
                            "kind": kind,
                            "definition_digest": "a" * 64,
                        }
                    },
                },
                expires_at=now + timedelta(hours=1),
            )
        )
        session.add(
            PackageOperationModel(
                id=op_id,
                project_id=project,
                actor=principal_identity(actor),
                key_digest=b"key",
                payload_fingerprint=b"payload",
                payload_ciphertext="protected",
                principal_ciphertext="protected",
                artifact_digest="a" * 64,
                upload_id=uuid4(),
                plan_id=plan_id,
                lifecycle="draft",
                state="materializing",
                phases_total=1,
            )
        )
        session.add(
            PackageResourceBindingModel(
                project_id=project,
                registry_id=registry,
                resource_uid=uid,
                kind=kind,
                resource_id=native,
                operation_id=op_id,
                preparation={"new_root": True, "root_revision": 1},
            )
        )
    observed = AsyncMock(return_value={"revision": 7, "resource_id": str(native)})
    receipt = PackageTransactionReceipt(
        operation_id=op_id,
        lease_token=uuid4(),
        phase="save:support",
        permission="agent:write",
        encryption_key="test-key",
        evidence={"component": "support", "action": action},
        binding_reader=observed,
    )
    data = {
        "id": str(native),
        "agent_id": str(native),
        "vector_snapshot_id": str(native),
    }
    async with factory.begin() as session:
        receipt.operation = await session.get(PackageOperationModel, op_id)
        await receipt.save(
            SimpleNamespace(session=session),
            OperationRequest(principal=actor),
            OperationResult(outcome=OperationOutcome.CREATED, body={"data": data}),
        )
        assert observed.await_args.args[0] is session
        assert observed.await_args.kwargs["lock"] is True
    # A concurrent edit after COMMIT changes the current generation to eight.
    current_reader = SimpleNamespace(
        inspect=AsyncMock(return_value={"revision": 8, "resource_id": str(native)})
    )
    result = await DevelopmentRegistry(
        factory, current_reader, current_reader
    ).bindings(project_id=project, principal=actor, registry_id=registry)
    binding = result["resources"][0]
    assert binding["definition_digest"] == "a" * 64
    assert binding["revision"] == binding["accepted_revision"] == 7
    assert binding["current_revision"] == 8
    assert binding["binding_status"] == "resource_changed"
    assert binding["generation_scope"] == "accepted_native_phase"
    assert binding["operation_id"] == str(op_id)
    async with factory() as session:
        from sqlalchemy import select

        stored = await session.scalar(select(PackageResourceBindingModel))
        assert "new_root" not in stored.preparation
        assert "root_revision" not in stored.preparation
    # If accepted evidence cannot be read in the owner transaction, neither a
    # new binding nor a phase receipt may survive the failed commit scope.
    receipt.phase = "failed:support"
    receipt.binding_reader = AsyncMock(
        side_effect=PackageError(
            "PACKAGE_NATIVE_EVIDENCE_INVALID", "Native evidence unavailable"
        )
    )
    with pytest.raises(PackageError, match="Native evidence unavailable"):
        async with factory.begin() as session:
            plan = await session.get(PackagePlanModel, plan_id)
            plan.document = {
                **plan.document,
                "resource_bindings": {
                    "support": {
                        "resource_uid": str(uid),
                        "kind": kind,
                        "definition_digest": "b" * 64,
                    }
                },
            }
            receipt.operation = await session.get(PackageOperationModel, op_id)
            await receipt.save(
                SimpleNamespace(session=session),
                OperationRequest(principal=actor),
                OperationResult(outcome=OperationOutcome.CREATED, body={"data": data}),
            )
    async with factory() as session:
        from sqlalchemy import func, select

        stored = await session.scalar(select(PackageResourceBindingModel))
        assert stored.definition_digest == "a" * 64
        assert stored.preparation["accepted_native"]["revision"] == 7
        assert (
            await session.scalar(select(func.count()).select_from(PackageEffectModel))
            == 1
        )
    # A later reservation can legitimately coexist with the old accepted
    # receipt. Its partial generation is not labeled as an accepted base.
    next_operation = uuid4()
    async with factory.begin() as session:
        session.add(
            PackageOperationModel(
                id=next_operation,
                project_id=project,
                actor=principal_identity(actor),
                key_digest=b"next-key",
                payload_fingerprint=b"next-payload",
                payload_ciphertext="protected",
                principal_ciphertext="protected",
                artifact_digest="b" * 64,
                upload_id=uuid4(),
                plan_id=plan_id,
                lifecycle="draft",
                state="materializing",
                phases_total=1,
            )
        )
        binding = await session.scalar(select(PackageResourceBindingModel))
        binding.operation_id, binding.definition_digest = next_operation, None
    partial = await DevelopmentRegistry(
        factory, current_reader, current_reader
    ).bindings(project_id=project, principal=actor, registry_id=registry)
    assert partial["resources"][0]["generation_scope"] == "unsealed_native_binding"
    assert partial["resources"][0]["binding_status"] == "binding_incomplete"
    assert partial["resources"][0]["revision"] is None
    assert partial["resources"][0]["accepted_revision"] is None
    # A first preparatory binding has no older accepted receipt at all.
    # It is still incomplete, never a legacy accepted base.
    async with factory.begin() as session:
        binding = await session.scalar(select(PackageResourceBindingModel))
        binding.preparation = {}
    initial = await DevelopmentRegistry(
        factory, current_reader, current_reader
    ).bindings(project_id=project, principal=actor, registry_id=registry)
    assert initial["resources"][0]["generation_scope"] == "unsealed_native_binding"
    assert initial["resources"][0]["revision"] is None
    async with factory.begin() as session:
        binding = await session.scalar(select(PackageResourceBindingModel))
        binding.preparation = {
            "accepted_native": {
                "revision": 7,
                "resource_id": str(native),
                "operation_id": str(op_id),
                "definition_digest": "a" * 64,
            }
        }
    async with factory.begin() as session:
        operation = await session.get(PackageOperationModel, next_operation)
        operation.state = "succeeded"
    with pytest.raises(PackageError, match="another binding receipt"):
        await DevelopmentRegistry(factory, current_reader, current_reader).bindings(
            project_id=project, principal=actor, registry_id=registry
        )
    await engine.dispose()
