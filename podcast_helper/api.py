"""
Podcast Helper — FastAPI HTTP surface.

Exposes every public function in :mod:`podcast_helper` as an HTTP
endpoint so ``podcast-helper`` can be dropped behind any reverse proxy
and consumed by other services. Kept intentionally minimal:

- ``/feed`` and ``/latest``: JSON responses over an RSS / Atom URL.
- ``/probe``: JSON classification of any URL (file / direct / rss /
  yt-dlp-<extractor>) — invaluable for operators debugging podcast
  ingest.
- ``/stream``: chunked ``StreamingResponse`` of raw f32le PCM bytes
  for any audio-bearing URL. Downstream ASR services can pipe the
  response directly.
- ``/record``: server-side archive to a compressed file, returned via
  ``FileResponse``; the temp file is cleaned up by a ``BackgroundTask``
  once the response has been fully streamed to the client.

Install the extra to get the runtime dependencies::

    pip install 'podcast-helper[api]'

Then run the app with any ASGI server::

    uvicorn podcast_helper.api:app --host 0.0.0.0 --port 8000

Usage Example
-------------
>>> # Start the server:
>>> #   uvicorn podcast_helper.api:app --reload
>>> # List a feed's episodes:
>>> #   curl 'http://localhost:8000/feed?url=https://feeds.npr.org/510289/podcast.xml'
>>> # Get the latest episode:
>>> #   curl 'http://localhost:8000/latest?url=https://feeds.npr.org/510289/podcast.xml'
>>> # Archive a URL to disk (server-side ffmpeg):
>>> #   curl -o ep.mp3 -X POST -F 'url=…' -F 'output_format=mp3' \\
>>> #        http://localhost:8000/record
>>> # Full OpenAPI docs at http://localhost:8000/docs

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import AsyncIterator, Optional

try:
    from fastapi import BackgroundTasks, FastAPI, Form, HTTPException, Query
    from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The FastAPI HTTP surface requires the [api] extra. "
        "Install with: pip install 'podcast-helper[api]'"
    ) from exc

from . import extract_audio_stream, feed, latest_episode


# ---------------------------------------------------------------------------
# App factory + shared plumbing
# ---------------------------------------------------------------------------


app = FastAPI(
    title="Podcast Helper API",
    description=(
        "HTTP surface for podcast-helper: RSS / Atom feed introspection, "
        "URL classification, and streaming PCM / archive output for any "
        "audio-bearing URL (files, direct enclosures, RSS feeds, yt-dlp sources)."
    ),
    version="0.3.3",
    docs_url="/docs",
    redoc_url="/redoc",
)


def _cleanup(*paths: Path | str) -> None:
    """Best-effort cleanup — never let a tidy-up failure kill a response."""
    for p in paths:
        try:
            path = Path(p)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink(missing_ok=True)
        except Exception:
            pass


def _new_tmpdir() -> Path:
    """Create a request-scoped temp directory under the system temp root."""
    return Path(tempfile.mkdtemp(prefix="podcast-helper-"))


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Simple liveness probe — no dependency check, just proves the app is up."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Reads (feed / latest / probe) — cheap, JSON
# ---------------------------------------------------------------------------


@app.get("/feed", tags=["reads"])
def get_feed(
    url: str = Query(..., description="RSS / Atom feed URL."),
    max_episodes: Optional[int] = Query(None, description="Cap number of episodes returned."),
) -> JSONResponse:
    """Return the feed's episodes as JSON (most-recent first)."""
    try:
        episodes = feed(url, max_episodes=max_episodes)
    except Exception as exc:
        # Surface upstream errors (bad URL, unparseable feed) as 400/502
        # depending on cause. Broad catch keeps a single failure path.
        raise HTTPException(status_code=502, detail=f"feed error: {exc}") from exc
    return JSONResponse({"episodes": episodes})


