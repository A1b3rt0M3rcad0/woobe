from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface.application.runtime_gateway import ChatRunIdentity
from modules.chat_surface.infra.services.control_plane_service import ControlPlaneChatSurfaceService


class _Gateway:
    def __init__(self, identity: ChatRunIdentity | None) -> None:
        self.identity = identity
        self.calls = []

    async def resolve_run(
        self,
        target,
        *,
        preferred_run_id=None,
        created_after=None,
    ):
        self.calls.append((target, preferred_run_id, created_after))
        return self.identity


def _binding(target_type: str):
    return SimpleNamespace(
        project_id=uuid4(),
        target_type=target_type,
        target_id=uuid4(),
        target_release_id=uuid4(),
        session_id=uuid4(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_active_run_resolution_is_delegated_to_runtime_gateway(
    target_type: str,
) -> None:
    binding = _binding(target_type)
    run_id = uuid4()
    gateway = _Gateway(ChatRunIdentity(run_id=run_id, status="running"))
    service = ControlPlaneChatSurfaceService(
        SimpleNamespace(),
        SimpleNamespace(),
        runtime_gateway=gateway,
    )

    resolved_run_id, resolved_status = await service._active_run_for_binding(binding)

    assert resolved_run_id == run_id
    assert resolved_status == "running"
    assert len(gateway.calls) == 1
    target, preferred_run_id, created_after = gateway.calls[0]
    assert target.project_id == binding.project_id
    assert target.target_type == binding.target_type
    assert target.target_id == binding.target_id
    assert target.target_release_id == binding.target_release_id
    assert target.session_id == binding.session_id
    assert preferred_run_id is None
    assert created_after is None


@pytest.mark.asyncio
async def test_message_request_run_resolution_preserves_run_correlation_inputs() -> None:
    binding = _binding("agent")
    run_id = uuid4()
    created_at = datetime.now(UTC)
    gateway = _Gateway(ChatRunIdentity(run_id=run_id, status="completed"))
    service = ControlPlaneChatSurfaceService(
        SimpleNamespace(),
        SimpleNamespace(),
        runtime_gateway=gateway,
    )
    request = SimpleNamespace(
        target_run_id=None,
        created_at=created_at,
    )

    resolved_run_id, resolved_status = await service._resolve_request_run(
        request,
        binding,
    )

    assert resolved_run_id == run_id
    assert resolved_status == "completed"
    _, preferred_run_id, resolved_created_after = gateway.calls[0]
    assert preferred_run_id is None
    assert resolved_created_after == created_at

    gateway.calls.clear()
    request.target_run_id = run_id

    await service._resolve_request_run(request, binding)

    _, preferred_run_id, resolved_created_after = gateway.calls[0]
    assert preferred_run_id == run_id
    assert resolved_created_after is None


@pytest.mark.asyncio
async def test_runtime_resolution_fails_closed_without_gateway() -> None:
    service = ControlPlaneChatSurfaceService(
        SimpleNamespace(),
        SimpleNamespace(),
    )

    with pytest.raises(RuntimeError, match="runtime gateway is not configured"):
        await service._active_run_for_binding(_binding("agent"))

