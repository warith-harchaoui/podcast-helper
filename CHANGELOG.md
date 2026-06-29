# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-06-29

### Added

- `extract_audio_stream(url, ..., speed=1.0)` — new `speed` parameter
  for VOD only. Implemented via ffmpeg's `atempo=` filter so the pitch
  is preserved (no chipmunk effect). `speed > 1.0` speeds up (e.g.
  `2.0` for 2× ASR throughput); `0 < speed < 1.0` slows down (e.g.
  `0.5` for proofreading). Outside `[0.5, 100]` the chain wraps
  multiple `atempo` filters whose product equals `speed`. Raises
  `ValueError` on live streams — you can't fast-forward past the live
  edge, and slowing down lets the consumer fall behind unboundedly.
  Implicitly disables `-re` realtime pacing when `speed != 1.0`.
- `extract_audio_stream(url, ..., record_to=<path>)` — new `record_to`
  parameter that writes a **parallel compressed archive** of the same
  audio to disk while the live PCM stream is consumed. Implemented via
  ffmpeg's native multi-output (one decode, two encoder paths, no
  extra subprocess). Codec is picked from the extension: `.mp3` (mp3,
  128 kbps), `.m4a` / `.aac` (aac, 128 kbps), `.opus` (opus, 96 kbps),
  `.ogg` (vorbis quality 5), `.flac` (lossless), `.wav` (pcm_s16le).
  The archive is `target_sample_rate` / `to_mono` / `speed`-coherent
  with the live PCM (same filter chain). Works for both VOD and live
  (live archives grow for the duration of the stream).

### Tests

- `tests/test_v02_features.py` — 22 unit tests covering `atempo`
  chaining edge cases at the `[0.5, 2.0]` boundaries, codec dispatch
  for every supported archive extension, the augmented
  `_build_ffmpeg_cmd` output shape, and the public
  `extract_audio_stream` validation paths (live-stream rejection,
  non-positive speed, unknown archive extension). Network-free.

## [0.1.4] - 2026-06-29

### Changed

- Bump `youtube-helper` pin from `v1.1.2` to `v1.2.0` — picks up the
  new `extract_frames_stream` wrapper (not used by podcast-helper
  directly, but the transitive `video-helper` v1.5.1 → v1.5.2 bump
  unblocks URL-aware frame extraction for downstream users mixing
  podcast-helper + video-helper in the same env).

## [0.1.3] - 2026-06-29 — superseded by 0.1.4

### Documentation

- Establish suite-wide Python coding-style mandate in `CONTRIBUTING.md`:
  numpy-style docstrings on every function and class, module-level
  docstring header (with usage example + author), full type annotations,
  generous explanatory comments.
- `EXAMPLES.md` cookbook present at the repo root and linked from
  README + LISEZMOI.
- `print(...)` in docs (EXAMPLES.md / README / LISEZMOI) is followed by
  a `#`-comment showing the expected output (doctest / REPL style);
  library `.py` code uses `osh.info` / `osh.warning` / `osh.error`
  instead of bare `print`.
- Every `brew install <pkg>` mention is paired with a brew.sh hint when
  not already obvious from context.
- `.gitignore` updated to drop accidental `*config.json` commits while
  keeping `*config.json.example` templates tracked.

### Changed

- Add GitHub Actions CI.

## [0.1.1] - 2026-06-29

### Changed

- Switch dep from `yt-helper @ v1.1.0` to `youtube-helper @ v1.1.0`
  (upstream rename). Python module name changes transitively:
  `import yt_helper` → `import youtube_helper`.
- Drop `setup.py` (sole source of truth is `pyproject.toml`).

## [0.1.0] - 2026-06-28

First release.

### Features at release

- `extract_audio_stream(url, ...)` — universal audio-stream
  consumer. URL-in → async PCM-out for:
    - local files
    - direct audio URLs (HTTP/HTTPS)
    - RSS / Atom feed URLs (auto-picks the latest episode)
    - any yt-dlp-supported source (YouTube, Vimeo, Twitch,
      SoundCloud, …)
- Backends: ffmpeg + libswresample + libsoxr for
  Shannon-correct resampling with anti-aliasing low-pass at the
  new Nyquist.
- Output: source-native channels OR canonical mono downmix.
- Feed-parsing: `feedparser` + `podcastparser` (so `extract` works
  on RSS URLs not only direct media).
