"""Smoke test for the MCP surface (`podcast_helper.mcp`).

Gated on the ``mcp`` extra (FastAPI + fastapi-mcp). Importing `podcast_helper.mcp`
mounts an MCP endpoint onto the FastAPI app; we check the endpoint is wired
and that the HTTP API keeps serving alongside it. Skips cleanly when the
extra isn't installed, so the default suite is unaffected.
"""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("fastapi_mcp")
starlette_testclient = pytest.importorskip("starlette.testclient")

from podcast_helper import mcp as mcp_module  # noqa: E402  (import mounts MCP on the app)


def test_mcp_endpoint_is_mounted() -> None:
    """Importing the module publishes an `/mcp` endpoint named 'podcast-helper'."""
    paths = {r.path for r in mcp_module.app.routes}
    assert any("/mcp" in p for p in paths), paths
    assert mcp_module.mcp.name == "podcast-helper"


def test_api_still_served_next_to_mcp() -> None:
    """The FastAPI routes still work once the MCP endpoint is mounted."""
    client = starlette_testclient.TestClient(mcp_module.app)
    res = client.get("/health")
    assert res.status_code == 200 and res.json()["status"] == "ok"


def test_mcp_description_names_the_kinds_probe_returns() -> None:
    """The tool description must use probe's real ``source_kind`` values."""
    desc = mcp_module.mcp.description
    for kind in ("file", "direct_audio", "ytdlp:<extractor>"):
        assert kind in desc, kind
    assert "yt-dlp-<extractor>" not in desc
    assert "/ rss /" not in desc
