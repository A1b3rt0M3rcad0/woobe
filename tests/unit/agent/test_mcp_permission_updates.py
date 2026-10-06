from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from modules.agent.application.mcp_permissions import UpdateMcpToolPermissionsUseCase, BulkUpdateMcpToolPermissionsUseCase
from modules.agent.application.dtos.mcp_permission_dtos import UpdateMcpToolPermissionsInput, BulkUpdateMcpToolPermissionsInput
from modules.agent.domain.enums import ToolType

class Repository:
    def __init__(self):
        self.tool = SimpleNamespace(id=uuid4(), type=ToolType.MCP, config={"protocol":"mcp", "discovered_tools":[{"name":"search", "permission":{"mode":"review"}},{"name":"write", "permission":{"mode":"deny"}}]})
        self.writes=0
    async def get_by_id(self, tool_id):
        return self.tool if tool_id==self.tool.id else None
    async def update(self, tool):
        self.writes+=1

@pytest.mark.asyncio
async def test_unknown_permission_does_not_partially_apply():
    repo=Repository(); before=deepcopy(repo.tool.config)
    dto=UpdateMcpToolPermissionsInput(tool_id=repo.tool.id, permissions=[{"remote_tool_name":"search","mode":"allow"},{"remote_tool_name":"missing","mode":"allow"}])
    with pytest.raises(ValueError, match="undiscovered"):
        await UpdateMcpToolPermissionsUseCase(repo).execute(dto)
    assert repo.writes==0 and repo.tool.config==before

@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["allow","deny","review"])
async def test_modes_are_persisted_and_reported(mode):
    repo=Repository()
    result=await UpdateMcpToolPermissionsUseCase(repo).execute(UpdateMcpToolPermissionsInput(tool_id=repo.tool.id, permissions=[{"remote_tool_name":"search","mode":mode}]))
    assert repo.writes==1 and result.permissions[0].mode==mode
    assert result.permissions[1].mode=="deny"
