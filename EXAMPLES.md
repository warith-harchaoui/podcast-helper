# Podcast Helper Examples

[🇫🇷 EXEMPLES.md](https://github.com/warith-harchaoui/podcast-helper/blob/main/EXEMPLES.md) · 🇬🇧 English

Runnable recipes for turning any audio-bearing URL into PCM (pulse-code
modulation: the raw, uncompressed audio samples that speech and audio
models consume).

Snippets that only need `ffmpeg` and a local file were **executed**, and
their output is pasted verbatim below. Snippets that need the network —
a live RSS feed, a YouTube URL — are marked as such and carry no pasted
output, because inventing one would be the easiest way to make this file
lie.

## Table of Contents

1. [Setup](#setup)
2. [One URL in, PCM frames out](#1-one-url-in-pcm-frames-out)
3. [RSS feeds and the Episode dict](#2-rss-feeds-and-the-episode-dict)
4. [YouTube, SoundCloud and other yt-dlp sources](#3-youtube-soundcloud-and-other-yt-dlp-sources)
5. [Live streams](#4-live-streams)
6. [Stereo and multichannel](#5-stereo-and-multichannel)
7. [The high-precision resampler](#6-the-high-precision-resampler)
8. [A compressed archive while you stream](#7-a-compressed-archive-while-you-stream)
9. [Feeding a model downstream](#8-feeding-a-model-downstream)
10. [The suite working together](#9-the-suite-working-together)
11. [Command line](#command-line)
12. [Troubleshooting](#troubleshooting)

## Setup

```bash
pip install podcast-helper
```

That one line brings the library and the `podcast-helper` command. The
HTTP and MCP surfaces live behind extras (`[api]`, `[mcp]`); the sections
below say when you need them.

`ffmpeg` must be on `PATH` — it is the decoder, not an optional accelerator:

```bash
brew install ffmpeg                 # macOS
sudo apt install -y ffmpeg          # Debian / Ubuntu
```

Every later snippet assumes these imports:

```python
import asyncio
import logging

import numpy as np
import os_helper as osh
import podcast_helper as ph
```

The executed examples all read the same one-second 440 Hz stereo tone, so
you can reproduce them without a network:

```bash
ffmpeg -f lavfi -i "sine=frequency=440:duration=1:sample_rate=44100" -ac 2 tone.wav
```

## 1. One URL in, PCM frames out

`extract_audio_stream` is the only function most callers need. It
classifies the URL you hand it (local file, direct audio, RSS feed,
yt-dlp source) and yields `PcmFrame` dicts: `t_abs_s` (seconds since the
source started), `pcm` (float32 samples) and `voiced` (always `None`
here — a downstream VAD fills it in).

```python
async def main():
    count = 0
    async for frame in ph.extract_audio_stream(
        "tone.wav",
        target_sample_rate=16000,
        to_mono=True,
        frame_ms=20,
        realtime=False,  # decode as fast as the machine allows
    ):
        if count < 3:
            rms = float(np.sqrt(np.mean(frame["pcm"] ** 2)))
            print(
                f"t={frame['t_abs_s']:.2f}s shape={frame['pcm'].shape} "
                f"dtype={frame['pcm'].dtype} rms={rms:.3f}"
            )
        count += 1
    print("frames:", count)


asyncio.run(main())
```

```text
t=0.00s shape=(320,) dtype=float32 rms=0.088
t=0.02s shape=(320,) dtype=float32 rms=0.088
t=0.04s shape=(320,) dtype=float32 rms=0.089
frames: 50
```

Fifty frames of 320 samples: 20 ms at 16 kHz, one second of audio. The
same call takes any other kind of URL without a flag:

```python
ph.extract_audio_stream("/Users/me/podcasts/episode.mp3")  # local file
ph.extract_audio_stream("https://cdn.example.com/ep/042.mp3")  # direct enclosure
ph.extract_audio_stream("https://feeds.example.org/show.xml")  # RSS, latest episode
ph.extract_audio_stream("https://www.youtube.com/watch?v=YE7VzlLtp-4")  # yt-dlp source
```

`realtime` defaults to `True`, which paces the decode at wall-clock
speed (ffmpeg's `-re`). Pass `realtime=False` for batch work, and read
[Troubleshooting](#troubleshooting) before you `break` out of a
`realtime=False` loop.

## 2. RSS feeds and the Episode dict

When you want to choose the episode yourself rather than letting
`extract_audio_stream` take the newest one, `feed` and `latest_episode`
expose the feed directly. Both fetch over HTTP, so this snippet **needs
the network** and no output is pasted:

```python
FEED = "https://feeds.npr.org/510289/podcast.xml"

episodes = ph.feed(FEED, max_episodes=20)  # newest first
for episode in episodes:
    print(episode["published_at"], "|", episode["title"], "|", episode["duration_seconds"], "s")

newest = ph.latest_episode(FEED)  # skips enclosure-less items
print(newest["title"], "->", newest["enclosure_url"])

yesterday = ph.feed(FEED, max_episodes=2)[1]  # pick by index


async def stream_one():
    async for frame in ph.extract_audio_stream(yesterday["enclosure_url"]):
        print(frame["t_abs_s"], frame["pcm"].shape)
        break


asyncio.run(stream_one())
```

`feed` sorts newest-first on `published_at` and sinks undated items to
the bottom; `max_episodes` caps the count (a negative cap raises
`ValueError` rather than slicing from the far end). `latest_episode`
returns the newest item that actually carries an audio enclosure, which
is why it is not simply `feed(url)[0]`: trailers and text-only items get
skipped.

Every episode is an `Episode` typed dict with the same keys whatever the
feed flavour:

| Key | Type | Notes |
|---|---|---|
| `guid` | str | Stable episode identifier; empty when the feed ships none. |
| `title` | str | Episode title. |
| `description` | str | Show notes; may contain HTML. |
| `link` | str | Episode web page, **not** the audio URL. |
| `published_at` | str | ISO 8601 UTC `YYYY-MM-DDTHH:MM:SS+00:00`, empty when absent. |
| `duration_seconds` | int | `0` when the feed does not say. |
| `enclosure_url` | str | The audio URL — this is what you stream. |
| `enclosure_type` | str | MIME type (`"audio/mpeg"`, `"audio/x-m4a"`, …). |
| `enclosure_size_bytes` | int | `0` when missing. |
| `image_url` | str | Episode art, falling back to the show's. |

`podcastparser` parses the feed first; `feedparser` is the fallback for
the Atom variants it refuses. You never choose between them.

## 3. YouTube, SoundCloud and other yt-dlp sources

Anything yt-dlp can extract works through the same `url` argument: the
extractor resolves `bestaudio*` and hands the direct URL plus its
headers to ffmpeg. For age-gated or members-only material, borrow a
browser's cookies. **Needs the network**, so no output is pasted:

```python
async def gated():
    async for frame in ph.extract_audio_stream(
        "https://www.youtube.com/watch?v=YE7VzlLtp-4",
        cookies_from_browser="firefox",  # or "chrome", "safari", ...
        target_sample_rate=16000,
    ):
        print(frame["t_abs_s"], frame["pcm"].shape)
        break


asyncio.run(gated())
```

`headers={...}` is merged on top of yt-dlp's own per-source headers,
with your keys winning, for sources that need a `Referer` or a token.

Spotify and Apple Podcasts are refused before any request goes out — see
[Troubleshooting](#troubleshooting) for the exact message and the way
around it.

## 4. Live streams

A YouTube or Twitch live URL resolves to an HLS manifest.
`extract_audio_stream` notices (`is_live=True` from the resolver) and
turns off `-re` pacing by itself, because a live source already paces
itself. The iterator then runs until the broadcast ends. **Needs the
network**:

```python
async def follow_live(url):
    seconds = 0.0
    async for frame in ph.extract_audio_stream(url, target_sample_rate=16000):
        seconds += frame["pcm"].size / 16000
        if seconds >= 30.0:
            print("got 30 s of live audio")
            return  # read the note below before stopping early


asyncio.run(follow_live("https://www.twitch.tv/some-live-channel"))
```

Two constraints here are real, not stylistic:

- `speed != 1.0` on a live source raises `ValueError`. You cannot
  fast-forward past the live edge, and slowing down lets the consumer
  fall behind without bound.
- Stopping the loop early is the only way out of a live source, and
  there is a cleanup defect in that path worth knowing about. It was
  measured on a VOD decoded with `realtime=False`, where ffmpeg runs
  ahead and the unread pipe backs up; a live source delivers at its own
  rate, so the backlog that triggers it does not build.
  [Troubleshooting](#troubleshooting) has the reproduction.

## 5. Stereo and multichannel

`to_mono=True` (the default) gives ffmpeg's standard downmix and a 1-D
array. `to_mono=False` preserves the source's own channel count and
gives a 2-D array of shape `(n_samples, n_channels)`:

```python
async def keep_channels():
    first = True
    # Drained to the end on purpose rather than broken out of — see
    # Troubleshooting for why that matters with realtime=False.
    async for frame in ph.extract_audio_stream(
        "tone.wav",
        to_mono=False,
        target_sample_rate=44100,
        frame_ms=20,
        realtime=False,
    ):
        if first:
            print("shape", frame["pcm"].shape, "ndim", frame["pcm"].ndim)
            left, right = frame["pcm"][:, 0], frame["pcm"][:, 1]
            print("peak L", float(np.abs(left).max()), "peak R", float(np.abs(right).max()))
            first = False


asyncio.run(keep_channels())
```

```text
shape (882, 2) ndim 2
peak L 0.08837890625 peak R 0.08837890625
```

Branch on `pcm.ndim`, never on the sample count: a **mono** source read
with `to_mono=False` still comes back 2-D, shape `(n_samples, 1)`. That
is deliberate, so `ndim` alone tells "downmixed" apart from "native
channels preserved". There is no `channels=N` knob — downmix is
canonical and deterministic, an upmix is a creative choice that belongs
downstream.

One measured consequence of the downmix is worth knowing: ffmpeg's
stereo-to-mono matrix weights each channel at -3 dB, so two **identical**
channels sum to +3 dB. A full-scale correlated stereo file came back
with a mono peak of `1.41`, outside the `[-1.0, 1.0]` range the
`PcmFrame` docstring promises. Clamp, or scale, if a downstream stage
assumes that bound.

## 6. The high-precision resampler

When `target_sample_rate` differs from the source rate, ffmpeg's
`libswresample` does the conversion by default: a polyphase resampler
with an anti-aliasing low-pass at the new Nyquist frequency
(`target_sample_rate / 2`). That is Shannon-correct, and plenty for ASR,
VAD and ML.

`resample_quality="high"` switches to `libsoxr` at 28-bit precision
(`aresample=...:resampler=soxr:precision=28`), roughly ten times slower
for artefacts below the threshold of hearing:

```python
async def audiophile():
    count = 0
    async for _frame in ph.extract_audio_stream(
        "tone.wav",
        target_sample_rate=48000,
        resample_quality="high",
        realtime=False,
    ):
        count += 1
    print("frames:", count)


asyncio.run(audiophile())
```

**Check your ffmpeg build first.** `libsoxr` is a compile-time option,
and a stock Homebrew ffmpeg does not carry it. On the machine these
examples were run on, the snippet above printed `frames: 0` plus an
ffmpeg error on the log, rather than raising:

```text
podcast-helper ffmpeg stderr: [Parsed_aresample_0 @ 0x...] [SWR @ 0x...] Requested resampling engine is unavailable
...
frames: 0
```

So before reaching for `resample_quality="high"`, confirm the engine is
there:

```bash
ffmpeg -hide_banner -version | grep -o -- --enable-libsoxr || echo "no libsoxr: stay on the default"
```

The default `libswresample` path is always available, because it is part
of ffmpeg itself.

## 7. A compressed archive while you stream

`record_to=` adds a second output to the *same* ffmpeg process: one
decode, two encoder paths, no extra subprocess. The archive is written
while you consume the live PCM, and it stays coherent with it — same
sample rate, same channel handling, same `speed`.

```python
import os


async def stream_and_keep():
    count = 0
    async for _frame in ph.extract_audio_stream(
        "tone.wav",
        target_sample_rate=16000,
        to_mono=True,
        realtime=False,
        record_to="tone.mp3",
    ):
        count += 1
    print("frames", count, "archive bytes", os.path.getsize("tone.mp3"))


asyncio.run(stream_and_keep())
```

```text
frames 50 archive bytes 17901
```

The codec comes from the extension: `.mp3` → libmp3lame 128 kbps,
`.m4a` / `.aac` → aac 128 kbps, `.opus` → libopus 96 kbps, `.ogg` →
libvorbis q5, `.flac` → lossless flac, `.wav` → pcm_s16le. Anything else
raises `ValueError` before ffmpeg starts.

## 8. Feeding a model downstream

A 20 ms frame is the right unit for a VAD and the wrong one for most ASR
models, which want a window of a second or more. The pattern is always
the same: accumulate frames, hand over a window, clear. Here the model
is a stand-in that reports what it was given, so the snippet runs as
written:

```python
def transcribe(audio: np.ndarray) -> str:
    """Stand-in for a real ASR call: reports what it was handed."""
    return f"<{audio.size} samples, {audio.size / 16000:.2f}s>"


async def windowed(url, window_s=0.5):
    buffer: list[np.ndarray] = []
    elapsed = 0.0
    async for frame in ph.extract_audio_stream(
        url, target_sample_rate=16000, frame_ms=20, realtime=False
    ):
        buffer.append(frame["pcm"])
        elapsed += 0.020
        if elapsed >= window_s:
            print(f"t={frame['t_abs_s']:.2f}s {transcribe(np.concatenate(buffer))}")
            buffer.clear()
            elapsed = 0.0


asyncio.run(windowed("tone.wav"))
```

```text
t=0.48s <8000 samples, 0.50s>
t=0.98s <8000 samples, 0.50s>
```

Swap `transcribe` for `whisper.transcribe`, a Silero VAD call or an LLM
summariser and the shape of the loop does not change. Two details carry
over to every real consumer:

- `frame_ms=20` at 16 kHz is 320 samples, Silero VAD's native frame, so
  a VAD-gated ingest needs no re-buffering at all.
- `t_abs_s` is monotonic from the start of the source, so timestamps you
  attach to a transcript stay aligned with the original episode.

For a VOD you can also decode faster than real time with `speed=2.0`:
the `atempo` filter chain preserves pitch, so the model is not handed
chipmunks. It raises `ValueError` on a live source.

## 9. The suite working together

podcast-helper is an AI Helpers member, so two of its compositions are
real rather than aspirational.

**os-helper owns logging.** podcast-helper never prints; it reports
through `osh.warning` and `osh.debug`. Raising the level shows you the
exact ffmpeg command it built, which is the single most useful thing to
have when a source misbehaves:

```python
osh.init_logging(level=logging.DEBUG)


async def show_command():
    async for _frame in ph.extract_audio_stream(
        "tone.wav", target_sample_rate=16000, realtime=False
    ):
        pass


asyncio.run(show_command())
```

```text
2026-10-27 13:01:42 | DEBUG | asyncio | Using selector: KqueueSelector
2026-10-27 13:01:42 | DEBUG | os_helper | podcast-helper: source=file is_live=False cmd=ffmpeg -hide_banner -loglevel error -nostdin -i tone.wav -ar 16000 -ac 1 -f f32le -
```

`osh.verbosity(2)` alone sets the level but installs no handler, so
nothing appears; `osh.init_logging(...)` is the call that makes
podcast-helper's own log lines visible.

**vocal-helper consumes this package.** Its `[stream]` extra depends on
podcast-helper, and `vocal_helper.sources.from_url` wraps
`extract_audio_stream` while pinning the contract its speech stages
need — 16 kHz, mono, 20 ms frames — and deliberately refuses to expose
those three as knobs. Statically verified against vocal-helper's source,
not executed here, because it pulls a whole speech stack:

```python
# pip install "vocal-helper[stream]"
from vocal_helper.sources import from_url


async def ingest(url):
    # realtime left at its default: see Troubleshooting on leaving a
    # realtime=False loop early.
    async for frame in from_url(url, record_to="episode.mp3"):
        print(frame["t_abs_s"], frame["pcm"].shape)
        break
```

`youtube-helper` is a declared dependency of podcast-helper, but note
what for: it is what brings the `yt-dlp` + ffmpeg chain into the
environment. The resolution code in `streaming.py` calls `yt_dlp`
directly rather than going through youtube-helper's own API.

## Command line

One click command, `podcast-helper`, with five subcommands whose flag
names match the HTTP and MCP surfaces, so a recipe transposes between
doors by copy-paste. Everything in this section was executed.

```bash
podcast-helper --help
```

```text
Usage: podcast-helper [OPTIONS] COMMAND [ARGS]...

  Podcast Helper — any audio URL in, PCM frames or an archive out.

  Feeds, direct audio links, local files and every yt-dlp source (YouTube,
  SoundCloud, Twitch, ...) go in through the same --url.

Options:
  -V, --version  Show the version and exit.
  -h, --help     Show this message and exit.

Commands:
  feed    Dump an RSS / Atom podcast feed as JSON.
  latest  Print the latest episode's enclosure URL (or full Episode as...
  probe   Report how podcast-helper classified a URL.
  record  Archive any audio-bearing URL to a compressed file.
  stream  Decode any audio-bearing URL to raw f32le PCM on stdout, or a...
```

`probe` answers "what did you decide this URL was?" without decoding a
byte — the fastest way to debug a source that behaves unexpectedly:

```bash
podcast-helper probe --url tone.wav
```

```text
{
  "source_kind": "file",
  "is_live": false,
  "header_count": 0
}
```

`record` archives a whole source to a compressed file and prints the
path it wrote:

```bash
podcast-helper record --url tone.wav --output ep.mp3
```

```text
ep.mp3
```

`stream` writes raw `f32le` PCM to stdout, which is what makes it
pipeable into ffplay, a VAD or an ASR front end. One second at 16 kHz is
16000 float32 samples, so 64000 bytes:

```bash
podcast-helper stream --url tone.wav --no-realtime --sample-rate 16000 | wc -c
```

```text
64000
```

`feed` and `latest` take a feed URL and need the network:

```bash
podcast-helper feed   --url https://feeds.npr.org/510289/podcast.xml --max-episodes 5
podcast-helper latest --url https://feeds.npr.org/510289/podcast.xml --json
```

Other flags worth knowing: `--mono/--stereo`, `--frame-ms`, `--speed`
and `--realtime/--no-realtime` on `stream`; `--show-url` on `probe`,
opt-in because a resolved URL can carry signed tokens. The same verbs
are served over HTTP with the `[api]` extra (`uvicorn
podcast_helper.api:app`, browser GUI at `/gui`) and as MCP tools with
`[mcp]` (`podcast-helper-mcp`, endpoint at `/mcp`).

## Troubleshooting

**A source decodes to zero frames and nothing raises.** When ffmpeg
cannot open the input, the iterator ends empty and the reason goes to
the log rather than to an exception. Check the frame count:

```python
async def main():
    count = 0
    async for _frame in ph.extract_audio_stream("broken.mp3", realtime=False):
        count += 1
    print("frames:", count)


asyncio.run(main())
```

```text
podcast-helper ffmpeg stderr: [in#0 @ 0x...] Failed to find two consecutive MPEG audio frames.
[in#0 @ 0x...] Error opening input: Invalid data found when processing input
Error opening input file broken.mp3.
Error opening input files: Invalid data found when processing input
frames: 0
```

`resample_quality="high"` on an ffmpeg without `libsoxr` fails the same
silent way — see [section 6](#6-the-high-precision-resampler).

**Stopping early on a `realtime=False` loop can hang.** Measured on a
one-second 44.1 kHz local file: `break`ing after the first frame with
`realtime=False` left the process wedged at generator close until it was
killed, while the identical code with `realtime=True` (the default)
exited cleanly, and so did consuming the stream to exhaustion. ffmpeg
races ahead of the consumer, and the unread stdout pipe leaves cleanup
waiting on an end-of-file that never arrives. Until it is fixed: exhaust
the iterator, or keep the default `realtime=True` when you intend to
stop early.

**Spotify and Apple Podcasts URLs are refused.** Deliberately, and
before any network request, with the workaround in the message:

```bash
podcast-helper probe --url https://open.spotify.com/episode/abc
```

```text
Error: Spotify-protected audio is DRM-gated and not retrievable through yt-dlp (or any reliable open tool). If this podcast has a public RSS feed (most do — check the show's website, getrssfeed.com, or Podcast Index), use the .mp3 enclosure URL directly. URL was: 'https://open.spotify.com/episode/abc'
```

**A negative `max_episodes` raises instead of slicing.** `episodes[:-1]`
means "all but the oldest", so a negative cap used to return almost
everything instead of failing:

```text
ValueError: max_episodes must be >= 0, got -1. A negative value would slice from the end of the list (dropping the oldest episodes) rather than capping the count.
```

**A network read hangs.** ffmpeg applies no I/O timeout unless asked, so
a half-closed connection is waited on forever. Network sources get
`-rw_timeout` (60 s by default); local files never do, since a path on
disk cannot stall on a socket:

```bash
export PODCAST_HELPER_RW_TIMEOUT=120   # seconds; 0 disables the bound
```

This bounds the read, it does not make a stall impossible: a run was
observed hanging for over four hours on a `googlevideo.com` URL that had
`-rw_timeout` on its command line. A job that must finish needs a bound
it owns — a supervisor, a watchdog — rather than this one.

**`FileNotFoundError` before the first frame** means `ffmpeg` is not on
`PATH`. The library shells out to it for every source, local files
included.
