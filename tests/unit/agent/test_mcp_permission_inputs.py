from uuid import uuid4

import pytest
from pydantic import ValidationError
from modules.agent.application.dtos.mcp_permission_dtos import UpdateMcpToolPermissionsInput, BulkUpdateMcpToolPermissionsInput

@pytest.mark.parametrize("mode", ["allow", "deny", "review"])
def test_canonical_modes(mode):
    assert BulkUpdateMcpToolPermissionsInput(tool_id=uuid4(), mode=mode).mode == mode

@pytest.mark.parametrize("permissions", [[], [{"remote_tool_name":" ","mode":"allow"}], [{"remote_tool_name":"search","mode":"unknown"}], [{"remote_tool_name":"search","mode":"allow","conditions":{}}], [{"remote_tool_name":"search","mode":"allow"},{"remote_tool_name":"search","mode":"deny"}]])
def test_invalid_permission_lists(permissions):
    with pytest.raises(ValidationError):
        UpdateMcpToolPermissionsInput(tool_id=uuid4(), permissions=permissions)

@pytest.mark.parametrize("risk", ["", " ", " padded "])
def test_blank_risk_is_not_silently_normalized(risk):
    with pytest.raises(ValidationError):
        BulkUpdateMcpToolPermissionsInput(tool_id=uuid4(), mode="allow", risk_level=risk)
