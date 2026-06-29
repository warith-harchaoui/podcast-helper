# Podcast Helper

> 🌐 Version française : [LISEZMOI.md](LISEZMOI.md)

`Podcast Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

Universal audio stream consumer for podcasts and any audio-bearing URL. **URL-in → PCM-out** for local files, direct audio URLs (RSS enclosure MP3 / M4A / Opus / WAV / HLS m3u8), RSS / Atom feed URLs (auto-picks the latest episode), and every `yt-dlp`-supported source (YouTube, Vimeo, SoundCloud, Twitch VOD / live, …). Refuses Spotify-DRM and Apple Podcasts catalog URLs upfront, with clear hints toward the RSS feed workaround.

[🕸️ AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

## Why it exists

Podcast pipelines (ASR, diarization, summarisation, search indexing) usually start with the same question: *"give me a stream of PCM frames from this URL, never mind whether it's a `.mp3` link, a feed, a YouTube video, or a podcast hosted on a CDN I've never heard of."* This library is that one function — and the small extras around it (`feed`, `latest_episode`) that make working with RSS sources friendly.

# Installation

You need `ffmpeg` on PATH:

- macOS 🍎 : `brew install ffmpeg`
- Ubuntu 🐧 : `sudo apt install ffmpeg`
- Windows 🪟 : grab a build from [ffmpeg.org/download.html](https://ffmpeg.org/download.html) and add it to `PATH`.

Then:

```bash
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/podcast-helper.git@v0.1.0
```

This pulls in [youtube-helper](https://github.com/warith-harchaoui/youtube-helper) v1.1.0 (and transitively `yt-dlp`, [os-helper](https://github.com/warith-harchaoui/os-helper), [audio-helper](https://github.com/warith-harchaoui/audio-helper), [video-helper](https://github.com/warith-harchaoui/video-helper)) plus [feedparser](https://feedparser.readthedocs.io/) + [podcastparser](https://podcastparser.readthedocs.io/) for RSS.

# Quick start

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

# What URLs are accepted

| Source | Detection | What happens |
|---|---|---|
| **Local file** / `file://` | path exists on disk OR `file://` scheme | ffmpeg opens it directly. |
| **Direct audio URL** (`.mp3`, `.m4a`, `.opus`, `.wav`, `.m3u8`, …) | URL extension is a known audio container | ffmpeg opens it directly with your `headers=` if any. |
| **RSS / Atom feed** (`.xml`, `.rss`, `.atom`) | URL extension is a known feed container | `podcastparser` (fallback: `feedparser`) parses it; latest episode's enclosure is fetched. |
| **YouTube / Vimeo / SoundCloud / Twitch VOD / Twitch live / …** | yt-dlp's extractor identifies it | yt-dlp picks `bestaudio*`, hands the direct URL + headers to ffmpeg. |
| **Generic web URL** (anything else) | yt-dlp's `generic` extractor | URL used as-is. |
| **Spotify** (open.spotify.com) | hostname match | `NotImplementedError` — Spotify audio is DRM-gated. Use the show's RSS feed if it exists. |
| **Apple Podcasts** (podcasts.apple.com) | hostname match | `NotImplementedError` — Apple URLs point to the catalog, not the audio. Use the show's RSS feed (linked on the show's site, or via `getrssfeed.com` / Podcast Index). |

# Signal-processing correctness

When `target_sample_rate` differs from the source rate, the conversion is performed by ffmpeg's `libswresample` (default) or `libsoxr` (`resample_quality="high"`). Both apply an **anti-aliasing low-pass filter at the new Nyquist frequency** (`target_sample_rate / 2`) before decimation — satisfying the Shannon-Nyquist sampling theorem. Naïve subsampling is never used.

Channel handling has exactly two modes — no synthetic upmix:

| `to_mono` | Output shape | What ffmpeg does |
|---|---|---|
| `True` (default) | `(n_samples,)` | Standard downmix (stereo → L+R with -3 dB, 5.1 → ITU mix) |
| `False` | `(n_samples, n_channels)` interleaved | Preserves the source's native channel count |

# Working with RSS feeds explicitly

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

# Live streams

For YouTube / Twitch live URLs, the resolved direct URL is typically an HLS `.m3u8` manifest. `extract_audio_stream` detects this (`is_live=True`) and automatically disables `-re` real-time pacing (the source paces itself). The async iterator runs indefinitely until the live stream ends; callers should `break` when they're done.

`speed != 1.0` for live streams will raise `ValueError` in v0.2 — you can't fast-forward beyond the live edge.

# Roadmap

| Version | Feature |
|---|---|
| **v0.1.0** (this release) | `extract_audio_stream` + `feed` + `latest_episode`. yt-dlp + ffmpeg + feedparser + podcastparser. |
| **v0.2.0** | `record_to="ep.mp3" \| ".m4a"` (tee-ffmpeg: PCM to caller + compressed archive to disk in parallel). `speed: float` for VOD (raises on live). `start_instant` / `end_instant` for VOD seek. |
| **v0.3.0** | `apple_podcasts_to_rss(url)` via iTunes Search API. Podcast Index API integration. Mic capture moves to `capture-helper`. |
| **v0.4.0+** | Chapters (ID3 CTOC/CHAP, Podcasting 2.0 `<podcast:chapters>`), transcripts, OPML import/export. |

# Author
 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

# Acknowledgements
Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.
