from uuid import uuid4
from datetime import datetime, timezone

from modules.identity.application.dtos.identity_dtos import (
    CreateUserInput,
    CreateUserOutput,
    CreateOrganizationInput,
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


class TestCreateOrganizationInput:
    def test_valid_input(self):
        dto = CreateOrganizationInput(name="My Org", slug="my-org")
        assert dto.name == "My Org"
        assert dto.slug == "my-org"


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
