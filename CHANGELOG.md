# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
