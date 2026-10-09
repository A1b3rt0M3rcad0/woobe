class DomainError(Exception):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class SnapshotCaptureConflict(ConflictError):
    """Safe owner diagnostic for an incomplete or inconsistent portable capture."""

    def __init__(self, code: str, message: str, *, path: str = ""):
        super().__init__(message)
        self.code, self.path = code, path


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
