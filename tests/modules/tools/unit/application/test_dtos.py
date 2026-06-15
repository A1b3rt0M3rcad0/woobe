from uuid import uuid4

from modules.tools.application.dtos.tools_dtos import (
    CreateSecretInput,
    CreateSecretOutput,
    CreateToolInput,
    CreateToolOutput,
    DeleteToolInput,
    ExecuteToolInput,
    ExecuteToolOutput,
    ListSecretsInput,
    ListToolsByAgentInput,
    ListToolsInput,
    TestToolInput,
    TestToolOutput,
    UpdateToolInput,
    UpdateToolStatusInput,
)


class TestCreateToolInput:
    def test_valid_input(self):
        dto = CreateToolInput(project_id=uuid4(), name="test-tool")
        assert dto.name == "test-tool"
        assert dto.risk_level.value == "low"


class TestCreateToolOutput:
    def test_valid_output(self):
        dto = CreateToolOutput(
            id=uuid4(), project_id=uuid4(), name="t", description=None,
            type="function", config=None, input_schema=None, output_schema=None,
            risk_level="low", timeout_ms=None, status="active",
        )
        assert dto.name == "t"


class TestCreateSecretInput:
    def test_valid_input(self):
        dto = CreateSecretInput(project_id=uuid4(), name="key", value="secret")
        assert dto.name == "key"


class TestCreateSecretOutput:
    def test_valid_output(self):
        dto = CreateSecretOutput(id=uuid4(), project_id=uuid4(), name="k", type="custom", data=None)
        assert dto.name == "k"


class TestUpdateToolInput:
    def test_valid_input(self):
        dto = UpdateToolInput(name="updated")
        assert dto.name == "updated"


class TestUpdateToolStatusInput:
    def test_valid_input(self):
        dto = UpdateToolStatusInput(status="active")
        assert dto.status == "active"


class TestDeleteToolInput:
    def test_valid_input(self):
        dto = DeleteToolInput(tool_id=uuid4())
        assert dto.tool_id is not None


class TestTestToolInput:
    def test_valid_input(self):
        dto = TestToolInput(config={})
        assert dto.config == {}


class TestTestToolOutput:
    def test_valid_output(self):
        dto = TestToolOutput(success=True)
        assert dto.success is True


class TestExecuteToolInput:
    def test_valid_input(self):
        dto = ExecuteToolInput(tool_id=uuid4())
        assert dto.tool_id is not None


class TestExecuteToolOutput:
    def test_valid_output(self):
        dto = ExecuteToolOutput(success=True)
        assert dto.success is True


class TestListToolsInput:
    def test_valid_input(self):
        dto = ListToolsInput(project_id=uuid4())
        assert dto.project_id is not None


class TestListToolsByAgentInput:
    def test_valid_input(self):
        dto = ListToolsByAgentInput(agent_id=uuid4())
        assert dto.agent_id is not None


class TestListSecretsInput:
    def test_valid_input(self):
        dto = ListSecretsInput(project_id=uuid4())
        assert dto.project_id is not None
