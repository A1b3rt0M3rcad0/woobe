from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from modules.package.application.planning import definition_digest
from modules.package.domain.bundle import PackageGraph
from modules.package.domain.errors import PackageError
from modules.package.infra.development_registry import DevelopmentRegistry
from modules.package.infra.models import PackageResourceBindingModel, PackageOperationModel, PackagePlanModel
from shared.infra.database.base import Base


@pytest.mark.asyncio
@pytest.mark.parametrize("alter", [None, "snapshot", "definition", "operation", "missing_proof", "retained_plan", "wrong_plan_scope"])
async def test_frozen_reuse_requires_exact_owner_receipt_without_export_ticket(alter):
    engine = create_async_engine("sqlite+aiosqlite://", execution_options={"schema_translate_map": {"package": None}})
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: Base.metadata.create_all(sync, tables=[model.__table__ for model in (PackageResourceBindingModel, PackageOperationModel, PackagePlanModel)]))
    project, registry, uid, native, snapshot, operation = [uuid4() for _ in range(6)]
    component = {"kind": "Agent", "metadata": {"key": "constituent", "name": "Frozen"}, "spec": {"model": {}}}
    digest = definition_digest({"component": component, "dependencies": {}, "support": [], "bindings": {}})
    accepted = {"revision": 1, "resource_id": str(native), "operation_id": str(operation), "definition_digest": digest, "frozen": True, "snapshot_id": str(snapshot), "snapshot_digest": "sealed-snapshot", "source_kind": "release"}
    if alter == "operation":
        accepted["operation_id"] = str(uuid4())
    if alter in {"missing_proof", "retained_plan", "wrong_plan_scope"}:
        accepted.pop("snapshot_digest")
        accepted.pop("source_kind")
    async with sessions.begin() as session:
        if alter in {"retained_plan", "wrong_plan_scope"}:
            plan_id = uuid4()
            document = {"registry_id": str(uuid4() if alter == "wrong_plan_scope" else registry), "resource_bindings": {"constituent": {"resource_uid": str(uid), "kind": "Agent", "resource_id": str(native), "definition_digest": digest, "frozen": True, "evidence": {"snapshot_id": str(snapshot), "snapshot_digest": "sealed-snapshot", "source_kind": "release"}}}}
            session.add(PackagePlanModel(id=plan_id, project_id=project, actor="original-actor", upload_id=uuid4(), artifact_digest="a" * 64, plan_digest="b" * 64, document=document, expires_at=datetime.now(UTC) - timedelta(days=1)))
            session.add(PackageOperationModel(id=operation, project_id=project, actor="original-actor", key_digest=b"k", payload_fingerprint=b"p", payload_ciphertext="protected", principal_ciphertext="protected", artifact_digest="a" * 64, upload_id=uuid4(), plan_id=plan_id, lifecycle="draft", state="succeeded", phases_total=1))
        session.add(PackageResourceBindingModel(project_id=project, registry_id=registry, resource_uid=uid, resource_id=native, kind="Agent", operation_id=operation, definition_digest=digest, preparation={"accepted_native": accepted}))
    reader = SimpleNamespace(inspect=AsyncMock(return_value={"resource_id": str(native), "revision": 99}))
    document = {"bindings": {}, "binding_resolutions": {}, "effects": [{"component": "constituent", "action": "finalize_agent_draft", "permission": "agent:write"}]}
    targets = {"constituent": {"resource_uid": str(uid), "resource_id": str(native), "release_id": str(uuid4() if alter == "snapshot" else snapshot)}}
    if alter == "definition":
        component["metadata"]["name"] = "Edited"
    async with sessions.begin() as session:
        action = DevelopmentRegistry(sessions, reader, reader).prepare(session, project_id=project, principal="new-authority", registry_id=str(registry), targets=targets, graph=PackageGraph({}, {"constituent": component}, {"constituent": "agent.yaml"}, ("constituent",)), inventory=[], document=document)
        if alter and alter != "retained_plan":
            with pytest.raises(PackageError):
                await action
        else:
            await action
            evidence = document["resource_bindings"]["constituent"]["evidence"]
            assert evidence["snapshot_id"] == str(snapshot)
            assert evidence["snapshot_digest"] == "sealed-snapshot"
            assert document["effects"][0]["action"] == "reuse_frozen_snapshot"
    await engine.dispose()
