from shared.domain.errors import NotFoundError


class CredentialNotFoundError(NotFoundError):
    pass


class AgentNotFoundError(NotFoundError):
    pass
