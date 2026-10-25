---
name: podcast-helper
description: >-
  URL in, audio out. Resolve any podcast / RSS / direct-audio / HLS / yt-dlp
  URL and either stream it as PCM frames (same shape as capture-helper's
  iter_mic_audio, ready for a VAD or an ASR) or archive it to a compressed
  file, plus RSS helpers that list a feed's episodes and pick the latest one,
  and a probe that classifies a URL (feed / direct file / yt-dlp / live). Use
  when the user says "get the latest episode of this podcast", "list the
  episodes in this feed", "parse this RSS", "download / archive this episode
  as mp3", "stream this audio URL into my transcription pipeline", "decode
  this URL to 16 kHz mono PCM", "capture this live stream while it airs", "is
  this URL a feed or a direct file", hands over an `.rss` / `.xml` / `.m3u8` /
  audio URL, or names `podcast-helper`, `podcast-helper-mcp`, `import
  podcast_helper as ph`. Do NOT use to transcribe (vocal-helper), edit a local
  audio file (audio-helper), or fetch video and platform metadata
  (youtube-helper).
license: BSD-3-Clause
metadata:
  author: Warith Harchaoui
  package: podcast-helper
  suite: ai-helpers
  homepage: https://deraison.ai/ai-helpers
---

# podcast-helper — any audio URL into suite-shaped PCM

`podcast-helper` is **URL-in → PCM-out**. Hand it a podcast feed, a direct
enclosure, an HLS manifest, a yt-dlp-reachable page or a local file, and it
resolves the source and decodes it into a stream of PCM frames — the same
shape as capture-helper's `iter_mic_audio`, so a pipeline written for a live
microphone runs unchanged over a podcast back-catalogue. On top of that sit
two RSS conveniences (`feed`, `latest`) and a URL classifier (`probe`).

It is ffmpeg- and yt-dlp-backed, and it produces audio, never words: it does
not transcribe, synthesize, or edit files already on disk.

## Before anything: verify it is installed

```bash
podcast-helper --help                # the CLI (ships with the package)
python -c "import podcast_helper"    # library import check
ffmpeg -version                      # hard system dependency for decoding
```

Install:

```bash
pip install podcast-helper                 # core: library + CLI
pip install 'podcast-helper[api]'          # + FastAPI HTTP surface and GUI
pip install 'podcast-helper[mcp]'          # + MCP tools over the same app
```

## The five verbs

| Intent | CLI | Library |
|---|---|---|
| List a feed's episodes | `podcast-helper feed URL` | `feed` |
| The latest episode + its enclosure URL | `podcast-helper latest URL` | `latest_episode` |
| Classify a URL (feed / direct / yt-dlp / live) | `podcast-helper probe URL` | — |
| Decode any URL to PCM | `podcast-helper stream URL` | `extract_audio_stream` |
| Archive any URL to a file | `podcast-helper record URL` | `extract_audio_stream(record_to=…)` |

Quick examples:

```bash
podcast-helper feed "https://example.com/feed.xml" --json
podcast-helper latest "https://example.com/feed.xml"
podcast-helper record "https://example.com/feed.xml" -o episode.mp3
podcast-helper probe "https://youtu.be/YE7VzlLtp-4"
```

```python
import podcast_helper as ph

ep = ph.latest_episode("https://example.com/feed.xml")  # Episode
print(ep.title, ep.published, ep.duration, ep.url)

for chunk in ph.extract_audio_stream(ep.url):  # PcmFrame, like a live mic
    ...  # break to stop
```

A **feed URL** is handled end to end: pointed at an RSS feed, `stream` and
`record` resolve the latest episode's enclosure themselves.

For the full flag matrix and the accepted URL kinds, read
`references/cli-reference.md`. For the HTTP API, MCP tools and the episode
browser, read `references/surfaces.md`. For the exhaustive trigger list, read
`references/triggers.md`.

## Rules of thumb

- **Stream when consuming, record when keeping.** `extract_audio_stream` never
  materialises the file — the right call for a three-hour episode you only
  mean to transcribe.
- **`probe` first when the URL is unfamiliar.** It tells you whether you have
  a feed, a direct file, a yt-dlp source or a live stream, which decides
  everything downstream.
- **The frames match capture-helper on purpose.** Hand them to a VAD, an ASR
  or a level meter written for a live microphone without reshaping anything.
- **This overlaps youtube-helper, deliberately.** Both reach yt-dlp sources:
  use podcast-helper when you want *decoded audio frames or an archive*, and
  youtube-helper when you want platform *metadata*, stream selection,
  thumbnails, subtitles or engagement figures.
- **Spotify is DRM-gated** and raises with a hint; `podcasts.apple.com` links
  point at the catalogue, not the audio. In both cases find the show's RSS
  feed — do not try to work around the block.
- **Feeds are other people's servers.** Fetch what was asked for; do not walk
  a whole back-catalogue unless that is the task, and do not poll in a loop.
- **After running, report the episode title, its duration and the output
  path** — do not re-fetch to confirm.
