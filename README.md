# Podcast Helper

[🇫🇷](https://github.com/warith-harchaoui/podcast-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/podcast-helper/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/podcast-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/podcast-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/podcast-helper/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#the-promise)

`Podcast Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

## The Promise

**Local-first by design.** podcast-helper runs entirely on your machine: it fetches only the episodes and feeds you ask for and processes them locally. Your data is never uploaded to a third-party service, there is no telemetry, no account, no cloud lock-in. Part of the [AI Helpers](https://github.com/warith-harchaoui/ai-helpers) suite: sovereignty over your data through local-first open source.

Universal audio stream consumer for podcasts and any audio-bearing URL. **URL in, PCM out** (PCM, pulse-code modulation, is the raw stream of uncompressed audio samples that speech-recognition and audio-analysis models expect as input, as opposed to a compressed file like an MP3), for local files, direct audio URLs (RSS enclosure MP3, M4A, Opus, WAV, HLS m3u8), RSS/Atom feed URLs (auto-picks the latest episode), and every `yt-dlp`-supported source (YouTube, Vimeo, SoundCloud, Twitch VOD or live, and more). Spotify's DRM-gated catalog and Apple Podcasts catalog URLs are refused upfront, with a clear hint toward the RSS-feed workaround.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/podcast-helper/main/assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## Documentation

[💻 Documentation](https://harchaoui.org/warith/ai-helpers/docs/podcast-helper-doc/)

[🗺️ Landscape](https://github.com/warith-harchaoui/podcast-helper/blob/main/LANDSCAPE.md)

[📋 Examples](https://github.com/warith-harchaoui/podcast-helper/blob/main/EXAMPLES.md)

## Battle-tested

`podcast-helper` ships on [PyPI](https://pypi.org/project/podcast-helper/) under semantic-versioned tags (currently v1.1.5), so a pinned range such as `podcast-helper>=1.1.0,<2` stays stable under you. Continuous integration (CI, an automated pipeline that runs the test suite and the linter on every push) is green on `main`: `pytest` and `ruff check` both have to pass before anything merges. It depends on two siblings from the same AI Helpers suite, [youtube-helper](https://github.com/warith-harchaoui/youtube-helper) for the yt-dlp resolution step and [os-helper](https://github.com/warith-harchaoui/os-helper) for shared logging and filesystem utilities, and it is itself a dependency of [vocal-helper](https://github.com/warith-harchaoui/vocal-helper) (speaker-labelled transcription), which builds its live and offline audio ingest directly on `extract_audio_stream`.

## Why it exists

Podcast pipelines usually start with the same question, whether the downstream step is automatic speech recognition (ASR), diarization (labeling which speaker is talking when), voice activity detection (VAD, deciding which stretches of audio have speech at all before running the heavier models on them), summarization, or search indexing: *"give me a stream of PCM frames from this URL, never mind whether it's a `.mp3` link, a feed, a YouTube video, or a podcast hosted on a CDN I've never heard of."* This library is that one function, plus the small extras around it (`feed`, `latest_episode`) that make working with RSS sources friendly.

## Installation

**Prerequisites:** **Python 3.10-3.13**, **git**, and **ffmpeg**, cross-platform:

- 🍎 **macOS** ([Homebrew](https://brew.sh)): `brew install python git ffmpeg`
- 🐧 **Ubuntu/Debian**: `sudo apt update && sudo apt install -y python3 python3-pip git ffmpeg`
- 🪟 **Windows** (PowerShell): `winget install Python.Python.3.12 Git.Git Gyan.FFmpeg`

We recommend using Python environments. Check this link if you're unfamiliar with setting one up: [🥸 Tech tips](https://harchaoui.org/warith/4ml/#install).

### From PyPI (recommended)

```bash
# Core library
pip install podcast-helper

# Optional surfaces
pip install "podcast-helper[cli]"
pip install "podcast-helper[api]"
pip install "podcast-helper[mcp]"
```

This pulls in [youtube-helper](https://github.com/warith-harchaoui/youtube-helper) (and transitively `yt-dlp`, [os-helper](https://github.com/warith-harchaoui/os-helper), [audio-helper](https://github.com/warith-harchaoui/audio-helper), [video-helper](https://github.com/warith-harchaoui/video-helper)), plus [feedparser](https://feedparser.readthedocs.io/) and [podcastparser](https://podcastparser.readthedocs.io/) for RSS.

### From source (no PyPI)

```bash
git clone https://github.com/warith-harchaoui/podcast-helper.git
cd podcast-helper
pip install -e .

# Optional surfaces
pip install -e ".[cli]"
pip install -e ".[api]"
pip install -e ".[mcp]"
```

## Quick start

```python
import asyncio
import podcast_helper as ph

async def main():
    # Pass *any* URL: file, direct mp3, RSS feed, YouTube, SoundCloud, Twitch VOD.
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

For the full catalog of recipes (RSS, yt-dlp sources, live streams, stereo / multichannel, anti-aliasing, downstream ASR / VAD / summarization pipelines), see [📋 EXAMPLES.md](https://github.com/warith-harchaoui/podcast-helper/blob/main/EXAMPLES.md).

## What URLs are accepted

| Source | Detection | What happens |
|---|---|---|
| **Local file** / `file://` | path exists on disk OR `file://` scheme | ffmpeg opens it directly. |
| **Direct audio URL** (`.mp3`, `.m4a`, `.opus`, `.wav`, `.m3u8`, …) | URL extension is a known audio container | ffmpeg opens it directly with your `headers=` if any. |
| **RSS / Atom feed** (`.xml`, `.rss`, `.atom`) | URL extension is a known feed container | `podcastparser` (fallback: `feedparser`) parses it; latest episode's enclosure is fetched. |
| **YouTube / Vimeo / SoundCloud / Twitch VOD / Twitch live / …** | yt-dlp's extractor identifies it | yt-dlp picks `bestaudio*`, hands the direct URL + headers to ffmpeg. |
| **Generic web URL** (anything else) | yt-dlp's `generic` extractor | URL used as-is. |
| **Spotify** (open.spotify.com) | hostname match | `NotImplementedError`: Spotify audio is DRM-gated. Use the show's RSS feed if it exists. |
| **Apple Podcasts** (podcasts.apple.com) | hostname match | `NotImplementedError`: Apple URLs point to the catalog, not the audio. Use the show's RSS feed (linked on the show's site, or via `getrssfeed.com` / Podcast Index). |

## Signal-processing correctness

When `target_sample_rate` differs from the source rate, the conversion is performed by ffmpeg's `libswresample` (default) or `libsoxr` (`resample_quality="high"`). Both apply an **anti-aliasing low-pass filter at the new Nyquist frequency** (`target_sample_rate / 2`, the sampling theorem's ceiling on the highest frequency a given rate can represent) before decimation: any content above that ceiling gets removed first, because if it were kept it would fold back down into the audible range as spurious noise once the rate drops, an artifact called aliasing. Naïve subsampling, dropping samples without this filter, skips that step and lets the aliasing through; it is never used here.