@app.get("/latest", tags=["reads"])
def get_latest(url: str = Query(..., description="RSS / Atom feed URL.")) -> JSONResponse:
    """Return the latest episode (with a non-empty audio enclosure) as JSON."""
    try:
        ep = latest_episode(url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"latest_episode error: {exc}") from exc
    return JSONResponse(ep)


@app.get("/probe", tags=["reads"])
def probe(
    url: str = Query(..., description="URL to classify."),
    show_url: bool = Query(False, description="Include the resolved direct URL in the response."),
) -> JSONResponse:
    """Report how podcast-helper classified a URL (source_kind, is_live, headers)."""
    from .streaming import _resolve_source

    try:
        resolved = _resolve_source(url, user_headers=None, cookies_from_browser=None)
    except NotImplementedError as exc:
        # Spotify / Apple Podcasts guards — return the hint verbatim.
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"probe error: {exc}") from exc

    payload = {
        "source_kind": resolved["source_kind"],
        "is_live": resolved["is_live"],
        "header_count": len(resolved["headers"]),
    }
    if show_url:
        payload["direct_url"] = resolved["direct_url"]
    return JSONResponse(payload)


# ---------------------------------------------------------------------------
# Streams — heavy, binary
# ---------------------------------------------------------------------------


async def _pcm_iterator(
    url: str, sample_rate: int, mono: bool, frame_ms: int, speed: float,
) -> AsyncIterator[bytes]:
    # Bridge our async iterator of PcmFrame dicts to the byte-stream
    # protocol FastAPI expects for a StreamingResponse. Each yielded
    # chunk is the raw f32le bytes of one frame.
    async for frame in extract_audio_stream(
        url,
        target_sample_rate=sample_rate,
        to_mono=mono,
        realtime=False,  # streaming to HTTP is server-paced, no -re needed
        frame_ms=frame_ms,
        speed=speed,
    ):
        yield frame["pcm"].tobytes()


@app.post("/stream", tags=["actions"])
def stream(
    url: str = Form(..., description="Audio-bearing URL."),
    sample_rate: int = Form(16000),
    mono: bool = Form(True),
    frame_ms: int = Form(20),
    speed: float = Form(1.0),
) -> StreamingResponse:
    """
    Stream raw f32le PCM for any audio-bearing URL.

    Clients: pipe the response body into ffplay / a VAD / an ASR
    frontend. The Content-Type is ``application/octet-stream``; sample
    rate / channels / format are conveyed via headers below.
    """
    headers = {
        "X-Sample-Rate": str(sample_rate),
        "X-Channels": "1" if mono else "auto",
        "X-Format": "f32le",
    }
    return StreamingResponse(
        _pcm_iterator(url, sample_rate, mono, frame_ms, speed),
        media_type="application/octet-stream",
        headers=headers,
    )


@app.post("/record", tags=["actions"])
async def record(
    background: BackgroundTasks,
    url: str = Form(..., description="Audio-bearing URL."),
    output_format: str = Form("mp3", description="Archive container (mp3/m4a/opus/ogg/flac/wav)."),
    sample_rate: int = Form(16000),
    mono: bool = Form(True),
    frame_ms: int = Form(20),
    speed: float = Form(1.0),
) -> FileResponse:
    """
    Archive any audio-bearing URL to a compressed file server-side, then
    return the file as the response body.
    """
    tmp = _new_tmpdir()
    dst = tmp / f"episode.{output_format.lstrip('.')}"
    # Sink the PCM frames while ffmpeg writes the parallel archive on disk.
    try:
        async for _ in extract_audio_stream(
            url,
            target_sample_rate=sample_rate,
            to_mono=mono,
            realtime=False,
            frame_ms=frame_ms,
            speed=speed,
            record_to=str(dst),
        ):
            pass
    except Exception as exc:
        _cleanup(tmp)
        raise HTTPException(status_code=502, detail=f"record error: {exc}") from exc

    background.add_task(_cleanup, tmp)
    return FileResponse(str(dst), filename=dst.name, media_type="application/octet-stream")
