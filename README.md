# Podcast Helper

[🇫🇷](https://github.com/warith-harchaoui/podcast-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/podcast-helper/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/podcast-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/podcast-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/podcast-helper/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#the-promise)

`Podcast Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

## The Promise

**Local-first by design.** podcast-helper runs entirely on your machine — it fetches only the episodes/feeds you ask for and processes them locally; your data is never uploaded to a third-party service, no telemetry, no account, no cloud lock-in. Part of the [AI Helpers](https://github.com/warith-harchaoui/ai-helpers) suite: sovereignty over your data through local-first Open Source.

Universal audio stream consumer for podcasts and any audio-bearing URL. **URL-in → PCM-out** for local files, direct audio URLs (RSS enclosure MP3 / M4A / Opus / WAV / HLS m3u8), RSS / Atom feed URLs (auto-picks the latest episode), and every `yt-dlp`-supported source (YouTube, Vimeo, SoundCloud, Twitch VOD / live, …). Refuses Spotify-DRM and Apple Podcasts catalog URLs upfront, with clear hints toward the RSS feed workaround.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/podcast-helper/main/assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## Documentation

[💻 Documentation](https://harchaoui.org/warith/ai-helpers/docs/podcast-helper-doc/)

[📋 Examples](https://github.com/warith-harchaoui/podcast-helper/blob/main/EXAMPLES.md)

## Why it exists

Podcast pipelines (ASR, diarization, summarisation, search indexing) usually start with the same question: *"give me a stream of PCM frames from this URL, never mind whether it's a `.mp3` link, a feed, a YouTube video, or a podcast hosted on a CDN I've never heard of."* This library is that one function — and the small extras around it (`feed`, `latest_episode`) that make working with RSS sources friendly.

## Installation

**Prerequisites** — **Python 3.10–3.13** and **git**, **ffmpeg**, cross-platform:

- 🍎 **macOS** ([Homebrew](https://brew.sh)): `brew install python git ffmpeg`
- 🐧 **Ubuntu/Debian**: `sudo apt update && sudo apt install -y python3 python3-pip git ffmpeg`
- 🪟 **Windows** (PowerShell): `winget install Python.Python.3.12 Git.Git Gyan.FFmpeg`

We recommend using Python environments. Check this link if you're unfamiliar with setting one up: [🥸 Tech tips](https://harchaoui.org/warith/4ml/#install).

### From source

```bash
# Core library
pip install "git+https://github.com/warith-harchaoui/podcast-helper.git@v0.4.0"

# Optional surfaces
pip install "podcast-helper[cli] @ git+https://github.com/warith-harchaoui/podcast-helper.git@v0.4.0"
pip install "podcast-helper[api] @ git+https://github.com/warith-harchaoui/podcast-helper.git@v0.4.0"
pip install "podcast-helper[api,mcp] @ git+https://github.com/warith-harchaoui/podcast-helper.git@v0.4.0"
```

PyPI release coming soon.

This pulls in [youtube-helper](https://github.com/warith-harchaoui/youtube-helper) (and transitively `yt-dlp`, [os-helper](https://github.com/warith-harchaoui/os-helper), [audio-helper](https://github.com/warith-harchaoui/audio-helper), [video-helper](https://github.com/warith-harchaoui/video-helper)) plus [feedparser](https://feedparser.readthedocs.io/) + [podcastparser](https://podcastparser.readthedocs.io/) for RSS.

## Quick start

```python
import asyncio
import podcast_helper as ph

async def main():
    # Pass *any* URL — file, direct mp3, RSS feed, YouTube, SoundCloud, Twitch VOD.
    async for frame in ph.extract_audio_stream(
        "https://feeds.npr.org/510289/podcast.xml",   # ← RSS, auto-pick latest episode
        target_sample_rate=16000,
        to_mono=True,
        frame_ms=20,
    ):
        # frame["pcm"]: np.float32 (320,) for 20ms @ 16kHz
        # frame["t_abs_s"]: 0.0, 0.02, 0.04, ...
        await asr.feed(frame["pcm"])

asyncio.run(main())
```

For the full catalog of recipes (RSS, yt-dlp sources, live streams, stereo / multichannel, anti-aliasing, downstream ASR / VAD / summarisation pipelines), see [📋 EXAMPLES.md](https://github.com/warith-harchaoui/podcast-helper/blob/main/EXAMPLES.md).

## What URLs are accepted

| Source | Detection | What happens |
|---|---|---|
| **Local file** / `file://` | path exists on disk OR `file://` scheme | ffmpeg opens it directly. |
| **Direct audio URL** (`.mp3`, `.m4a`, `.opus`, `.wav`, `.m3u8`, …) | URL extension is a known audio container | ffmpeg opens it directly with your `headers=` if any. |
| **RSS / Atom feed** (`.xml`, `.rss`, `.atom`) | URL extension is a known feed container | `podcastparser` (fallback: `feedparser`) parses it; latest episode's enclosure is fetched. |
| **YouTube / Vimeo / SoundCloud / Twitch VOD / Twitch live / …** | yt-dlp's extractor identifies it | yt-dlp picks `bestaudio*`, hands the direct URL + headers to ffmpeg. |
| **Generic web URL** (anything else) | yt-dlp's `generic` extractor | URL used as-is. |
| **Spotify** (open.spotify.com) | hostname match | `NotImplementedError` — Spotify audio is DRM-gated. Use the show's RSS feed if it exists. |
| **Apple Podcasts** (podcasts.apple.com) | hostname match | `NotImplementedError` — Apple URLs point to the catalog, not the audio. Use the show's RSS feed (linked on the show's site, or via `getrssfeed.com` / Podcast Index). |

