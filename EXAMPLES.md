# Podcast Helper Examples

Practical recipes for streaming podcast audio into PCM frames. All
snippets assume:

```python
import asyncio
import podcast_helper as ph
```

and that `ffmpeg` is on PATH (`brew install ffmpeg` on macOS;
`sudo apt install ffmpeg` on Linux).

---

## Table of Contents

1. [Setup](#setup)
2. [URL → PCM in one call](#url--pcm-in-one-call)
3. [RSS feeds: latest episode, list, by index](#rss-feeds-latest-episode-list-by-index)
4. [YouTube / Vimeo / SoundCloud audio](#youtube--vimeo--soundcloud-audio)
5. [Live streams](#live-streams)
6. [Stereo / multichannel sources](#stereo--multichannel-sources)
7. [Anti-aliasing — high precision resampler](#anti-aliasing--high-precision-resampler)
8. [Common downstream pipelines](#common-downstream-pipelines)

---

## Setup

```bash
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/podcast-helper.git@v0.1.3
```

Pulls in `youtube-helper` (and transitively `yt-dlp`, `audio-helper`,
`video-helper`, `os-helper`) plus `feedparser` + `podcastparser`.

## URL → PCM in one call

`extract_audio_stream(url, ...)` is the only function you usually need:
it figures out what kind of URL you passed (local file / direct audio /
RSS feed / yt-dlp source) and yields PCM frames.

```python
async def main():
    async for frame in ph.extract_audio_stream(
        "https://feeds.npr.org/510289/podcast.xml",
        target_sample_rate=16000,
        to_mono=True,
        frame_ms=20,
    ):
        # frame["pcm"]:    np.float32, shape (320,) for 20ms @ 16kHz
        # frame["t_abs_s"]: 0.00, 0.02, 0.04, ...
        await asr.feed(frame["pcm"])

asyncio.run(main())
```

Same code works with:

```python
# Local file
ph.extract_audio_stream("/Users/me/podcasts/episode.mp3")

# Direct RSS enclosure
ph.extract_audio_stream("https://cdn.simplecast.com/audio/.../episode.mp3")

# YouTube video — yt-dlp resolves bestaudio
ph.extract_audio_stream("https://www.youtube.com/watch?v=YE7VzlLtp-4")

# SoundCloud
ph.extract_audio_stream("https://soundcloud.com/user/track-id")
```

## RSS feeds: latest episode, list, by index

```python
# Just give me the freshest episode
ep = ph.latest_episode("https://feeds.npr.org/510289/podcast.xml")
print(ep["title"], "→", ep["enclosure_url"])

# Browse the catalog (newest first)
episodes = ph.feed("https://feeds.npr.org/510289/podcast.xml", max_episodes=20)
for ep in episodes:
    print(ep["published_at"], "—", ep["title"], f"({ep['duration_seconds']}s)")

# Pick by index (e.g. yesterday's episode = second-newest)
ep = ph.feed("https://feeds.npr.org/510289/podcast.xml", max_episodes=2)[1]

# Then stream its audio
async def stream_one():
    async for frame in ph.extract_audio_stream(ep["enclosure_url"]):
        ...
asyncio.run(stream_one())
```

Each `Episode` is a typed dict:

| Field | Type | Notes |
|---|---|---|
| `guid` | str | Stable episode identifier (empty if feed didn't ship one). |
| `title` | str | |
| `description` | str | May contain HTML / show-note markup. |
| `link` | str | Episode webpage (NOT the audio URL). |
| `published_at` | str | ISO 8601 UTC `YYYY-MM-DDTHH:MM:SS+00:00` (empty when absent). |
| `duration_seconds` | int | 0 when missing. |
| `enclosure_url` | str | The actual audio URL — feed this to `extract_audio_stream`. |
| `enclosure_type` | str | MIME (`"audio/mpeg"`, `"audio/x-m4a"`, …). |
| `enclosure_size_bytes` | int | 0 when missing. |
| `image_url` | str | Episode art, falls back to show art. |

## YouTube / Vimeo / SoundCloud audio

Any URL `yt-dlp` can extract works directly. For age-gated or
members-only content, pass `cookies_from_browser`:

```python
async def youtube_premium():
    async for frame in ph.extract_audio_stream(
        "https://www.youtube.com/watch?v=...",
        cookies_from_browser="firefox",   # or "chrome" / "safari"
        target_sample_rate=16000,
    ):
        ...
```

## Live streams

For YouTube / Twitch live URLs, `extract_audio_stream` detects the live
flag and disables `-re` real-time pacing (the source paces itself). The
async iterator runs until the live stream ends or the client breaks.

```python
async def transcribe_live(url):
    async for frame in ph.extract_audio_stream(url, target_sample_rate=16000):
        if vad.is_speech(frame["pcm"]):
            transcript = asr.feed(frame["pcm"])
            if "stop" in transcript:
                break
```

In a future release, `speed != 1.0` on live streams will raise
`ValueError` — you can't fast-forward past the live edge.

## Stereo / multichannel sources

By default `to_mono=True` downmixes to a single channel (ffmpeg's
standard mixing matrix). To keep the source's native channel count,
pass `to_mono=False`. The frame's `pcm` array then has shape
`(n_samples, n_channels)` interleaved per sample:

```python
async def keep_stereo():
    async for frame in ph.extract_audio_stream(
        "https://cdn.example.com/album.flac",
        to_mono=False,
        target_sample_rate=44100,
    ):
        # frame["pcm"]: np.float32, shape (882, 2) for 20ms @ 44.1kHz stereo
        left, right = frame["pcm"][:, 0], frame["pcm"][:, 1]
        ...
```

There is no `channels=N` knob — downmix-to-mono is canonical and
deterministic; arbitrary upmix is a creative choice that belongs in
your downstream stack.

## Anti-aliasing — high precision resampler

When `target_sample_rate` differs from the source rate, the conversion
goes through ffmpeg's `libswresample` by default — a polyphase resampler
with anti-aliasing low-pass at the new Nyquist (`target_sample_rate / 2`).
That's Shannon-correct and more than enough for ASR / VAD / ML.

For audiophile / lossless work, opt into `libsoxr` 28-bit precision
(~10× slower, inaudible artefacts):

```python
ph.extract_audio_stream(
    url,
    target_sample_rate=44100,
    resample_quality="high",   # uses aresample=...:resampler=soxr:precision=28
)
```

## Common downstream pipelines

### ASR (Silero, Whisper-streaming, etc.)

```python
async def transcribe(url):
    chunks = []
    async for frame in ph.extract_audio_stream(url, target_sample_rate=16000, frame_ms=20):
        chunks.append(frame["pcm"])
        if len(chunks) * 0.02 >= 5.0:           # every 5 seconds
            audio = np.concatenate(chunks)
            print(whisper.transcribe(audio))
            chunks.clear()
```

### VAD-gated ingest

```python
import torch
vad = torch.jit.load("silero_vad.jit")

async def vad_ingest(url):
    async for frame in ph.extract_audio_stream(url, target_sample_rate=16000, frame_ms=20):
        if vad(torch.from_numpy(frame["pcm"])) > 0.5:
            await queue.put(frame)
```

### Streaming summarisation (LLM-friendly chunks)

```python
async def summarise_window(url, window_s=60.0):
    chunks, total = [], 0.0
    async for frame in ph.extract_audio_stream(url, target_sample_rate=16000):
        chunks.append(frame["pcm"])
        total += 0.02
        if total >= window_s:
            audio = np.concatenate(chunks)
            transcript = whisper.transcribe(audio)
            summary = llm.summarise(transcript)
            yield summary
            chunks, total = [], 0.0
```
