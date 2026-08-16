"""
Unit tests for ``podcast_helper.streaming``.

The Spotify / Apple Podcasts guards and URL classification primitives
run offline (pure URL parsing). End-to-end streaming against a real
audio source is covered by the ``integration`` marker (slow + network +
requires ffmpeg on PATH).

Author
------
Project maintainers.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest

from podcast_helper.streaming import (
    _DIRECT_AUDIO_EXTS,
    _apple_podcasts_guard,
    _is_local_file,
    _looks_like_feed_url,
    _spotify_guard,
    _strip_file_scheme,
    _url_extension,
    extract_audio_stream,
)

# ---------------------------------------------------------------------------
# URL classification — pure functions
# ---------------------------------------------------------------------------


def test_is_local_file_returns_true_for_real_paths(tmp_path: Path) -> None:
    """An existing on-disk path is classified as a local file."""
    f = tmp_path / "x.mp3"
    f.write_bytes(b"x")
    assert _is_local_file(str(f)) is True


def test_is_local_file_returns_false_for_http() -> None:
    """A remote ``http(s)`` URL is never mistaken for a local file."""
    assert _is_local_file("https://example.com/x.mp3") is False


def test_is_local_file_returns_true_for_file_scheme() -> None:
    """The ``file://`` scheme is always treated as a local file."""
    assert _is_local_file("file:///etc/hosts") is True


def test_strip_file_scheme() -> None:
    """``file://`` is stripped to a bare path; bare paths pass through."""
    assert _strip_file_scheme("file:///tmp/x.mp3") == "/tmp/x.mp3"
    assert _strip_file_scheme("/tmp/x.mp3") == "/tmp/x.mp3"


def test_url_extension() -> None:
    """The extension is read from the path, ignoring query strings, empty when absent."""
    assert _url_extension("https://feeds.example.com/podcast.xml") == "xml"
    assert _url_extension("https://cdn.example.com/episode.mp3?foo=bar") == "mp3"
    assert _url_extension("https://example.com/") == ""
    assert _url_extension("https://example.com/no-extension") == ""


def test_known_direct_audio_extensions() -> None:
    """Every audio container the README promises is in the direct-audio set."""
    # Sanity: the set must cover what we promise in the README.
    for ext in ("mp3", "m4a", "opus", "ogg", "wav", "flac", "m3u8"):
        assert ext in _DIRECT_AUDIO_EXTS


def test_looks_like_feed_url() -> None:
    """Feed extensions (.xml/.rss/.atom) match; a direct audio URL does not."""
    assert _looks_like_feed_url("https://feeds.example.com/podcast.xml") is True
    assert _looks_like_feed_url("https://feeds.example.com/podcast.rss") is True
    assert _looks_like_feed_url("https://feeds.example.com/podcast.atom") is True
    assert _looks_like_feed_url("https://cdn.example.com/episode.mp3") is False


# ---------------------------------------------------------------------------
# Guards — fail-fast on known-DRM / known-catalog hosts
# ---------------------------------------------------------------------------


def test_spotify_guard_raises_for_known_hosts() -> None:
    """A Spotify host trips the DRM guard with a descriptive error."""
    with pytest.raises(NotImplementedError, match="DRM-gated"):
        _spotify_guard("https://open.spotify.com/episode/abc123")


def test_spotify_guard_pass_for_other_hosts() -> None:
    """Non-Spotify hosts pass the guard silently (no exception)."""
    # Should not raise.
    _spotify_guard("https://www.youtube.com/watch?v=abc")
    _spotify_guard("https://example.com/episode.mp3")


def test_apple_podcasts_guard_raises_for_known_hosts() -> None:
    """An ``podcasts.apple.com`` catalog URL trips the Apple guard."""
    with pytest.raises(NotImplementedError, match="Apple"):
        _apple_podcasts_guard("https://podcasts.apple.com/us/podcast/abc/id123")


def test_apple_podcasts_guard_pass_for_other_hosts() -> None:
    """Non-Apple hosts pass the guard silently (no exception)."""
    _apple_podcasts_guard("https://www.youtube.com/watch?v=abc")


# ---------------------------------------------------------------------------
# Validation — bad inputs raise cleanly
# ---------------------------------------------------------------------------


