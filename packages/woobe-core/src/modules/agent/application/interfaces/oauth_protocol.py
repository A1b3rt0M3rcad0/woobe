"""Private owner-to-transport protocol marker; never a request field."""
from contextvars import ContextVar

private_oauth_protocol_response = ContextVar('private_oauth_protocol_response', default=False)
