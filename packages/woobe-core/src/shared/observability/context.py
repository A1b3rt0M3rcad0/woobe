from contextvars import ContextVar

request_id_context: ContextVar[str] = ContextVar("request_id", default="-")
correlation_id_context: ContextVar[str] = ContextVar("correlation_id", default="-")