def _consume(coro_gen: AsyncIterator[Any]) -> list[Any]:
    """Drive an async generator to completion (returns the list of frames).

    Parameters
    ----------
    coro_gen : AsyncIterator[Any]
        The async generator returned by ``extract_audio_stream`` (or any
        compatible async iterator of frames).

    Returns
    -------
    list[Any]
        Every item the generator yielded, in order. Used here mainly to
        force eager evaluation so validation errors surface synchronously.
    """

    async def _run() -> list[Any]:
        # Collect the whole stream — the validation tests below rely on
        # the error being raised while the generator is driven, not lazily.
        return [x async for x in coro_gen]

    return asyncio.run(_run())


def test_invalid_target_sample_rate() -> None:
    """A non-positive ``target_sample_rate`` is rejected before ffmpeg spawns."""
    with pytest.raises(ValueError, match="target_sample_rate"):
        _consume(extract_audio_stream("dummy.mp3", target_sample_rate=0))


def test_invalid_frame_ms() -> None:
    """A non-positive ``frame_ms`` is rejected before ffmpeg spawns."""
    with pytest.raises(ValueError, match="frame_ms"):
        _consume(extract_audio_stream("dummy.mp3", frame_ms=0))


def test_invalid_resample_quality() -> None:
    """An out-of-vocabulary ``resample_quality`` raises a clear ``ValueError``."""
    with pytest.raises(ValueError, match="resample_quality"):
        _consume(extract_audio_stream("dummy.mp3", resample_quality="bogus"))


def test_spotify_url_raises_early() -> None:
    """A Spotify URL fails fast through the public entry point too."""
    with pytest.raises(NotImplementedError, match="Spotify"):
        _consume(extract_audio_stream("https://open.spotify.com/episode/abc123"))


def test_apple_podcasts_url_raises_early() -> None:
    """An Apple Podcasts URL fails fast through the public entry point too."""
    with pytest.raises(NotImplementedError, match="Apple"):
        _consume(extract_audio_stream("https://podcasts.apple.com/us/podcast/abc/id123"))


# ---------------------------------------------------------------------------
# Integration — real local file decode (requires ffmpeg)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_extract_audio_stream_from_local_file_yields_frames(tmp_path: Path) -> None:
    """Generate a 1s silent WAV with ffmpeg, decode it back to PCM frames."""
    import shutil
    import subprocess

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")

    src = tmp_path / "silence.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=mono",
            "-t",
            "1.0",
            str(src),
        ],
        check=True,
    )

    async def collect() -> list[Any]:
        """Drain the async stream into a list so we can assert on it."""
        out: list[Any] = []
        async for frame in extract_audio_stream(
            str(src),
            target_sample_rate=16000,
            to_mono=True,
            realtime=False,  # decode as fast as possible
            frame_ms=20,
        ):
            out.append(frame)
        return out

    frames = asyncio.run(collect())
    # ~1s at 50 frames/s (20ms each) = ~50 frames
    assert 40 <= len(frames) <= 60
    # Mono → shape (n_samples,) with 320 samples for 20ms @ 16kHz
    for f in frames[:5]:
        assert f["pcm"].shape == (320,)
        assert f["pcm"].dtype.name == "float32"
    # Monotonic times
    times = [f["t_abs_s"] for f in frames]
    assert times == sorted(times)


