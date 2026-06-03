import uuid

from modules.tools.domain.errors import (
    DuplicateSecretError,
    SecretNotFoundError,
    ToolNotFoundError,
)
from shared.domain.errors import ConflictError, NotFoundError


class TestToolNotFoundError:
    def test_inheritance(self):
        e = ToolNotFoundError(tool_id=uuid.uuid4())
        assert isinstance(e, NotFoundError)

    def test_message(self):
        tid = uuid.uuid4()
        e = ToolNotFoundError(tool_id=tid)
        assert str(e) == f"Tool not found: {tid}"
        assert e.tool_id == tid


class TestSecretNotFoundError:
    def test_inheritance(self):
        e = SecretNotFoundError(secret_id=uuid.uuid4())
        assert isinstance(e, NotFoundError)

    def test_message(self):
        sid = uuid.uuid4()
        e = SecretNotFoundError(secret_id=sid)
        assert str(e) == f"Secret not found: {sid}"
        assert e.secret_id == sid


class TestDuplicateSecretError:
    def test_inheritance(self):
        e = DuplicateSecretError(name="key", project_id=uuid.uuid4())
        assert isinstance(e, ConflictError)

    def test_message(self):
        pid = uuid.uuid4()
        e = DuplicateSecretError(name="my-api-key", project_id=pid)
        assert str(e) == f"Secret 'my-api-key' already exists in project {pid}"
        assert e.name == "my-api-key"
        assert e.project_id == pid
