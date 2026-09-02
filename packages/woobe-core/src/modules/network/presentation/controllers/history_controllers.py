from uuid import UUID

from modules.network.application.dtos.history import (
    ListNetworkExecutionEventsInput,
    ListNetworkSessionMessagesInput,
    ListNetworkSessionsInput,
    NetworkMessageHistoryOutput,
    ResetNetworkSessionContextInput,
)
from modules.network.application.interfaces.use_case import UseCase
from modules.network.presentation.controllers.project_authorization import (
    authorize_project,
    project_id_from_request,
)
from shared.contracts.errors import ValidationError
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response
from shared.presentation.interface.controller import Controller


def _query_int(request: Request, name: str, default: int) -> int:
    value = request.query_params.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{name} must be an integer") from exc


def _message_payload(item: NetworkMessageHistoryOutput) -> dict:
    payload = item.model_dump(exclude={"execution"})
    execution = item.execution
    if execution is None:
        payload["execution"] = None
        return payload

    execution_payload = execution.model_dump(exclude={"events"})
    execution_payload["events"] = [
        {
            "id": event.id,
            "sequence": event.sequence,
            "event_type": event.event_type,
            "invocation_id": event.invocation_id,
            "parent_invocation_id": event.parent_invocation_id,
            "node_id": event.node_id,
            "agent_id": event.agent_id,
            "depth": event.depth,
            "data": event.payload,
            "created_at": event.created_at,
        }
        for event in execution.events
    ]
    payload["execution"] = execution_payload
    return payload


class ListNetworkSessionsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        result = await self._use_case.execute(
            ListNetworkSessionsInput(
                project_id=project_id,
                network_id=UUID(str(request.path_params["network_id"])),
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": [item.model_dump() for item in result]},
        )


class ListNetworkSessionMessagesController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        offset = max(0, _query_int(request, "offset", 0))
        limit = min(500, max(1, _query_int(request, "limit", 200)))
        result = await self._use_case.execute(
            ListNetworkSessionMessagesInput(
                project_id=project_id,
                network_id=UUID(str(request.path_params["network_id"])),
                network_session_id=UUID(
                    str(request.path_params["network_session_id"])
                ),
                offset=offset,
                limit=limit,
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": [_message_payload(item) for item in result]},
        )


class ResetNetworkSessionContextController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        network_session_id = UUID(str(request.path_params["network_session_id"]))
        await self._use_case.execute(
            ResetNetworkSessionContextInput(
                project_id=project_id,
                network_id=UUID(str(request.path_params["network_id"])),
                network_session_id=network_session_id,
            )
        )
        return Response(
            status_code=200,
            body={
                "success": True,
                "data": {"network_session_id": str(network_session_id)},
            },
        )


class ListNetworkExecutionEventsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        project_id = project_id_from_request(request)
        authorize_project(request, project_id)
        after_sequence = max(0, _query_int(request, "after_sequence", 0))
        result = await self._use_case.execute(
            ListNetworkExecutionEventsInput(
                project_id=project_id,
                execution_id=UUID(str(request.path_params["execution_id"])),
                after_sequence=after_sequence,
                limit=500,
            )
        )
        return Response(
            status_code=200,
            body={"success": True, "data": [item.model_dump() for item in result]},
        )