## Signal-processing correctness

When `target_sample_rate` differs from the source rate, the conversion is performed by ffmpeg's `libswresample` (default) or `libsoxr` (`resample_quality="high"`). Both apply an **anti-aliasing low-pass filter at the new Nyquist frequency** (`target_sample_rate / 2`) before decimation — satisfying the Shannon-Nyquist sampling theorem. Naïve subsampling is never used.

Channel handling has exactly two modes — no synthetic upmix:

| `to_mono` | Output shape | What ffmpeg does |
|---|---|---|
| `True` (default) | `(n_samples,)` | Standard downmix (stereo → L+R with -3 dB, 5.1 → ITU mix) |
| `False` | `(n_samples, n_channels)` interleaved | Preserves the source's native channel count |

## Working with RSS feeds explicitly

If you want to inspect or select episodes yourself:

```python
import podcast_helper as ph

# Full episode list, most-recent first
episodes = ph.feed("https://feeds.npr.org/510289/podcast.xml", max_episodes=20)
for ep in episodes:
    print(ep["published_at"], "—", ep["title"], "—", ep["duration_seconds"], "s")

# Or just the latest one
ep = ph.latest_episode("https://feeds.npr.org/510289/podcast.xml")
print(ep["title"], "→", ep["enclosure_url"])

# Then stream its audio
import asyncio
async def main():
    async for frame in ph.extract_audio_stream(ep["enclosure_url"]):
        ...
asyncio.run(main())
```

Each `Episode` dict has a normalised schema regardless of feed flavour:

```
{guid, title, description, link, published_at (ISO UTC),
 duration_seconds, enclosure_url, enclosure_type, enclosure_size_bytes,
 image_url}
```

## Multi-surface exposure

`podcast-helper` exposes the same public functions through five
interchangeable surfaces — pick the one that fits the caller.

| Surface | Entry point | Extra | Best for |
|---|---|---|---|
| Library (async iterator) | `import podcast_helper as ph` | — | Python code, notebooks, downstream ASR / VAD / summarisation |
| argparse CLI | `podcast-helper` | — (stdlib only) | shell scripts, CI, ffmpeg pipelines |
| click CLI | `podcast-helper-click` | `[cli]` | click-native shells (bash / zsh completion, colored help) |
| FastAPI HTTP | `uvicorn podcast_helper.api:app` | `[api]` | HTTP microservices, cross-language callers |
| MCP server | `podcast-helper-mcp` | `[api,mcp]` | Claude Desktop, MCP-aware agents, IDE integrations |
| Browser GUI | `GET /gui` (served by the API) | `[api]` | drop-a-URL episode browser: list · preview · archive, no terminal |

