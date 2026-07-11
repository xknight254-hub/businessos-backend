"""Structured logging for BusinessOS backend.

Provides a JSON formatter with request correlation IDs and basic PII
redaction. Modules should call ``get_logger(__name__)`` instead of the
stdlib ``logging.getLogger`` so logs stay structured and consistent.
"""
from __future__ import annotations

import json
import logging
import sys
import uuid
from typing import Any, Optional

# Fields that must never be logged in cleartext.
_SENSITIVE_KEYS = {
    "password",
    "pin",
    "secret",
    "secret_key",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "mpesa_consumer_secret",
    "mpesa_passkey",
    "openai_api_key",
    "etims_api_key",
    "whatsapp_api_token",
    "authorization",
}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in _SENSITIVE_KEYS else _redact(v)) for k, v in value.items()}
    if isinstance(value, str) and len(value) > 12 and any(
        s in value.lower() for s in ("key", "token", "secret", "password", "pin")
    ):
        return value[:4] + "***"  # keep a short prefix for traceability
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Merge any structured kwargs the caller attached via extra={...}
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(_redact(extra))
        if record.exc_info is None and record.args and not isinstance(record.msg, str):
            payload["msg"] = str(record.msg)
        payload.pop("exc_info", None)
        payload.pop("args", None)
        return json.dumps(payload, default=str)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def new_correlation_id() -> str:
    return uuid.uuid4().hex
