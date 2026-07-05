"""Basic health endpoint tests."""

from http import HTTPStatus

import pytest

from bgmon_api.app import create_app


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = create_app()
    app.config.update({"TESTING": True})
    return app


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()


def test_health_returns_ok(client):
    """Health endpoint should return ok status."""
    response = client.get("/health")
    assert response.status_code == HTTPStatus.OK
    data = response.get_json()
    assert data["status"] == "ok"
    assert "is_leader" in data
    assert "last_libre_fetch_at" in data
    assert "instance_id" in data
