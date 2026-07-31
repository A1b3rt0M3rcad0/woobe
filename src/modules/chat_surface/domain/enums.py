from enum import StrEnum


class ChatSurfaceTargetType(StrEnum):
    AGENT = "agent"
    NETWORK = "network"


class ChatSurfaceStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


CHAT_SURFACE_KEY_SCOPES = frozenset(
    {
        "surface:sessions:create",
        "surface:sessions:token:issue",
        "surface:sessions:archive",
    }
)

