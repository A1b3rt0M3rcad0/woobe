from uuid import uuid4

from modules.tools.domain.errors import DuplicateSecretError, SecretNotFoundError, ToolNotFoundError


class TestToolNotFoundError:
    def test_is_exception(self):
        assert issubclass(ToolNotFoundError, Exception)

    def test_default_message(self):
        tool_id = uuid4()
        err = ToolNotFoundError(tool_id)
        assert str(err) == f"Tool not found: {tool_id}"


class TestSecretNotFoundError:
    def test_is_exception(self):
        assert issubclass(SecretNotFoundError, Exception)

    def test_default_message(self):
        secret_id = uuid4()
        err = SecretNotFoundError(secret_id)
        assert str(err) == f"Secret not found: {secret_id}"


class TestDuplicateSecretError:
    def test_is_exception(self):
        assert issubclass(DuplicateSecretError, Exception)

    def test_default_message(self):
        project_id = uuid4()
        err = DuplicateSecretError("my-secret", project_id)
        assert str(err) == f"Secret 'my-secret' already exists in project {project_id}"
