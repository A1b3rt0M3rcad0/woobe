from modules.core.domain.errors import (
    ApiKeyNotFoundError,
    DuplicateSlugError,
    ProjectNotFoundError,
)
from shared.domain.errors import ConflictError, DomainError, NotFoundError


class TestProjectNotFoundError:
    def test_inheritance(self):
        err = ProjectNotFoundError("proj-id")
        assert isinstance(err, Exception)
        assert isinstance(err, DomainError)
        assert isinstance(err, NotFoundError)
        assert isinstance(err, ProjectNotFoundError)

    def test_message_format(self):
        err = ProjectNotFoundError("proj-123")
        assert "proj-123" in str(err)


class TestApiKeyNotFoundError:
    def test_inheritance(self):
        err = ApiKeyNotFoundError("key-id")
        assert isinstance(err, Exception)
        assert isinstance(err, DomainError)
        assert isinstance(err, NotFoundError)
        assert isinstance(err, ApiKeyNotFoundError)

    def test_message_format(self):
        err = ApiKeyNotFoundError("key-456")
        assert "key-456" in str(err)


class TestDuplicateSlugError:
    def test_inheritance(self):
        err = DuplicateSlugError("slug already exists")
        assert isinstance(err, Exception)
        assert isinstance(err, DomainError)
        assert isinstance(err, ConflictError)
        assert isinstance(err, DuplicateSlugError)

    def test_message_format(self):
        err = DuplicateSlugError("duplicate slug: my-project")
        assert "duplicate slug" in str(err)
