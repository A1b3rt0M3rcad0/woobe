from __future__ import annotations

from uuid import UUID

from fastapi import Request as FastAPIRequest

from modules.agent.entrypoint import public_run_composer, public_stream_composer
from modules.agent.presentation.http.run_routes import (
    active_agent_run,
    attach_agent_run,
    cancel_agent_run,
)
from modules.network.presentation.public_runtime import (
    is_network_runtime_request,
    run_network_http,
    stream_network_http,
)
from modules.network.presentation.reattach_routes import (
    active_network_execution,
    cancel_network_run,
    reattach_network_execution,
)
from modules.network.presentation.runtime_environment_dependency import (
    enforce_public_network_runtime_environment,
)
from shared.presentation.http.adapter import request_adapter, response_adapter


class RuntimeHttpComposition:
    """Outer HTTP composition for Agent and Network runtime targets.

    Target dispatch belongs to the API composition root. Agent and Network keep
    their own execution semantics while attach/reattach converge on the shared
    RuntimeObserver inside their public boundaries.
    """

    async def run(self, request: FastAPIRequest):
        if is_network_runtime_request(request):
            await enforce_public_network_runtime_environment(request)
            return await run_network_http(request)
        handler = public_run_composer()
        response = await request_adapter(request, handler)
        return response_adapter(response)

    async def stream(self, request: FastAPIRequest):
        if is_network_runtime_request(request):
            await enforce_public_network_runtime_environment(request)
            return await stream_network_http(request)
        return await public_stream_composer()(request)

    async def reattach(self, target_type: str, run_id: UUID, request: FastAPIRequest):
        if target_type == "network":
            return await reattach_network_execution(run_id, request)
        return await attach_agent_run(run_id, request)

    async def cancel(self, target_type: str, run_id: UUID, request: FastAPIRequest):
        if target_type == "network":
            return await cancel_network_run(run_id, request)
        return await cancel_agent_run(run_id, request)

    async def active(
        self,
        target_type: str,
        session_id: UUID,
        request: FastAPIRequest,
    ):
        if target_type == "network":
            return await active_network_execution(
                request,
                network_session_id=session_id,
            )
        return await active_agent_run(request, session_id=session_id)


RUNTIME_HTTP = RuntimeHttpComposition()
