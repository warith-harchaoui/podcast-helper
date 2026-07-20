"""
Smoke tests for the FastAPI HTTP surface.

Only exercises endpoints that do not require ffmpeg or the network
(``/health``, plus OpenAPI schema introspection to catch endpoint-name
drift). Heavier round-trip tests belong to the ``integration`` suite
where real feeds and ffmpeg are available.

Usage Example
-------------
>>> #   pytest tests/test_api.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import pytest

# FastAPI + httpx live in the ``[api]`` / ``[dev]`` optional extras.
# Skip cleanly when the environment does not have them.
fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Yield a TestClient bound to the podcast-helper FastAPI app."""
    from podcast_helper.api import app

    with TestClient(app) as c:
        yield c


def test_health_returns_ok(client):
    """``/health`` should return 200 + ``{"status": "ok"}``."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_lists_expected_endpoints(client):
    """The OpenAPI spec should list every expected route path."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    expected = {"/health", "/feed", "/latest", "/probe", "/stream", "/record"}
    assert expected.issubset(set(paths.keys()))


def test_docs_endpoint_is_served(client):
    """``/docs`` should serve the Swagger UI landing HTML."""
    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger" in r.text.lower() or "openapi" in r.text.lower()


def test_gui_returns_200_html(client):
    """``GET /gui`` should return 200 with a self-contained HTML page."""
    r = client.get("/gui")
    assert r.status_code == 200
    # It must be an HTML document (correct content type + a doctype).
    assert r.headers["content-type"].startswith("text/html")
    body = r.text.lower()
    assert "<!doctype html>" in body
    # Sanity-check it is the episode browser and wires the real actions
    # (the JS calls "/feed", "/probe" and "/record", so assert on those).
    assert "episode browser" in body
    assert "/feed" in r.text and "/probe" in r.text and "/record" in r.text


def test_root_redirects_to_gui(client):
    """``GET /`` should redirect (or resolve) to the GUI page."""
    # follow_redirects defaults True in the TestClient; assert we land on HTML.
    r = client.get("/")
    assert r.status_code == 200
    assert "episode browser" in r.text.lower()