Channel handling has exactly two modes; there is no synthetic upmix:

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
    print(ep["published_at"], "|", ep["title"], "|", ep["duration_seconds"], "s")

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

Each `Episode` dict has a normalized schema regardless of feed flavor:

```
{guid, title, description, link, published_at (ISO UTC),
 duration_seconds, enclosure_url, enclosure_type, enclosure_size_bytes,
 image_url}
```

## Multi-surface exposure

`podcast-helper` exposes the same public functions through five
interchangeable surfaces; pick the one that fits the caller.

| Surface | Entry point | Extra | Best for |
|---|---|---|---|
| Library (async iterator) | `import podcast_helper as ph` | none | Python code, notebooks, downstream ASR / VAD / summarization |
| argparse CLI | `podcast-helper` | none (stdlib only) | shell scripts, CI, ffmpeg pipelines |
| click CLI | `podcast-helper-click` | `[cli]` | click-native shells (bash / zsh completion, colored help) |
| FastAPI HTTP | `uvicorn podcast_helper.api:app` | `[api]` | HTTP microservices, cross-language callers |
| Browser GUI | `GET /gui` (served by the API) | `[api]` | drop-a-URL episode browser: list · preview · archive, no terminal |
| MCP | `podcast-helper-mcp` | `[mcp]` | any MCP-aware agent host (calls the same endpoints as tools) |

