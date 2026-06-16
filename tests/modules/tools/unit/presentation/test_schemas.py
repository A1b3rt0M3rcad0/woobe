from uuid import uuid4

from modules.tools.presentation.schemas import (
    CreateSecretRequest,
    CreateToolRequest,
    ExecuteToolRequest as SchemaExecuteToolRequest,
    ExecuteToolResponse as SchemaExecuteToolResponse,
    SecretResponse,
    TestToolRequest as SchemaTestToolRequest,
    TestToolResponse as SchemaTestToolResponse,
    ToolResponse,
    UpdateToolRequest,
    UpdateToolStatusRequest,
)


class TestCreateToolRequest:
    def test_valid_request(self):
        req = CreateToolRequest(project_id=uuid4(), name="test")
        assert req.name == "test"


class TestToolResponseSchema:
    def test_valid_response(self):
        resp = ToolResponse(
            id=uuid4(), project_id=uuid4(), name="t", description=None,
            type="function", config=None, input_schema=None, output_schema=None,
            risk_level="low", timeout_ms=None, status="active",
        )
        assert resp.status == "active"


class TestUpdateToolRequest:
    def test_valid_request(self):
        req = UpdateToolRequest(name="updated")
        assert req.name == "updated"


class TestUpdateToolStatusRequest:
    def test_valid_request(self):
        req = UpdateToolStatusRequest(status="active")
        assert req.status == "active"


class TestSchemaTestToolRequest:
    def test_valid_request(self):
        req = SchemaTestToolRequest(config={})
        assert req.config == {}


class TestSchemaTestToolResponse:
    def test_valid_response(self):
        resp = SchemaTestToolResponse(success=True)
        assert resp.success is True


class TestExecuteToolRequest:
    def test_valid_request(self):
        req = SchemaExecuteToolRequest(tool_id=uuid4())
        assert req.tool_id is not None


class TestSchemaExecuteToolResponse:
    def test_valid_response(self):
        resp = SchemaExecuteToolResponse(success=True)
        assert resp.success is True


class TestCreateSecretRequest:
    def test_valid_request(self):
        req = CreateSecretRequest(project_id=uuid4(), name="key", value="v")
        assert req.name == "key"


class TestSecretResponse:
    def test_valid_response(self):
        resp = SecretResponse(id=uuid4(), project_id=uuid4(), name="k", type="custom", data=None)
        assert resp.name == "k"
