from modules.agent.application.interfaces.use_case import UseCase
from modules.agent.application.dtos.tools_dtos import ListToolsInput
from modules.agent.application.interfaces.mcp_readiness import with_mcp_readiness
from modules.agent.presentation.schemas import ToolResponse
from shared.presentation.contracts import OperationOutcome
from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult
from shared.presentation.interface.controller import Controller


def render_tool(tool) -> dict:
    data = dict(vars(tool))
    data["config"] = with_mcp_readiness(data.get("config"), data.get("status"))
    return ToolResponse(**data).model_dump()


class ListToolsController(Controller):
    def __init__(self, use_case: UseCase) -> None:
        self._use_case = use_case

    async def handle(self, request: OperationRequest) -> OperationResult:
        project_id = request.query_params.get("project_id")
        input_dto = ListToolsInput(project_id=project_id)
        result = await self._use_case.execute(input_dto)
        return OperationResult(
            outcome=OperationOutcome.SUCCESS,
            body={"success": True, "message": "ok", "data": [render_tool(item) for item in result]},
        )

