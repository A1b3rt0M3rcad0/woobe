import uuid

from modules.runtime.domain.errors import MessageNotFoundError, SessionNotFoundError
from shared.domain.errors import NotFoundError


class TestSessionNotFoundError:
    def test_inheritance(self):
        e = SessionNotFoundError(session_id=uuid.uuid4())
        assert isinstance(e, NotFoundError)

    def test_message(self):
        sid = uuid.uuid4()
        e = SessionNotFoundError(session_id=sid)
        assert str(e) == f"Session not found: {sid}"
        assert e.session_id == sid


class TestMessageNotFoundError:
    def test_inheritance(self):
        e = MessageNotFoundError(message_id=uuid.uuid4())
        assert isinstance(e, NotFoundError)

    def test_message(self):
        mid = uuid.uuid4()
        e = MessageNotFoundError(message_id=mid)
        assert str(e) == f"Message not found: {mid}"
        assert e.message_id == mid
