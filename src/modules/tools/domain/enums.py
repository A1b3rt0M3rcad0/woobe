from __future__ import annotations

from enum import StrEnum, auto


class ToolType(StrEnum):
    FUNCTION = auto()
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
