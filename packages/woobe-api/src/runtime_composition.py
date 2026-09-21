from __future__ import annotations

from uuid import UUID

from fastapi import Request as FastAPIRequest

from modules.agent.entrypoint import (
    build_agent_runtime_contract_reader,
    build_public_stream_components,
    public_run_composer,
)
from modules.network.entrypoint import build_network_service
from shared.infra.errors import ValidationError
from shared.contracts.runtime_contracts import compare_contract_schema
from shared.security.principal import ProjectApiPrincipal
from woobe_api.http.agent.controllers.public_runtime_stream_controller import (
    PublicRuntimeStreamController,
)
from woobe_api.http.agent.run_routes import (
    active_agent_run,
    attach_agent_run,
    cancel_agent_run,
)
from woobe_api.http.network.public_runtime import (
    is_network_runtime_request,
    run_network_http,
    stream_network_http,
)
from woobe_api.http.network.reattach_routes import (
    active_network_execution,
    cancel_network_run,
    reattach_network_execution,
)
from woobe_api.http.network.runtime_environment_dependency import (
    enforce_public_network_runtime_environment,
)
from woobe_api.http.shared.adapters import request_adapter, response_adapter


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
        controller = PublicRuntimeStreamController(*build_public_stream_components())
        return await controller.handle(request)

    async def validate_contracts(
        self,
        principal: ProjectApiPrincipal,
        *,
        output_contract,
        external_context,
    ):
        target_id = principal.target_id or principal.agent_id
        environment = principal.environment
        if (
            principal.kind != "runtime"
            or principal.target_type not in {"agent", "network"}
            or target_id is None
            or environment not in {"staging", "production"}
        ):
            raise ValidationError("Runtime Key binding is incomplete")

        if principal.target_type == "agent":
            snapshot = await build_agent_runtime_contract_reader().read(
                agent_id=target_id,
                project_id=principal.project_id,
                environment=environment,
            )
        else:
            snapshot = await build_network_service().runtime_contract_snapshot(
                network_id=target_id,
                project_id=principal.project_id,
                environment=environment,
            )

        output_result = compare_contract_schema(
            snapshot.output_contract,
            output_contract,
        )
        external_context_result = compare_contract_schema(
            snapshot.external_context,
            external_context,
        )
        return {
            "success": True,
            "data": {
                "valid": (
                    output_result["valid"]
                    and external_context_result["valid"]
                ),
                "target_type": principal.target_type,
                "target_id": str(target_id),
                "environment": environment,
                "release_id": snapshot.release_id,
                "release_version": snapshot.release_version,
                "output_contract": output_result,
                "external_context": external_context_result,
            },
        }

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
