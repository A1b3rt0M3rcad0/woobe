from modules.core.domain.errors import ApiKeyNotFoundError, DuplicateSlugError, ProjectNotFoundError


class TestProjectNotFoundError:
    def test_is_exception(self):
        assert issubclass(ProjectNotFoundError, Exception)

    def test_default_message(self):
        err = ProjectNotFoundError("Project not found")
        assert str(err) == "Project not found"


class TestApiKeyNotFoundError:
    def test_is_exception(self):
        assert issubclass(ApiKeyNotFoundError, Exception)

    def test_default_message(self):
        err = ApiKeyNotFoundError("API key not found")
        assert str(err) == "API key not found"


class TestDuplicateSlugError:
    def test_is_exception(self):
        assert issubclass(DuplicateSlugError, Exception)

    def test_default_message(self):
        err = DuplicateSlugError("Duplicate slug")
        assert str(err) == "Duplicate slug"
