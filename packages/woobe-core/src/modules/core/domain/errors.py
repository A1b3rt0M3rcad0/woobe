from shared.contracts.errors import ConflictError, NotFoundError


class ProjectNotFoundError(NotFoundError):
    pass


class ApiKeyNotFoundError(NotFoundError):
    pass


class ApiKeyNotActiveError(ConflictError):
    pass


class DuplicateSlugError(ConflictError):
    pass