Install any combination of extras:

```bash
pip install 'podcast-helper[cli]'          # + click twin
pip install 'podcast-helper[api]'          # + FastAPI HTTP surface
pip install 'podcast-helper[mcp]'          # + MCP tools (needs [api] too, pulled in automatically)
pip install 'podcast-helper[cli,api,mcp]'  # everything
```

Every surface publishes the same verbs, `feed`, `latest`, `stream`,
`record`, `probe`, with identical argument names, so switching
between them is a copy-paste. The Dockerfile in this repo ships the
FastAPI surface on port 8000 out of the box (`docker build -t
podcast-helper . && docker run --rm -p 8000:8000 podcast-helper`).

### Browser GUI: the episode browser (`GET /gui`)

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
archive. **Probe** classifies any URL. Nothing is uploaded: playback
streams the enclosure straight to your browser, and archiving runs
ffmpeg on your own machine.

For the exhaustive catalog of triggers, phrasings, accepted URLs and
when *not* to reach for podcast-helper, see
[`TRIGGERS.md`](https://github.com/warith-harchaoui/podcast-helper/blob/main/TRIGGERS.md).

For an ambitious visual product on top, see [`GUI.md`](https://github.com/warith-harchaoui/podcast-helper/blob/main/GUI.md).

## Live streams

For YouTube / Twitch live URLs, the resolved direct URL is typically an HLS (HTTP Live Streaming, a protocol that serves audio or video as a sequence of small segment files listed in a `.m3u8` playlist) manifest. `extract_audio_stream` detects this (`is_live=True`) and automatically disables `-re` real-time pacing (the source paces itself). The async iterator runs indefinitely until the live stream ends; callers should `break` when they're done.

`speed != 1.0` for live streams raises `ValueError`: you can't fast-forward beyond the live edge. Use `speed=...` on VOD only.

## Not built yet

- `start_instant` / `end_instant` for VOD seek.
- `apple_podcasts_to_rss(url)`, resolving an Apple Podcasts catalog URL to its RSS feed via the iTunes Search API.
- Podcast Index API integration.
- Chapters (ID3 CTOC/CHAP, Podcasting 2.0 `<podcast:chapters>`) and transcripts.
- OPML import/export.

See [CHANGELOG.md](https://github.com/warith-harchaoui/podcast-helper/blob/main/CHANGELOG.md) for what has already shipped.

## Rust rewrite

A companion crate, [`podcast-helper-rs`](https://github.com/warith-harchaoui/podcast-helper-rs),
rewrites the same "URL in, PCM out" promise in Rust: local files, direct
audio URLs, and RSS/Atom feeds decoded via `ffmpeg`, with
YouTube/Vimeo/SoundCloud/Twitch delegated to `youtube-helper-rs`. The
interest: a single static binary with no Python interpreter to install,
useful when podcast ingestion needs to run as part of a larger Rust
pipeline (for example, feeding a Rust speech-recognition or diarization
service) rather than a Python one. It's a smaller v0.1 surface, not a full
replacement — no async frame iterator yet, no `itunes:duration` parsing;
see its README for the exact deliberate differences.

## Author

 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

## Acknowledgements

Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.

## License

This project is licensed under the BSD-3-Clause License. See the [LICENSE](https://github.com/warith-harchaoui/podcast-helper/blob/main/LICENSE) file for details.
