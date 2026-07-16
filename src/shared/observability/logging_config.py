from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from shared.observability.context import correlation_id_context, request_id_context
from shared.security.redaction import SensitiveDataLoggingFilter, redact_sensitive_data

_STANDARD_LOG_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_context.get()
        record.correlation_id = correlation_id_context.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_data(record.getMessage()),
            "request_id": getattr(record, "request_id", "-"),
            "correlation_id": getattr(record, "correlation_id", "-"),
        }
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _STANDARD_LOG_RECORD_FIELDS
            and key not in {"request_id", "correlation_id", "message", "asctime"}
            and not key.startswith("_")
        }
        if extras:
            payload["fields"] = redact_sensitive_data(extras)
        if record.exc_info:
            payload["exception"] = redact_sensitive_data(self.formatException(record.exc_info))
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging(*, level: str, json_logs: bool) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(SensitiveDataLoggingFilter())
    handler.addFilter(RequestContextFilter())
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s "
                "request_id=%(request_id)s correlation_id=%(correlation_id)s: "
                "%(message)s"
            )
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
