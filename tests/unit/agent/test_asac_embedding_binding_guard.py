from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
from sqlalchemy.dialects import postgresql
from modules.agent.infra.database.asac_binding_guard import AgentASaCBindingGuard
from shared.contracts.errors import ConflictError

@pytest.mark.asyncio
async def test_embedding_guard_holds_versions_and_rejects_revocation_or_model_change(monkeypatch):
    import modules.agent.infra.database.asac_binding_guard as module
    authorize=AsyncMock();monkeypatch.setattr(module,"authorize_export_read",authorize)
    project=uuid4();now=datetime.now(UTC)
    credential=SimpleNamespace(id=uuid4(),project_id=project,status="active",updated_at=now)
    model=SimpleNamespace(id=uuid4(),project_id=project,status="active",updated_at=now,spec_hash="sealed-spec",provider_credential_id=credential.id)
    vector=SimpleNamespace(id=uuid4(),project_id=project,status="READY",collection_id=uuid4(),snapshot_hash="vector-hash",updated_at=now,embedding_provider_model_id=model.id)
    expected={"knowledge":{"docs":{"vector_snapshot_id":str(vector.id),"collection_id":str(vector.collection_id),
        "snapshot_hash":vector.snapshot_hash,"revision":now.isoformat(),"embedding_provider_model_id":str(model.id),
        "embedding_model":{"model_id":str(model.id),"revision":now.isoformat(),"spec_hash":model.spec_hash,
            "credential_id":str(credential.id),"credential_revision":now.isoformat()}}}}
    environment=SimpleNamespace(verify=AsyncMock());guard=AgentASaCBindingGuard(environment)
    async def run():
        session=SimpleNamespace(scalar=AsyncMock(side_effect=[vector,model,credential]))
        await guard.verify(session,project_id=project,resource_id=uuid4(),principal=object(),environment="production",expected=expected)
        return session
    session=await run()
    assert [call.args[3] for call in authorize.await_args_list]==["knowledge:read","provider:read"]
    assert all("FOR SHARE" in str(call.args[0].compile(dialect=postgresql.dialect())) for call in session.scalar.await_args_list)
    model.updated_at=now+timedelta(seconds=1)
    with pytest.raises(ConflictError,match="version changed"): await run()
    model.updated_at=now;credential.status="revoked"
    with pytest.raises(ConflictError,match="version changed"): await run()
