CHAT_SURFACE_ACCESS_KEY_SCOPE_ORDER = (
    "surface:sessions:create",
    "surface:sessions:token:issue",
    "surface:sessions:archive",
)
CHAT_SURFACE_ACCESS_KEY_SCOPES = frozenset(CHAT_SURFACE_ACCESS_KEY_SCOPE_ORDER)

__all__ = [
    "CHAT_SURFACE_ACCESS_KEY_SCOPE_ORDER",
    "CHAT_SURFACE_ACCESS_KEY_SCOPES",
]
