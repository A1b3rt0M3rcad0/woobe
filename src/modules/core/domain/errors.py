from shared.infra.errors import ConflictError, NotFoundError


class ProjectNotFoundError(NotFoundError):
    pass


class ApiKeyNotFoundError(NotFoundError):
    pass


class DuplicateSlugError(ConflictError):
    pass
