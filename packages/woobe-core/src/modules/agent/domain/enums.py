from enum import StrEnum, auto


class Provider(StrEnum):
    openai = auto()
    openai_compatible = auto()
    anthropic = auto()
    deepseek = auto()
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
    released = auto()
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


class SessionStatus(StrEnum):
    ACTIVE = auto()
    WAITING = auto()
    IDLE = auto()
    CLOSED = auto()
    EXPIRED = auto()
    ERROR = auto()


class MessageRole(StrEnum):
    SYSTEM = auto()
    USER = auto()
    ASSISTANT = auto()
    TOOL_CALL = auto()
    TOOL_RESULT = auto()


class RuntimeSessionMode(StrEnum):
    CHAT = auto()
    WORKFLOW = auto()
    AUTONOMOUS = auto()
    BACKGROUND = auto()


class ToolType(StrEnum):
    FUNCTION = auto()
    HTTP = auto()
    MCP = auto()
    # Deprecated compatibility alias for existing persisted tools and clients.
    # New clients must create HTTP tools with ToolType.HTTP instead.
    HTTP_MCP = auto()
    API = auto()
    DATABASE_QUERY = auto()
    WEBHOOK = auto()
    FILE_OPERATION = auto()
    CODE_EXECUTION = auto()
    CUSTOM = auto()


class RiskLevel(StrEnum):
    LOW = auto()
    MEDIUM = auto()
    HIGH = auto()
    CRITICAL = auto()


class SecretType(StrEnum):
    API_KEY = auto()
    OAUTH_TOKEN = auto()
    BASIC_AUTH = auto()
    CERTIFICATE = auto()
    CUSTOM = auto()


class ToolStatus(StrEnum):
    ACTIVE = auto()
    INACTIVE = auto()
    DEPRECATED = auto()
    DISABLED = auto()
