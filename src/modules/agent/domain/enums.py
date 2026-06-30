from enum import StrEnum, auto


class Provider(StrEnum):
    openai = auto()
    anthropic = auto()
    google = auto()
    azure = auto()
    aws_bedrock = auto()
    custom = auto()
    openrouter = auto()
    groq = auto()


class CredentialStatus(StrEnum):
    active = auto()
    expired = auto()
    revoked = auto()
    invalid = auto()
    archived = auto()


class ProviderModelStatus(StrEnum):
    active = auto()
    inactive = auto()
    archived = auto()


class AgentStatus(StrEnum):
    active = auto()
    inactive = auto()
    archived = auto()


class SessionMode(StrEnum):
    stateless = auto()
    stateful = auto()


class AgentType(StrEnum):
    chat = auto()
    completion = auto()
    assistant = auto()
    custom = auto()


class PromptStatus(StrEnum):
    draft = auto()
    released = auto()
    archived = auto()


class ContractStatus(StrEnum):
    draft = auto()
    released = auto()
    archived = auto()


class ValidationMode(StrEnum):
    strict = auto()
    loose = auto()


class ModelConfigStatus(StrEnum):
    draft = auto()
    released = auto()
    archived = auto()


class ReleaseStatus(StrEnum):
    draft = auto()
    staging = auto()
    production = auto()
    archived = auto()
    rolled_back = auto()


class ReleaseTestStatus(StrEnum):
    pending = auto()
    passed = auto()
    failed = auto()
    error = auto()
