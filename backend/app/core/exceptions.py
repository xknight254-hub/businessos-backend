"""Centralized exception handling for BusinessOS backend.

Define domain exceptions and wire uniform FastAPI handlers so that no
stack traces leak to clients and every error returns a consistent shape:

    {"error": {"code": "...", "message": "...", "request_id": "..."}}
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from jose import JWTError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

logger = get_logger(__name__)


class BusinessError(Exception):
    """Base class for expected, domain-level errors."""

    code = "business_error"
    status_code = 400

    def __init__(self, message: str, *, code: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class NotFoundError(BusinessError):
    code = "not_found"
    status_code = 404


class ConflictError(BusinessError):
    code = "conflict"
    status_code = 409


class UnauthorizedError(BusinessError):
    code = "unauthorized"
    status_code = 401


class ForbiddenError(BusinessError):
    code = "forbidden"
    status_code = 403


def _body(request: Request, code: str, message: str, status_code: int) -> JSONResponse:
    rid = getattr(request.state, "correlation_id", None)
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": rid}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        logger.warning("http_error", extra={"code": exc.status_code, "detail": str(exc.detail)})
        return _body(request, "http_error", str(exc.detail), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        logger.warning("validation_error", extra={"errors": exc.errors()})
        return _body(request, "validation_error", "Request validation failed", status.HTTP_422_UNPROCESSABLE_ENTITY)

    @app.exception_handler(JWTError)
    async def _jwt(request: Request, exc: JWTError):
        logger.warning("jwt_error", extra={"detail": str(exc)})
        return _body(request, "unauthorized", "Invalid or expired token", status.HTTP_401_UNAUTHORIZED)

    @app.exception_handler(BusinessError)
    async def _business(request: Request, exc: BusinessError):
        logger.warning("business_error", extra={"code": exc.code, "detail": exc.message})
        return _body(request, exc.code, exc.message, exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        logger.error("unhandled_error", extra={"type": type(exc).__name__, "detail": str(exc)})
        return _body(request, "internal_error", "Internal server error", status.HTTP_500_INTERNAL_SERVER_ERROR)
