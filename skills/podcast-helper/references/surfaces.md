# podcast-helper non-CLI surfaces

## 1. Library

```python
import podcast_helper as ph
```

Public API (`podcast_helper.__all__`): `extract_audio_stream`, `PcmFrame`,
`feed`, `latest_episode`, `Episode`.

A deliberately small surface. `Episode` carries the feed's own metadata
(title, publication date, duration, enclosure URL). `extract_audio_stream`
yields `PcmFrame`s — decoded samples plus their timing — and takes
`record_to=` when you want the bytes kept as well as consumed.

```python
async for frame in ph.extract_audio_stream(url, target_sample_rate=16000, to_mono=True):
    pcm = frame["pcm"]  # float32, (320,) per 20 ms at 16 kHz, as capture_helper.iter_mic_audio
```

It is an **async** generator, **infinite on a live source**; the caller breaks
out, and breaking never raises. A source that fails (unreachable, undecodable,
a fired read timeout) raises `RuntimeError` after the frames it did deliver,
so a truncated stream is never mistaken for a complete one.

Logging and file management route through `os_helper` — the suite convention.

## 2. CLI — `podcast-helper` (core)

One command line, no extra to install. See `cli-reference.md`.

## 3. HTTP API — FastAPI (`[api]`)

```bash
pip install 'podcast-helper[api]'
uvicorn podcast_helper.api:app --port 8000   # OpenAPI docs at /docs
```

| Method | Route | Purpose |
|---|---|---|
| GET | `/health`, `/`, `/gui` | liveness and the episode browser |
| GET | `/feed` | episodes of a feed |
| GET | `/latest` | the newest episode |
| GET | `/probe` | classify a URL |
| POST | `/stream` | decode to raw `f32le` PCM |
| POST | `/record` | archive to a file (`output_format`: mp3/m4a/aac/opus/ogg/flac/wav), returned as the body |

## 4. MCP — `fastapi-mcp` over the *same* app (`[mcp]`)

```bash
pip install 'podcast-helper[mcp]'
podcast-helper-mcp                  # same app, MCP mounted at /mcp
```

`podcast_helper.mcp` takes the FastAPI app from `podcast_helper.api` and
mounts `FastApiMCP` on it. Every MCP tool *is* an HTTP route, so the two
surfaces cannot drift and one process serves both doors. The tools carry
FastAPI's operation ids: `get_feed_feed_get`, `get_latest_latest_get`,
`probe_probe_get`, `stream_stream_post`, `record_record_post`, plus
`health_health_get` and `gui_gui_get`. The server binds `127.0.0.1:8000`;
`--host` / `--port`, or `PODCAST_HELPER_HOST` and `PODCAST_HELPER_PORT` when
the flags are absent, override both. `podcast-helper-mcp --help` prints the
options and exits.

Register it with Claude Code:

```bash
claude mcp add podcast-helper --transport http http://127.0.0.1:8000/mcp
```

## 5. Episode browser GUI (`[api]`)

`GET /gui` — paste a feed URL, see the episodes, play or download one. The
surface to hand a human who wants to browse before fetching.

## Where this sits in the suite

```
podcast-helper  ──►  vocal-helper   (transcribe, diarize the PCM)
      │         ──►  audio-helper   (resample, split, stems on the archive)
capture-helper  ──►  the same PcmFrame shape, from a live microphone
```

podcast-helper and youtube-helper overlap on yt-dlp sources, on purpose:
reach for **podcast-helper** when you want decoded audio frames or an archive,
and **youtube-helper** when you want platform metadata, stream selection,
thumbnails, subtitles or engagement figures.