Install any combination of extras:

```bash
pip install 'podcast-helper[cli]'          # + click twin
pip install 'podcast-helper[api]'          # + FastAPI HTTP surface
pip install 'podcast-helper[api,mcp]'      # + MCP tools on top of FastAPI
pip install 'podcast-helper[cli,api,mcp]'  # everything
```

Every surface publishes the same verbs — `feed`, `latest`, `stream`,
`record`, `probe` — with identical argument names, so switching
between them is a copy-paste. The Dockerfile in this repo ships the
FastAPI + MCP surfaces on port 8000 out of the box (`docker build -t
podcast-helper . && docker run --rm -p 8000:8000 podcast-helper`).

### Browser GUI — the episode browser (`GET /gui`)

With the `[api]` extra, the FastAPI app serves a self-contained
single-page **episode browser** (Tailwind via CDN + vanilla JS, no
build step) that drives the very same endpoints:

```bash
pip install 'podcast-helper[api]'
uvicorn podcast_helper.api:app --port 8000
# open http://localhost:8000/gui  (or just http://localhost:8000/)
```

Paste a feed / RSS / audio / yt-dlp URL → **List episodes** (calls
`/feed`) → click an episode to see its metadata and play the enclosure
inline → **Record to file** (calls `/record`) to download a compressed
archive. **Probe** classifies any URL. Nothing is uploaded — playback
streams the enclosure straight to your browser and archiving runs
ffmpeg on your own machine.

For the exhaustive catalogue of triggers, phrasings, accepted URLs and
when *not* to reach for podcast-helper, see
[`TRIGGERS.md`](https://github.com/warith-harchaoui/podcast-helper/blob/main/TRIGGERS.md).
podcast-helper also ships as an installable Claude / OpenCode **skill**
— see [`skills/README.md`](https://github.com/warith-harchaoui/podcast-helper/blob/main/skills/README.md).

For an ambitious visual product on top, see [`GUI.md`](https://github.com/warith-harchaoui/podcast-helper/blob/main/GUI.md). For a
competitive comparison against the Python audio / podcast ecosystem,
see [`LANDSCAPE.md`](https://github.com/warith-harchaoui/podcast-helper/blob/main/LANDSCAPE.md).

## Live streams

For YouTube / Twitch live URLs, the resolved direct URL is typically an HLS `.m3u8` manifest. `extract_audio_stream` detects this (`is_live=True`) and automatically disables `-re` real-time pacing (the source paces itself). The async iterator runs indefinitely until the live stream ends; callers should `break` when they're done.

`speed != 1.0` for live streams raises `ValueError` (as of v0.2.0) — you can't fast-forward beyond the live edge. Use `speed=...` on VOD only.

## Roadmap

| Version | Feature |
|---|---|
| v0.1.0 | `extract_audio_stream` + `feed` + `latest_episode`. yt-dlp + ffmpeg + feedparser + podcastparser. |
| v0.2.0 | `record_to="ep.mp3" \| ".m4a" \| ".opus" \| ".ogg" \| ".flac" \| ".wav"` (ffmpeg multi-output: PCM to caller + compressed archive to disk in parallel). `speed: float` for VOD (raises on live), via `atempo=` filter (pitch-preserving). |
| **v0.4.0** (this release) | Browser **episode-browser GUI** at `GET /gui`; installable Claude / OpenCode **skill** (`skills/podcast-helper/`); exhaustive `TRIGGERS.md`. Additive, backward-compatible. |
| **v0.5.0** | `start_instant` / `end_instant` for VOD seek. `apple_podcasts_to_rss(url)` via iTunes Search API. Podcast Index API integration. |
| **v0.6.0+** | Chapters (ID3 CTOC/CHAP, Podcasting 2.0 `<podcast:chapters>`), transcripts, OPML import/export. |

## Author

 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

## Acknowledgements

Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.

## License

This project is licensed under the BSD-3-Clause License — see the [LICENSE](https://github.com/warith-harchaoui/podcast-helper/blob/main/LICENSE) file for details.
