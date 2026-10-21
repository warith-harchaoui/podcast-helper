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

import pathlib

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


def _page_name() -> str:
    """The GUI's own name, in whatever language it renders by default.

    Taken from the rendered page rather than from a catalogue lookup, so this
    says "the page shows its own title" without naming a language. It also
    arrives already escaped the way the page escapes it: the French title
    carries an apostrophe, which `render_gui` writes as `&#x27;` — correct
    HTML that a browser renders as an apostrophe, and not the literal the
    catalogue holds.
    """
    import re

    from podcast_helper import gui

    title = re.search(r"<title>([^<]*)</title>", gui.render_gui())
    assert title, "the default page has no <title>"
    return title.group(1).lower()


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
    # Ask the locale file what the page is called rather than hard-coding one
    # language's wording: the page renders in French by default, so asserting
    # the English copy would be testing the default locale, not the page.
    assert _page_name() in body
    assert "/feed" in r.text and "/probe" in r.text and "/record" in r.text


def test_root_redirects_to_gui(client):
    """``GET /`` should redirect (or resolve) to the GUI page."""
    # follow_redirects defaults True in the TestClient; assert we land on HTML.
    r = client.get("/")
    assert r.status_code == 200
    assert _page_name() in r.text.lower()


def test_record_rejects_unsupported_output_format(client):
    """An ``output_format`` outside the known codec table is a clean 400.

    This also covers path traversal: "../../../../tmp/pwned.mp3" is rejected
    for the same reason a bogus extension like "exe" would be — neither is a
    recognized archive codec — so the request never reaches the point where
    the client-supplied string would otherwise be spliced into a filesystem
    path outside the request's own temp directory.
    """
    r = client.post(
        "/record",
        data={"url": "https://example.com/ep.mp3", "output_format": "../../../../tmp/pwned.mp3"},
    )
    assert r.status_code == 400
    assert "unsupported output_format" in r.json()["detail"]

    # A merely-unsupported (but otherwise well-formed) extension must be
    # rejected too, not just a traversal attempt.
    r2 = client.post("/record", data={"url": "https://example.com/ep.mp3", "output_format": "exe"})
    assert r2.status_code == 400


# ---------------------------------------------------------------------------
# Channel flag on /stream and /record -- FastAPI 0.147 checkbox semantics.
# ---------------------------------------------------------------------------
#
# FastAPI 0.147 reads an omitted boolean form field as False whatever default
# is declared, so the on-by-default ``mono=True`` could not survive on the
# wire. The flag is now the off-by-default ``stereo``, and the retired name
# earns a 400 rather than silently inverting a caller's intent.


def test_stream_downmixes_to_mono_when_the_flag_is_omitted(client):
    """An omitted flag must still mean mono.

    ``X-Channels`` reports the resolved choice, so the header is a real
    assertion on the decision without needing ffmpeg or the network: the
    response body is a lazy generator that is never consumed here.
    """
    r = client.post("/stream", data={"url": "https://example.com/ep.mp3"})
    assert r.status_code == 200
    assert r.headers["X-Channels"] == "1"


def test_stream_stereo_preserves_native_channels(client):
    """``stereo=true`` must switch the resolved choice away from mono."""
    r = client.post("/stream", data={"url": "https://example.com/ep.mp3", "stereo": "true"})
    assert r.status_code == 200
    assert r.headers["X-Channels"] == "auto"


def test_stream_rejects_the_retired_mono_flag(client):
    """A client still sending ``mono`` gets a 400, never a silent flip."""
    r = client.post("/stream", data={"url": "https://example.com/ep.mp3", "mono": "false"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "`mono`" in detail
    assert "`stereo`" in detail


def test_record_rejects_the_retired_mono_flag(client):
    """``/record`` guards the same flag, before it validates anything else.

    The guard runs ahead of the ``output_format`` check and ahead of ffmpeg,
    so this costs no encoder and no network.
    """
    r = client.post(
        "/record",
        data={"url": "https://example.com/ep.mp3", "output_format": "mp3", "mono": "true"},
    )
    assert r.status_code == 400
    assert "`stereo`" in r.json()["detail"]


def test_record_forwards_the_resolved_channel_choice(client, monkeypatch, tmp_path):
    """``/record`` must pass ``to_mono=True`` when the flag is omitted."""
    import podcast_helper.api as api_mod

    captured = {}

    async def fake_stream(
        url, *, target_sample_rate, to_mono, realtime, frame_ms, speed, record_to
    ):
        captured["to_mono"] = to_mono
        pathlib.Path(record_to).write_bytes(b"stub")
        return
        yield  # pragma: no cover - makes this an async generator

    monkeypatch.setattr(api_mod, "extract_audio_stream", fake_stream)
    r = client.post("/record", data={"url": "https://example.com/ep.mp3"})
    assert r.status_code == 200
    assert captured["to_mono"] is True

    r = client.post("/record", data={"url": "https://example.com/ep.mp3", "stereo": "true"})
    assert r.status_code == 200
    assert captured["to_mono"] is False
