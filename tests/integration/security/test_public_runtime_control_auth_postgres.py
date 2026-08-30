from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select

import public_runtime_routes
from modules.core.infra.database.models import (
    ApiKeyModel,
    ProjectModel,
    SecurityConcurrencyLeaseModel,
    SecurityRateLimitEventModel,
)
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory
from shared.security.api_keys import issue_runtime_api_key
from shared.security.dependency import enforce_request_security
from shared.security.http_guard import HttpSecurityGuard
from shared.security.rate_limit import (
    ApiKeyConcurrencyLimiter,
    ApiKeyRequestLimiter,
    LoginRateLimiter,
)


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_public_cancel_uses_real_runtime_key_auth_without_execution_lease(
    monkeypatch,
    target_type: str,
) -> None:
    settings = Settings.model_validate({})
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    project_id = uuid4()
    target_id = uuid4()
    api_key_id = uuid4()
    run_id = uuid4()
    issued = issue_runtime_api_key("production")
    calls = []

    try:
        async with session_factory() as session, session.begin():
            session.add(
                ProjectModel(
                    id=project_id,
                    workspace_id=uuid4(),
                    name="Public Runtime control auth",
                    slug=f"runtime-control-{project_id}",
                    status="active",
                    data={},
                )
            )
            session.add(
                ApiKeyModel(
                    id=api_key_id,
                    project_id=project_id,
                    credential_id=uuid4(),
                    name="Runtime production key",
                    description=None,
                    key_prefix=issued.public_prefix,
                    key_hash=issued.digest,
                    key_version=issued.key_version,
                    scopes=["runtime:execute"],
                    kind="runtime",
                    agent_id=target_id if target_type == "agent" else None,
                    target_type=target_type,
                    target_id=target_id,
                    chat_surface_id=None,
                    environment="production",
                    interfaces=["http", "stream"],
                    status="active",
                    last_used_at=None,
                    expires_at=None,
                    revoked_at=None,
                    created_by_user_id=uuid4(),
                    rotated_from_id=None,
                )
            )

        async def cancel_agent(actual_run_id, request):
            principal = request.state.principal
            calls.append(("agent", actual_run_id, principal))
            return {
                "success": True,
                "data": {
                    "run_id": str(actual_run_id),
                    "status": "cancel_requested",
                },
            }

        async def cancel_network(actual_run_id, request):
            principal = request.state.principal
            calls.append(("network", actual_run_id, principal))
            return {
                "success": True,
                "data": {
                    "run_id": str(actual_run_id),
                    "status": "cancel_requested",
                },
            }

        monkeypatch.setattr(public_runtime_routes, "cancel_agent_run", cancel_agent)
        monkeypatch.setattr(public_runtime_routes, "cancel_network_run", cancel_network)

        guard = HttpSecurityGuard(
            session_factory=session_factory,
            token_codec=MagicMock(),
            login_rate_limiter=LoginRateLimiter(
                max_attempts=100,
                window_seconds=60,
                session_factory=session_factory,
            ),
            api_key_rate_limiter=ApiKeyRequestLimiter(
                max_requests=100,
                window_seconds=60,
                session_factory=session_factory,
            ),
            api_key_concurrency_limiter=ApiKeyConcurrencyLimiter(
                max_concurrency=1,
                session_factory=session_factory,
            ),
            settings=settings,
        )
        app = FastAPI()
        app.state.security_guard = guard
        security_dependency = Depends(enforce_request_security)
        app.router.dependencies.append(security_dependency)
        try:
            app.include_router(public_runtime_routes.router)
        finally:
            app.router.dependencies.remove(security_dependency)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                f"/v1/runs/{run_id}/cancel",
                headers={"Authorization": f"Bearer {issued.value}"},
            )

        assert response.status_code == 202
        assert response.json()["data"]["status"] == "cancel_requested"
        assert len(calls) == 1
        called_target, called_run_id, principal = calls[0]
        assert called_target == target_type
        assert called_run_id == run_id
        assert principal.api_key_id == api_key_id
        assert principal.project_id == project_id
        assert principal.target_type == target_type
        assert principal.target_id == target_id
        assert principal.environment == "production"

        async with session_factory() as session:
            lease_count = await session.scalar(
                select(func.count(SecurityConcurrencyLeaseModel.id)).where(
                    SecurityConcurrencyLeaseModel.subject_key == str(api_key_id)
                )
            )
        assert int(lease_count or 0) == 0
    finally:
        async with session_factory() as session, session.begin():
            await session.execute(
                delete(SecurityConcurrencyLeaseModel).where(
                    SecurityConcurrencyLeaseModel.subject_key == str(api_key_id)
                )
            )
            await session.execute(
                delete(SecurityRateLimitEventModel).where(
                    SecurityRateLimitEventModel.subject_key == str(api_key_id)
                )
            )
            await session.execute(delete(ApiKeyModel).where(ApiKeyModel.id == api_key_id))
            await session.execute(delete(ProjectModel).where(ProjectModel.id == project_id))
        await engine.dispose()
