class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class PreconditionFailedError(ConflictError):
    pass


class ValidationError(DomainError):
    pass


class AuthenticationError(DomainError):
    pass


class AuthorizationError(DomainError):
    pass


class PayloadTooLargeError(DomainError):
    pass


class RuntimeTimeoutError(DomainError):
    pass


class RateLimitError(DomainError):
    def __init__(self, message: str, *, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after
