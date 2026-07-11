"""Tests for Phase 1 foundation: structured logging + centralized errors."""
from fastapi.testclient import TestClient

from app.core.exceptions import BusinessError, ConflictError, NotFoundError
from app.main import app


def test_unhandled_exception_returns_uniform_shape():
    # Force an unhandled error via a temporary route.
    @app.get("/_test_boom")
    async def _boom():
        raise RuntimeError("kaboom")

    client = TestClient(app)
    r = client.get("/_app_nonexistent_route_xyz")
    # Unknown route -> 404 uniform error shape
    assert r.status_code == 404
    body = r.json()
    assert "error" in body
    assert "code" in body["error"]
    assert "request_id" in body["error"]


def test_business_error_handler_shape():
    @app.get("/_test_conflict")
    async def _conflict():
        raise ConflictError("Phone already registered")

    client = TestClient(app)
    r = client.get("/_test_conflict")
    assert r.status_code == 409
    body = r.json()
    assert body["error"]["code"] == "conflict"
    assert body["error"]["message"] == "Phone already registered"
    assert body["error"]["request_id"]


def test_correlation_id_header_present():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert "x-request-id" in r.headers


def test_validation_error_uniform_shape():
    client = TestClient(app)
    # send-code requires a valid +254... phone; send invalid -> 422 uniform
    r = client.post("/auth/send-code", json={"phone": "invalid"})
    assert r.status_code == 422
    assert "error" in r.json()
    assert r.json()["error"]["code"] == "validation_error"
