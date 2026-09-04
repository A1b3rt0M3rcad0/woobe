from shared.contracts.errors import ConflictError, NotFoundError


class EmailAlreadyExistsError(ConflictError):
    pass


class WorkspaceNotFoundError(NotFoundError):
    pass


class UserNotFoundError(NotFoundError):
    pass


class InvalidCredentialsError(NotFoundError):
    pass

