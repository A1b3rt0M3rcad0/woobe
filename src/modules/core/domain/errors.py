from shared.domain.errors import ConflictError, NotFoundError


class ProjectNotFoundError(NotFoundError):
    pass


class ApiKeyNotFoundError(NotFoundError):
    pass


class DuplicateSlugError(ConflictError):
    pass
