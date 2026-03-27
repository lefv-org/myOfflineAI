"""
Smoke tests for myOfflineAI.
Verifies core endpoints respond after simplification changes.
Does not require a running Ollama instance.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Create a test client for the FastAPI app."""
    from open_webui.main import app
    with TestClient(app) as c:
        yield c


class TestAppStarts:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_app_config_endpoint(self, client):
        response = client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data or "name" in data

    def test_auth_signin_rejects_empty(self, client):
        response = client.post("/api/v1/auths/signin", json={})
        assert response.status_code in (400, 401, 422)


class TestOllamaRouterRegistered:
    def test_ollama_endpoint_exists(self, client):
        """Ollama router should be registered (will 401 without auth, but not 404)."""
        response = client.get("/ollama/api/tags")
        assert response.status_code != 404


class TestRemovedRoutersGone:
    """After Phase 2, these API endpoints should not return JSON (the SPA catch-all
    serves index.html for unregistered paths, so status is 200 but content is HTML)."""

    @pytest.mark.parametrize("path", [
        "/api/v1/channels",
        "/api/v1/notes",
        "/api/v1/scim/v2/Users",
        "/api/v1/pipelines",
        "/api/v1/terminals",
        "/openai/api/chat/completions",
    ])
    def test_removed_endpoint_has_no_json_api(self, client, path):
        response = client.get(path)
        content_type = response.headers.get("content-type", "")
        assert "application/json" not in content_type, (
            f"{path} should be removed but still serves a JSON API response"
        )
