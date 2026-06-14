from enum import StrEnum, auto


class Provider(StrEnum):
    openai = auto()
    anthropic = auto()
    google = auto()
    azure = auto()
    aws_bedrock = auto()
    custom = auto()
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


class CollectionStatus(StrEnum):
    ACTIVE = auto()
    ARCHIVED = auto()
    DELETED = auto()


class DocumentStatus(StrEnum):
    UPLOADED = auto()
    PARSING = auto()
    CHUNKING = auto()
    INDEXING = auto()
    READY = auto()
    FAILED = auto()
    DELETED = auto()


class ParserType(StrEnum):
    PDF = auto()
    DOCX = auto()
    MD = auto()
    HTML = auto()
    TEXT = auto()
    CSV = auto()
    JSON = auto()
    IMAGE = auto()


class KnowledgeVersionStatus(StrEnum):
    DRAFT = auto()
    RELEASED = auto()
    ARCHIVED = auto()
