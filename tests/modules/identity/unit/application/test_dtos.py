from uuid import uuid4
from datetime import datetime, timezone

from modules.identity.application.dtos.identity_dtos import (
    CreateUserInput,
    CreateUserOutput,
    CreateWorkspaceInput,
    LoginInput,
    GetUserOutput,
)
from modules.identity.domain.enums import UserStatus


class TestCreateUserInput:
    def test_valid_input(self):
        dto = CreateUserInput(email="test@example.com", password="secret123")
        assert dto.email == "test@example.com"
        assert dto.password == "secret123"


class TestCreateUserOutput:
    def test_valid_output(self):
        uid = uuid4()
        now = datetime.now(timezone.utc)
        dto = CreateUserOutput(id=uid, email="test@example.com", status=UserStatus.active, created_at=now)
        assert dto.id == uid
        assert dto.email == "test@example.com"


class TestCreateWorkspaceInput:
    def test_valid_input(self):
        dto = CreateWorkspaceInput(name="My Workspace", slug="my-workspace")
        assert dto.name == "My Workspace"
        assert dto.slug == "my-workspace"


class TestLoginInput:
    def test_valid_input(self):
        dto = LoginInput(email="user@example.com", password="pass")
        assert dto.email == "user@example.com"


class TestGetUserOutput:
    def test_valid_output(self):
        uid = uuid4()
        now = datetime.now(timezone.utc)
        dto = GetUserOutput(id=uid, email="a@b.com", status=UserStatus.active, created_at=now)
        assert dto.email == "a@b.com"
