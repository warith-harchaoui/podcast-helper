---
name: podcast-helper
description: >-
  Turn any podcast / RSS / audio / video URL into a stream of PCM frames, or
  browse and archive podcast episodes, with the `podcast-helper` toolkit —
  resolve a feed / direct enclosure / yt-dlp source, list a feed's episodes,
  pick the latest, decode any audio-bearing URL to raw f32le PCM (Shannon-
  correct resampling, mono downmix or native channels), archive an episode to a
  compressed file (mp3/m4a/opus/ogg/flac/wav), and probe how a URL is
  classified. Exposed as a Python library (`import podcast_helper as ph`), two
  CLIs (`podcast-helper` argparse and `podcast-helper-click`), a FastAPI HTTP
  surface, an MCP tool set, and a minimal browser GUI at `/gui`. Local-first,
  ffmpeg + yt-dlp backed, no SaaS, no telemetry.

  TRIGGER — any of: the user names a podcast / feed / stream operation on a URL
  ("get the latest episode of this podcast", "list the episodes in this RSS
  feed", "give me a PCM stream from this podcast / YouTube / SoundCloud URL",
  "stream this episode to my ASR / VAD / transcription pipeline", "decode this
  audio URL to raw PCM / f32le / 16 kHz mono", "download / archive / record this
  episode to mp3 / m4a / opus / flac / wav", "resolve the RSS feed for this
  show", "what's the enclosure / direct audio URL of the latest episode",
  "classify / probe this URL — is it a feed, a direct file, a yt-dlp source, is
  it live"); the user pastes an RSS / Atom feed URL (`.xml .rss .atom`, feeds.*,
  anchor.fm, libsyn, buzzsprout, transistor.fm, simplecast, megaphone, acast,
  captivate, podbean) and wants its episodes or audio; the user pastes a podcast
  / audio / video URL (a YouTube / Vimeo / SoundCloud / Twitch VOD or live URL,
  or a direct `.mp3 .m4a .aac .opus .ogg .wav .flac .m3u8` enclosure) and wants
  its audio decoded, streamed, or archived; the user types or references a
  command (`podcast-helper`, `podcast-helper-click`, `podcast-helper-mcp`,
  subcommands `feed|latest|stream|record|probe`) or a library function
  (`extract_audio_stream`, `feed`, `latest_episode`, `Episode`, `PcmFrame`); the
  user wants the podcast API / MCP server run, or the episode-browser GUI; the
  user asks to install / run podcast-helper.

  SKIP when: the task is speech-to-text / transcription / captions / subtitles /
  diarization (use vocal-helper / a whisper skill); text-to-speech / voice
  cloning / synthesis; music or audio generation; file-to-file audio editing on
  a LOCAL file already in hand — convert / trim / split / concat / silence /
  room-tone / stem-separation / MFCC similarity (use audio-helper); downloading
  a VIDEO file or its frames from a URL (use youtube-helper / video-helper);
  DAW-style mixing / mastering / loudness normalization. podcast-helper's job is
  URL-in → PCM-out and RSS episode browsing / archiving; it does not transcribe,
  synthesize, or edit files already on disk.
---

# podcast-helper — universal audio-stream consumer + RSS episode toolkit

`podcast-helper` is a small, local-first Python toolkit that answers one
question well: *"give me a stream of PCM frames from this URL — never mind
whether it's a `.mp3` link, an RSS feed, a YouTube video, or a podcast on a CDN
I've never heard of."* Around that core sit friendly RSS helpers (`feed`,
`latest_episode`). The same functions are reachable five ways (library, two
CLIs, HTTP API, MCP, GUI) so an agent can pick whichever fits.

## Before anything: verify it is installed

```bash
podcast-helper --version            # argparse CLI (always installed with the pkg)
python -c "import podcast_helper"    # library import check
```

If missing, install it (ffmpeg is a hard system dependency):

