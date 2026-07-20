# podcast-helper non-CLI surfaces

`podcast-helper` exposes the same public functions through five surfaces. The
Python library and argparse CLI are always available; the others live behind
optional extras.

## 1. Python library (default)

```python
import podcast_helper as ph

# RSS / Atom helpers
ph.feed(url, max_episodes=None)          # -> list[Episode], most-recent first
ph.latest_episode(url)                   # -> Episode (first with an audio enclosure)

# Universal PCM stream — async iterator of PcmFrame
async for frame in ph.extract_audio_stream(
    url,                                 # file / direct / feed / yt-dlp URL
    target_sample_rate=16000,
    to_mono=True,
    resample_quality="default",          # or "high" (libsoxr, 28-bit)
    realtime=True,
    frame_ms=20,
    headers=None,
    cookies_from_browser=None,           # "firefox" / "chrome" / "safari" for gated sources
    speed=1.0,                           # VOD only, pitch-preserving; raises on live
    record_to=None,                      # e.g. "ep.mp3" — parallel archive while streaming
):
    frame["pcm"]      # np.float32, shape (n,) mono or (n, ch) stereo
    frame["t_abs_s"]  # seconds since source start (monotonic)
    frame["voiced"]   # None (VAD downstream fills it)
```

Typed dicts `Episode` and `PcmFrame` are exported. The public API is fixed via
`podcast_helper.__all__`; **vocal-helper depends on `extract_audio_stream` and
the `PcmFrame` shape** — treat these as stable.

## 2. CLI — argparse (default) and click

- **argparse** `podcast-helper <sub> …` — ships with the base package, zero
  extra deps. Primary surface. See `cli-reference.md`.
- **click** `podcast-helper-click <sub> …` — install `podcast-helper[cli]`. Same
  subcommands and flag names; nicer `--help`, shell completion.

## 3. HTTP API — FastAPI (`podcast-helper[api]`)

```bash
pip install 'podcast-helper[api]'
uvicorn podcast_helper.api:app --host 0.0.0.0 --port 8000
# OpenAPI docs: http://localhost:8000/docs
```

Endpoints:
- `GET  /health` — liveness probe → `{"status":"ok"}`.
- `GET  /` — redirects to `/gui`.
- `GET  /gui` — the single-page episode browser (see below).
- `GET  /feed?url=…&max_episodes=…` — JSON `{"episodes": [Episode, …]}`.
- `GET  /latest?url=…` — JSON of the latest `Episode`.
- `GET  /probe?url=…&show_url=…` — JSON `{source_kind, is_live, header_count[, direct_url]}`.
- `POST /stream` — form `url sample_rate mono frame_ms speed` → chunked f32le PCM
  (`application/octet-stream`; sample rate / channels / format in `X-*` headers).
- `POST /record` — form `url output_format sample_rate mono frame_ms speed` →
  the archive file (`FileResponse`); the temp dir is cleaned by a `BackgroundTask`.

## 4. MCP server — FastAPI-MCP (`podcast-helper[api,mcp]`)

```bash
pip install 'podcast-helper[api,mcp]'
podcast-helper-mcp                 # serves FastAPI + MCP on :8000
# or: python -m podcast_helper.mcp
```

Wraps the exact FastAPI app with `fastapi_mcp` — the same endpoints become MCP
tools (`feed`, `latest`, `probe`, `stream`, `record`) for any MCP-aware host.
Host / port via `PODCAST_HELPER_HOST` / `PODCAST_HELPER_PORT` env vars.

## 5. GUI — minimal episode browser (`GET /gui`)

Served by the FastAPI app; no build step, no framework — a single self-contained
HTML page (Tailwind via CDN + vanilla ES-module JS) defined in
`podcast_helper/gui.py`.

Workflow: paste a feed / RSS / audio / yt-dlp URL → **List episodes** (calls
`GET /feed`) → a scrollable list of episode cards (cover, title, date, duration)
→ click one to load its metadata + play the enclosure inline in an `<audio>`
element → **Record to file** (POSTs to `/record`) to download a compressed
archive. **Probe** classifies any URL via `GET /probe`.

```bash
uvicorn podcast_helper.api:app --port 8000
# open http://localhost:8000/gui  (or just http://localhost:8000/)
```

This page follows the AI Helpers suite minimal-GUI template (see
`audio_helper/gui.py`): copy the plumbing (URL box, action buttons, fetch →
list/player/download rendering), swap the domain widgets. For an ambitious
visual product on top, see the repo-root `GUI.md` design note.
