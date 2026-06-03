from enum import StrEnum, auto


class Provider(StrEnum):
    openai = auto()
    anthropic = auto()
    google = auto()
    azure = auto()
    aws_bedrock = auto()
    groq = auto()


class CredentialStatus(StrEnum):
    active = auto()
    expired = auto()
    revoked = auto()
    invalid = auto()


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
