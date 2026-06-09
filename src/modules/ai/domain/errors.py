from shared.domain.errors import NotFoundError


class CredentialNotFoundError(NotFoundError):
    pass


class AgentNotFoundError(NotFoundError):
    pass


class PromptNotFoundError(NotFoundError):
    pass


class ContractNotFoundError(NotFoundError):
    pass


class ModelConfigNotFoundError(NotFoundError):
    pass


class ReleaseNotFoundError(NotFoundError):
    pass


class ReleaseTestNotFoundError(NotFoundError):
    pass
