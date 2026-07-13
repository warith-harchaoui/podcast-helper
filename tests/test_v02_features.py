"""
Unit tests for podcast-helper v0.2.0 — ``speed=`` and ``record_to=``.

These tests exercise the new internals (``_build_atempo_chain``,
``_archive_codec_args``, and the augmented ``_build_ffmpeg_cmd``)
without spawning ffmpeg. They cover:

- ``atempo`` chaining edge cases at the ``[0.5, 2.0]`` boundaries.
- Codec dispatch for every supported archive extension.
- The augmented ``_build_ffmpeg_cmd`` output shape.
- Public ``extract_audio_stream`` validation paths for ``speed`` and
  ``record_to`` (live-stream rejection, non-positive speed, unknown
  archive extension).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from podcast_helper.streaming import (
    _ARCHIVE_CODECS,
    _archive_codec_args,
    _build_atempo_chain,
    _build_ffmpeg_cmd,
    extract_audio_stream,
)


# ---------------------------------------------------------------------------
# _build_atempo_chain
# ---------------------------------------------------------------------------


def test_atempo_chain_unity_is_single_filter() -> None:
    assert _build_atempo_chain(1.0) == "atempo=1.000000"


def test_atempo_chain_2x_is_single_filter() -> None:
    assert _build_atempo_chain(2.0) == "atempo=2.000000"


def test_atempo_chain_above_2x_chains_doubles() -> None:
    """4× = 2× × 2×."""
    chain = _build_atempo_chain(4.0)
    parts = chain.split(",")
    assert parts[0] == "atempo=2.0"
    assert len(parts) >= 2


def test_atempo_chain_half_is_single_filter() -> None:
    assert _build_atempo_chain(0.5) == "atempo=0.500000"


def test_atempo_chain_below_half_chains_halves() -> None:
    """0.25× = 0.5× × 0.5×."""
    chain = _build_atempo_chain(0.25)
    parts = chain.split(",")
    assert parts[0] == "atempo=0.5"
    assert len(parts) >= 2


def test_atempo_chain_product_matches_target_for_chained_case() -> None:
    """Sanity: the chained-filter product should equal speed."""
    chain = _build_atempo_chain(8.0)
    factors = [float(p.split("=")[1]) for p in chain.split(",")]
    product = 1.0
    for f in factors:
        product *= f
    assert product == pytest.approx(8.0, abs=1e-3)


# ---------------------------------------------------------------------------
# _archive_codec_args — every supported extension
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ext", list(_ARCHIVE_CODECS))
def test_archive_codec_args_supported_extension(ext: str) -> None:
    args = _archive_codec_args(f"out.{ext}")
    assert args[0] == "-c:a"
    assert args == _ARCHIVE_CODECS[ext]


def test_archive_codec_args_case_insensitive_extension() -> None:
    """Users who write ``.MP3`` shouldn't get a surprise ValueError."""
    args = _archive_codec_args("OUT.MP3")
    assert args == _ARCHIVE_CODECS["mp3"]


def test_archive_codec_args_unknown_extension_raises() -> None:
    with pytest.raises(ValueError, match="unsupported archive extension"):
        _archive_codec_args("recording.xyz")


# ---------------------------------------------------------------------------
# _build_ffmpeg_cmd — composition of speed + record_to
# ---------------------------------------------------------------------------


def test_build_cmd_no_options_is_unchanged_shape() -> None:
    """Default invocation matches the pre-v0.2.0 shape (no atempo, no archive)."""
    cmd = _build_ffmpeg_cmd(
        "https://example.com/audio.mp3",
        target_sample_rate=16000,
        to_mono=True,
        resample_quality="default",
        realtime=True,
        is_live=False,
        headers={},
    )
    joined = " ".join(cmd)
    assert "atempo" not in joined
    # Single output — the f32le pipe.
    assert joined.count("-f f32le") == 1
    assert "-ar 16000" in joined
    assert "-ac 1" in joined
    # -re for VOD + realtime stays on.
    assert "-re" in joined


def test_build_cmd_speed_adds_atempo_and_disables_re() -> None:
    cmd = _build_ffmpeg_cmd(
        "https://example.com/audio.mp3",
        target_sample_rate=16000,
        to_mono=True,
        resample_quality="default",
        realtime=True,
        is_live=False,
        headers={},
        speed=2.0,
    )
    joined = " ".join(cmd)
    assert "atempo=2.000000" in joined
    # speed != 1.0 explicitly opts out of -re pacing.
    assert "-re" not in joined


def test_build_cmd_record_to_appends_archive_output() -> None:
    cmd = _build_ffmpeg_cmd(
        "https://example.com/audio.mp3",
        target_sample_rate=16000,
        to_mono=True,
        resample_quality="default",
        realtime=True,
        is_live=False,
        headers={},
        record_to="/tmp/archive.mp3",
    )
    joined = " ".join(cmd)
    # Two outputs: f32le pipe and the mp3 archive.
    assert "-f f32le" in joined
    assert "/tmp/archive.mp3" in joined
    assert "libmp3lame" in joined


def test_build_cmd_speed_and_record_to_apply_to_both_outputs() -> None:
    cmd = _build_ffmpeg_cmd(
        "https://example.com/audio.mp3",
        target_sample_rate=16000,
        to_mono=True,
        resample_quality="default",
        realtime=True,
        is_live=False,
        headers={},
        speed=1.5,
        record_to="/tmp/archive.opus",
    )
    joined = " ".join(cmd)
    # atempo appears twice — once per output spec.
    assert joined.count("atempo=") == 2
    assert "libopus" in joined


# ---------------------------------------------------------------------------
# Public extract_audio_stream — validation paths (no ffmpeg spawned)
# ---------------------------------------------------------------------------


def _seed_resolved(monkeypatch: pytest.MonkeyPatch, *, is_live: bool) -> None:
    """Replace ``_resolve_source`` so we never hit yt-dlp."""

    def _fake(url: str, **kwargs: Any):
        return {
            "direct_url": url,
            "headers": {},
            "is_live": is_live,
            "source_kind": "test",
        }

    monkeypatch.setattr("podcast_helper.streaming._resolve_source", _fake)


def test_extract_audio_stream_speed_on_live_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_resolved(monkeypatch, is_live=True)

    async def _consume():
        async for _ in extract_audio_stream("https://example.com/live", speed=2.0):
            pass

    with pytest.raises(ValueError, match="speed != 1.0 is invalid for live"):
        asyncio.run(_consume())


def test_extract_audio_stream_non_positive_speed_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_resolved(monkeypatch, is_live=False)

    async def _consume():
        async for _ in extract_audio_stream("https://example.com/clip.mp3", speed=0):
            pass

    with pytest.raises(ValueError, match="speed must be > 0"):
        asyncio.run(_consume())


def test_extract_audio_stream_unknown_archive_extension_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_resolved(monkeypatch, is_live=False)

    async def _consume():
        async for _ in extract_audio_stream(
            "https://example.com/clip.mp3", record_to="archive.xyz",
        ):
            pass

    with pytest.raises(ValueError, match="unsupported archive extension"):
        asyncio.run(_consume())
