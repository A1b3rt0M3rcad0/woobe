from datetime import datetime, timezone
from uuid import uuid4

from modules.core.application.dtos.create_project_dtos import (
    CreateProjectInput,
    CreateProjectOutput,
)
from modules.core.application.dtos.get_project_dtos import GetProjectOutput
from modules.core.application.dtos.update_project_dtos import UpdateProjectInput
from modules.core.domain.enums import ProjectStatus


class TestCreateProjectInput:
    def test_valid_input(self):
        dto = CreateProjectInput(workspace_id=uuid4(), name="Test Project", slug="test-project")
        assert dto.name == "Test Project"
        assert dto.slug == "test-project"


class TestCreateProjectOutput:
    def test_valid_output(self):
        uid = uuid4()
        now = datetime.now(timezone.utc)
        dto = CreateProjectOutput(id=uid, workspace_id=uuid4(), name="Test Project", slug="test-project", status=ProjectStatus.active, created_at=now)
        assert dto.id == uid
        assert dto.name == "Test Project"


class TestGetProjectOutput:
    def test_valid_output(self):
        uid = uuid4()
        dto = GetProjectOutput(id=uid, workspace_id=uuid4(), name="Project", slug="project", status=ProjectStatus.active)
        assert dto.slug == "project"


class TestUpdateProjectInput:
    def test_valid_input(self):
        dto = UpdateProjectInput(project_id=uuid4(), name="Updated", slug="updated")
        assert dto.name == "Updated"
