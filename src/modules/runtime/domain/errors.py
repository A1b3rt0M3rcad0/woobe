from __future__ import annotations

from uuid import UUID

from shared.domain.errors import NotFoundError


class SessionNotFoundError(NotFoundError):
    def __init__(self, session_id: UUID) -> None:
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class MessageNotFoundError(NotFoundError):
    def __init__(self, message_id: UUID) -> None:
        self.message_id = message_id
        super().__init__(f"Message not found: {message_id}")


class AskJobNotFoundError(NotFoundError):
    def __init__(self, job_id: UUID) -> None:
        self.job_id = job_id
        super().__init__(f"Ask job not found: {job_id}")
