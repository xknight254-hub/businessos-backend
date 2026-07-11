"""Regression tests for M1.4: routers raise typed BusinessError, not raw HTTPException.

Confirms the uniform error schema is preserved after the service-layer
validation refactor (auth, products, customers, sales, payments, automation).
"""
from fastapi.testclient import TestClient

from app.core.exceptions import (
    NotFoundError, ConflictError, BadRequestError, ForbiddenError, UnauthorizedError,
)
from app.main import app


def test_typed_errors_map_to_uniform_schema():
    cases = [
        ("/_m14_nf", NotFoundError("nope"), 404, "not_found"),
        ("/_m14_cf", ConflictError("dup"), 409, "conflict"),
        ("/_m14_br", BadRequestError("bad"), 400, "bad_request"),
        ("/_m14_fb", ForbiddenError("no"), 403, "forbidden"),
        ("/_m14_ua", UnauthorizedError("auth"), 401, "unauthorized"),
    ]
    client = TestClient(app)
    for path, exc, code, err_code in cases:
        def _handler(e=exc):
            raise e
        app.get(path)(_handler)
        r = client.get(path)
        assert r.status_code == code, (path, r.status_code, r.text)
        body = r.json()
        assert body["error"]["code"] == err_code, body
        assert "request_id" in body["error"]
