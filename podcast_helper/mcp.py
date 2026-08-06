"""Podcast Helper: Model Context Protocol (MCP) surface.

A thin adapter that exposes the FastAPI app from :mod:`podcast_helper.api` as
MCP tools, so any MCP-aware host (an agent runtime, an IDE integration, a
custom shell) can call podcast-helper's universal audio-stream-consumer
operations (feed introspection, URL classification, PCM streaming, server-side
archiving) as first-class tools — local files, direct audio URLs, RSS feed
enclosures, and any yt-dlp-supported source, all with URL-in -> PCM-out
semantics. Uses `fastapi-mcp` (https://github.com/tadata-org/fastapi_mcp): one
wrapper publishes the whole existing HTTP surface, so the routes are never
duplicated.

Install the extra to pull in ``fastapi-mcp``::

    pip install "podcast-helper[mcp]"

Then run the server (HTTP API + MCP endpoint at ``/mcp``)::

    podcast-helper-mcp                 # console entry point
    python -m podcast_helper.mcp       # equivalent

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

try:
    from fastapi_mcp import FastApiMCP
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        'The MCP surface needs the [mcp] extra: pip install "podcast-helper[mcp]"'
    ) from exc

# Reuse the exact same FastAPI app: MCP is a thin wrapper on top, no new routes.
from podcast_helper.api import app

# Publish the HTTP endpoints (feed / latest / probe / stream / record) as MCP tools.
mcp = FastApiMCP(
    app,
    name="podcast-helper",
    description=(
        "podcast-helper MCP tools: a universal audio stream consumer. "
        "Introspect RSS/Atom feeds (feed, latest), classify any URL "
        "(probe: file / direct / rss / yt-dlp-<extractor>), stream raw f32le "
        "PCM from any audio-bearing source, or archive one to a compressed "
        "file server-side (record) — local files, direct audio URLs, RSS "
        "enclosures, and any yt-dlp-supported source (YouTube, Vimeo, Twitch, "
        "SoundCloud, ...), entirely on the local machine."
    ),
)
# Newer fastapi-mcp splits mount() into transport-specific mount_http(); fall back to
# the legacy mount() so a range of fastapi-mcp versions keeps working.
if hasattr(mcp, "mount_http"):
    mcp.mount_http()
else:  # pragma: no cover - legacy fastapi-mcp
    mcp.mount()


def main() -> None:
    """Console entry point (``podcast-helper-mcp``): serve the API + MCP endpoint.

    Boots the FastAPI app (now serving both the plain HTTP routes and the
    ``/mcp`` MCP endpoint) with uvicorn in a single worker. Local-first: binds
    to loopback by default (override with ``PODCAST_HELPER_HOST`` /
    ``PODCAST_HELPER_PORT``).
    """
    import os

    import uvicorn

    host = os.environ.get("PODCAST_HELPER_HOST", "127.0.0.1")
    port = int(os.environ.get("PODCAST_HELPER_PORT", "8000"))
    print(f"Podcast Helper API + MCP -> http://{host}:{port}  (MCP at /mcp)")
    uvicorn.run(app, host=host, port=port, workers=1)


if __name__ == "__main__":  # pragma: no cover
    main()
