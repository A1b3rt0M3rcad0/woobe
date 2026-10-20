from __future__ import annotations


class WoobeError(Exception):
    """Base exception for SDK failures."""


class WoobeRequestError(WoobeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code

    @property
    def retryable(self) -> bool:
        return self.status_code is not None and self.status_code >= 500


class WoobeAuthenticationError(WoobeRequestError):
    """Runtime Key authentication or authorization failed."""


class WoobeConnectionError(WoobeError):
    """The transport connection failed or ended before terminal runtime state."""


class WoobeProtocolError(WoobeError):
    """The Runtime API returned a frame that violates the SDK contract."""


class WoobeStreamGapError(WoobeProtocolError):
    """A logical runtime event sequence gap was detected."""


class WoobeRecoveryError(WoobeError):
    """The SDK cannot safely recover the canonical Run without risking duplication."""