@pytest.mark.integration
def test_extract_audio_stream_does_not_deadlock_on_flooded_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A subprocess that floods stderr before writing stdout must not hang the stream.

    ffmpeg can write enough to stderr (warnings, reconnects — this module
    targets live/HLS sources) to fill the OS pipe buffer. If stderr is only
    read after the stdout loop exits, the child blocks on its stderr write
    and the whole stream deadlocks. Replaces the real ffmpeg command with a
    throwaway script that writes >1 MB to stderr *before* any stdout, then a
    handful of silent PCM frames — this reliably reproduces the deadlock
    against the old (buggy) implementation and must complete quickly here.
    """
    import podcast_helper.streaming as streaming_module

    src = tmp_path / "fake.wav"
    src.write_bytes(b"")  # never actually decoded — _build_ffmpeg_cmd is replaced below

    # 25 frames of 20ms @ 16kHz mono float32 = 0.5s of silence.
    frame_bytes = 320 * 4
    n_frames = 25
    script = (
        "import sys\n"
        "sys.stderr.write('x' * 2_000_000)\n"
        "sys.stderr.flush()\n"
        f"sys.stdout.buffer.write(b'\\x00' * {frame_bytes * n_frames})\n"
        "sys.stdout.flush()\n"
    )

    def fake_build_cmd(*_args: object, **_kwargs: object) -> list[str]:
        return [sys.executable, "-c", script]

    monkeypatch.setattr(streaming_module, "_build_ffmpeg_cmd", fake_build_cmd)

    async def collect() -> list[Any]:
        out: list[Any] = []
        async for frame in extract_audio_stream(
            str(src),
            target_sample_rate=16000,
            to_mono=True,
            realtime=False,
            frame_ms=20,
        ):
            out.append(frame)
        return out

    frames = asyncio.run(asyncio.wait_for(collect(), timeout=10.0))
    assert len(frames) == n_frames
    for f in frames:
        assert f["pcm"].shape == (320,)


# ---------------------------------------------------------------------------
# Extension-less feed URLs — Content-Type fallback when yt-dlp can't resolve
# ---------------------------------------------------------------------------


def test_extensionless_feed_url_resolves_via_content_type_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A feed URL with no .xml/.rss/.atom extension (e.g. Megaphone-style)
    doesn't match ``_looks_like_feed_url``, so it falls to yt-dlp — which
    can't handle raw RSS/Atom and fails. This must not surface that failure:
    a ``Content-Type`` sniff should recognize it as a feed and recurse onto
    the latest episode's enclosure, exactly like an .xml-suffixed feed would.
    """
    import sys

    import podcast_helper.streaming as streaming_module

    def fake_ytdlp(url: str, *, cookies_from_browser: str | None) -> dict:
        raise RuntimeError(f"yt-dlp could not extract info for URL: {url!r}")

    def fake_head(url: str, **kwargs: object) -> Any:
        class _Resp:
            headers = {"Content-Type": "application/rss+xml; charset=utf-8"}

        return _Resp()

    def fake_latest_episode(url: str) -> dict:
        return {"enclosure_url": "https://cdn.example.com/ep1.mp3"}

    monkeypatch.setattr(streaming_module, "_resolve_via_ytdlp", fake_ytdlp)
    monkeypatch.setattr(streaming_module.requests, "head", fake_head)
    # The lazy `from .feed import latest_episode` inside _resolve_source looks
    # this up on the actual submodule object at call time. `podcast_helper`'s
    # own __init__.py does `from .feed import feed, ...`, which rebinds the
    # *package's* `feed` attribute to the `feed()` function it re-exports,
    # shadowing the submodule reference there -- `import podcast_helper.feed`
    # would silently hand back that function instead. Go through
    # sys.modules['podcast_helper.feed'], which always holds the true
    # submodule object regardless of that shadowing.
    monkeypatch.setattr(sys.modules["podcast_helper.feed"], "latest_episode", fake_latest_episode)

    resolved = streaming_module._resolve_source(
        "https://feeds.megaphone.fm/SOMESHOW",
        user_headers=None,
        cookies_from_browser=None,
    )
    assert resolved["direct_url"] == "https://cdn.example.com/ep1.mp3"
    assert resolved["source_kind"] == "direct_audio"


def test_non_feed_ytdlp_failure_still_raises_the_original_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When yt-dlp fails on a URL that genuinely isn't a feed either (the
    Content-Type probe doesn't match, e.g. an unresolvable YouTube video),
    the original yt-dlp error must propagate unchanged — the feed fallback
    must never mask a real resolution failure.
    """
    import podcast_helper.streaming as streaming_module

    def fake_ytdlp(url: str, *, cookies_from_browser: str | None) -> dict:
        raise RuntimeError("yt-dlp could not extract info for URL: private video")

    def fake_head(url: str, **kwargs: object) -> Any:
        class _Resp:
            headers = {"Content-Type": "text/html; charset=utf-8"}

        return _Resp()

    monkeypatch.setattr(streaming_module, "_resolve_via_ytdlp", fake_ytdlp)
    monkeypatch.setattr(streaming_module.requests, "head", fake_head)

    with pytest.raises(RuntimeError, match="private video"):
        streaming_module._resolve_source(
            "https://www.youtube.com/watch?v=unavailable",
            user_headers=None,
            cookies_from_browser=None,
        )


def test_content_type_probe_never_raises_on_network_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A HEAD request that errors out (timeout, DNS failure, ...) must make
    the probe return False, not propagate — the caller's original yt-dlp
    error is always what the user sees when the probe itself can't confirm
    anything either way."""
    import podcast_helper.streaming as streaming_module

    def fake_head(url: str, **kwargs: object) -> Any:
        raise streaming_module.requests.exceptions.ConnectionError("no route to host")

    monkeypatch.setattr(streaming_module.requests, "head", fake_head)
    assert streaming_module._content_type_looks_like_feed("https://example.com/feed") is False
