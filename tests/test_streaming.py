"""
Unit tests for ``podcast_helper.streaming``.

The Spotify / Apple Podcasts guards and URL classification primitives
run offline (pure URL parsing). End-to-end streaming against a real
audio source is covered by the ``integration`` marker (slow + network +
requires ffmpeg on PATH).
"""

import asyncio
import os

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


def test_is_local_file_returns_true_for_real_paths(tmp_path):
    f = tmp_path / "x.mp3"
    f.write_bytes(b"x")
    assert _is_local_file(str(f)) is True


def test_is_local_file_returns_false_for_http():
    assert _is_local_file("https://example.com/x.mp3") is False


def test_is_local_file_returns_true_for_file_scheme():
    assert _is_local_file("file:///etc/hosts") is True


def test_strip_file_scheme():
    assert _strip_file_scheme("file:///tmp/x.mp3") == "/tmp/x.mp3"
    assert _strip_file_scheme("/tmp/x.mp3") == "/tmp/x.mp3"


def test_url_extension():
    assert _url_extension("https://feeds.example.com/podcast.xml") == "xml"
    assert _url_extension("https://cdn.example.com/episode.mp3?foo=bar") == "mp3"
    assert _url_extension("https://example.com/") == ""
    assert _url_extension("https://example.com/no-extension") == ""


def test_known_direct_audio_extensions():
    # Sanity: the set must cover what we promise in the README.
    for ext in ("mp3", "m4a", "opus", "ogg", "wav", "flac", "m3u8"):
        assert ext in _DIRECT_AUDIO_EXTS


def test_looks_like_feed_url():
    assert _looks_like_feed_url("https://feeds.example.com/podcast.xml") is True
    assert _looks_like_feed_url("https://feeds.example.com/podcast.rss") is True
    assert _looks_like_feed_url("https://feeds.example.com/podcast.atom") is True
    assert _looks_like_feed_url("https://cdn.example.com/episode.mp3") is False


# ---------------------------------------------------------------------------
# Guards — fail-fast on known-DRM / known-catalog hosts
# ---------------------------------------------------------------------------


def test_spotify_guard_raises_for_known_hosts():
    with pytest.raises(NotImplementedError, match="DRM-gated"):
        _spotify_guard("https://open.spotify.com/episode/abc123")


def test_spotify_guard_pass_for_other_hosts():
    # Should not raise.
    _spotify_guard("https://www.youtube.com/watch?v=abc")
    _spotify_guard("https://example.com/episode.mp3")


def test_apple_podcasts_guard_raises_for_known_hosts():
    with pytest.raises(NotImplementedError, match="Apple"):
        _apple_podcasts_guard("https://podcasts.apple.com/us/podcast/abc/id123")


def test_apple_podcasts_guard_pass_for_other_hosts():
    _apple_podcasts_guard("https://www.youtube.com/watch?v=abc")


# ---------------------------------------------------------------------------
# Validation — bad inputs raise cleanly
# ---------------------------------------------------------------------------


def _consume(coro_gen):
    """Drive an async generator to completion (returns the list of frames)."""
    async def _run():
        return [x async for x in coro_gen]
    return asyncio.get_event_loop().run_until_complete(_run())


def test_invalid_target_sample_rate():
    with pytest.raises(ValueError, match="target_sample_rate"):
        _consume(extract_audio_stream("dummy.mp3", target_sample_rate=0))


def test_invalid_frame_ms():
    with pytest.raises(ValueError, match="frame_ms"):
        _consume(extract_audio_stream("dummy.mp3", frame_ms=0))


def test_invalid_resample_quality():
    with pytest.raises(ValueError, match="resample_quality"):
        _consume(extract_audio_stream("dummy.mp3", resample_quality="bogus"))


def test_spotify_url_raises_early():
    with pytest.raises(NotImplementedError, match="Spotify"):
        _consume(extract_audio_stream("https://open.spotify.com/episode/abc123"))


def test_apple_podcasts_url_raises_early():
    with pytest.raises(NotImplementedError, match="Apple"):
        _consume(extract_audio_stream("https://podcasts.apple.com/us/podcast/abc/id123"))


# ---------------------------------------------------------------------------
# Integration — real local file decode (requires ffmpeg)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_extract_audio_stream_from_local_file_yields_frames(tmp_path):
    """Generate a 1s silent WAV with ffmpeg, decode it back to PCM frames."""
    import shutil
    import subprocess

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not on PATH")

    src = tmp_path / "silence.wav"
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
         "-t", "1.0", str(src)],
        check=True,
    )

    async def collect():
        out = []
        async for frame in extract_audio_stream(
            str(src),
            target_sample_rate=16000,
            to_mono=True,
            realtime=False,           # decode as fast as possible
            frame_ms=20,
        ):
            out.append(frame)
        return out

    frames = asyncio.get_event_loop().run_until_complete(collect())
    # ~1s at 50 frames/s (20ms each) = ~50 frames
    assert 40 <= len(frames) <= 60
    # Mono → shape (n_samples,) with 320 samples for 20ms @ 16kHz
    for f in frames[:5]:
        assert f["pcm"].shape == (320,)
        assert f["pcm"].dtype.name == "float32"
    # Monotonic times
    times = [f["t_abs_s"] for f in frames]
    assert times == sorted(times)