```bash
pip install podcast-helper                 # core (extract_audio_stream + feed helpers)
pip install 'podcast-helper[cli]'          # + click CLI twin
pip install 'podcast-helper[api]'          # + FastAPI HTTP surface + /gui browser
pip install 'podcast-helper[api,mcp]'      # + MCP tools on top of FastAPI
```

ffmpeg must be on PATH:
- macOS 🍎 : `brew install ffmpeg` (install `brew` via [brew.sh](https://brew.sh/))
- Ubuntu 🐧 : `sudo apt install ffmpeg`
- Windows 🪟 : `winget install Gyan.FFmpeg`

## The five verbs

Same names across the library, both CLIs, the API, and the MCP tools:

| Intent | CLI | Library |
|--------|-----|---------|
| List an RSS / Atom feed's episodes | `podcast-helper feed` | `feed` |
| Get the latest episode / enclosure URL | `podcast-helper latest` | `latest_episode` |
| Decode any URL to raw PCM (stdout / WAV) | `podcast-helper stream` | `extract_audio_stream` |
| Archive any URL to a compressed file | `podcast-helper record` | `extract_audio_stream(record_to=…)` |
| Classify a URL (file/direct/rss/yt-dlp, live?) | `podcast-helper probe` | `_resolve_source` |

Quick examples:

```bash
podcast-helper feed   --url https://feeds.npr.org/510289/podcast.xml
podcast-helper latest --url https://feeds.npr.org/510289/podcast.xml --json
podcast-helper stream --url episode.mp3 --output episode.wav --sample-rate 16000
podcast-helper record --url https://feeds.npr.org/510289/podcast.xml --output ep.mp3
podcast-helper probe  --url https://youtu.be/dQw4w9WgXcQ
```

```python
import asyncio
import podcast_helper as ph

# List / pick episodes
episodes = ph.feed("https://feeds.npr.org/510289/podcast.xml", max_episodes=20)
ep = ph.latest_episode("https://feeds.npr.org/510289/podcast.xml")

# Stream PCM (URL-in → PCM-out) — pass ANY URL (feed / direct / yt-dlp)
async def main():
    async for frame in ph.extract_audio_stream(
        "https://feeds.npr.org/510289/podcast.xml",   # auto-picks latest episode
        target_sample_rate=16000, to_mono=True, frame_ms=20,
    ):
        pcm = frame["pcm"]            # np.float32 (320,) for 20 ms @ 16 kHz
        # feed pcm to your ASR / VAD here
asyncio.run(main())
```

For the full flag matrix and every option, read `references/cli-reference.md`.
For the API / MCP / GUI surfaces (endpoints, ports, the `/gui` browser), read
`references/surfaces.md`. For the exhaustive, auditable trigger list, read
`references/triggers.md`.

## Rules of thumb

- **Pick the verb from the intent, not the URL type.** "latest episode of X" →
  `latest`; "all episodes" → `feed`; "PCM for my ASR" → `stream`; "save it to
  mp3" → `record`; "what kind of URL is this" → `probe`.
- **`extract_audio_stream` takes ANY URL.** A feed URL auto-resolves to the
  latest episode's enclosure; a yt-dlp URL resolves via `bestaudio*`; a direct
  `.mp3` opens straight in ffmpeg; a local file / `file://` opens verbatim.
- **Spotify and Apple Podcasts URLs fail fast.** Spotify audio is DRM-gated;
  `podcasts.apple.com` links point to the catalog, not the audio. Both raise
  `NotImplementedError` with a hint to find the show's RSS feed. Don't retry —
  find the RSS feed instead.
- **Resampling is Shannon-correct.** `target_sample_rate` triggers an
  anti-aliasing low-pass at the new Nyquist (libswresample default, or libsoxr
  with `resample_quality="high"`). Never naive subsampling.
- **`speed != 1.0` is VOD-only** (pitch-preserving `atempo`); it raises on live
  streams. `record_to=` writes a parallel archive while the PCM flows.
- **Local only.** It fetches only the feeds / episodes you ask for and processes
  them on your machine; no telemetry, no account, no cloud upload.
