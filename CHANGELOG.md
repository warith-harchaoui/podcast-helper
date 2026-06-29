# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
