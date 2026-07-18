"""
podcast_helper.streaming
========================

Universal audio stream consumer — URL-in → PCM-out.

Accepts:

- Local file paths (``"/tmp/episode.mp3"``, ``"file:///tmp/episode.mp3"``).
- Direct HTTP audio URLs (RSS enclosure MP3 / M4A / Opus / WAV / HLS m3u8).
- RSS / Atom feed URLs (auto-picks the latest episode's enclosure).
- ``yt-dlp``-supported URLs (YouTube, Vimeo, SoundCloud, Twitch VOD / live, …).

Refuses with a clear ``NotImplementedError`` for known-DRM sources
(Spotify-exclusive audio) and known-catalog-not-audio URLs (Apple
Podcasts links — point to ``podcasts.apple.com`` rather than the
underlying RSS) with hints on the correct workaround.

Signal-processing correctness
-----------------------------
When ``target_sample_rate`` differs from the source rate, the conversion
is performed by ffmpeg's ``libswresample`` (default) or ``libsoxr``
(``resample_quality="high"``), both of which apply an **anti-aliasing
low-pass filter at the new Nyquist frequency** (``target_sample_rate / 2``)
before decimation. This satisfies the Shannon-Nyquist sampling theorem.
Naïve subsampling (keeping every Nth sample) would fold supra-Nyquist
energy into the audible band and is never used.

Channel handling — two modes only
---------------------------------
- ``to_mono=True``  → ffmpeg's standard downmix matrix (stereo: L+R with
  -3 dB each; 5.1: ITU-standard mix). PCM frame shape ``(n_samples,)``.
- ``to_mono=False`` → the source's **native channel count is preserved**.
  No synthetic upmix, ever. PCM frame shape ``(n_samples, n_channels)``,
  interleaved per sample (LRLR... for stereo).

There is no arbitrary ``channels=N`` knob: downmix-to-mono is canonical
and deterministic; upmix / multi-channel synthesis is a creative choice
that doesn't belong in a library primitive.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import asyncio
import os
import shlex
from collections.abc import AsyncIterator
from typing import Literal, TypedDict
from urllib.parse import urlparse

import numpy as np
import os_helper as osh
from numpy.typing import NDArray
from yt_dlp import YoutubeDL

# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class PcmFrame(TypedDict):
    """One PCM frame in absolute stream time.

    Keys
    ----
    t_abs_s : float
        Seconds since the source started. Monotonic — does not reset on
        reconnect (future v0.3 will pad with silence if reconnect lands).
    pcm : NDArray[np.float32]
        Audio samples in ``[-1.0, 1.0]``, ``float32``.

        - Shape ``(n_samples,)`` when ``to_mono=True`` (default).
        - Shape ``(n_samples, n_channels)`` when ``to_mono=False``, with
          samples interleaved by channel (``[L0, R0, L1, R1, ...]`` for
          stereo, reshaped to ``(n_samples, 2)``).
    voiced : bool | None
        Always ``None`` here — VAD downstream fills it in if used.
    """

    t_abs_s: float
    pcm: NDArray[np.float32]
    voiced: bool | None


# ---------------------------------------------------------------------------
# Constants — URL classification
# ---------------------------------------------------------------------------

# File extensions we treat as direct audio without probing yt-dlp.
_DIRECT_AUDIO_EXTS = frozenset(
    {
        "mp3",
        "m4a",
        "aac",
        "opus",
        "ogg",
        "oga",
        "wav",
        "flac",
        "wma",
        "aiff",
        "aif",
        "ape",
        "ac3",
        "amr",
        "m3u8",  # HLS manifest — ffmpeg handles natively
    }
)

# File extensions / Content-Type substrings that mean "this is a feed".
_FEED_EXTS = frozenset({"xml", "rss", "atom"})
_FEED_CONTENT_TYPE_SUBSTRINGS = (
    "application/rss",
    "application/atom",
    "application/xml",
    "text/xml",
    "application/x.atom+xml",
)

# Hostnames known to gate audio behind DRM / login → fail fast with hint.
_SPOTIFY_HOSTS = ("open.spotify.com", "spotify.com")
_APPLE_PODCASTS_HOSTS = ("podcasts.apple.com",)


# ---------------------------------------------------------------------------
# Internal — URL classification & resolution
# ---------------------------------------------------------------------------


def _is_local_file(url: str) -> bool:
    """True if ``url`` is a local file path or ``file://`` URL."""
    if url.startswith("file://"):
        return True
    # Bare path — must exist on disk to count.
    if os.path.sep in url and osh.file_exists(url):
        return True
    return osh.file_exists(url)


def _strip_file_scheme(url: str) -> str:
    """Remove a leading ``file://`` scheme from a URL, if present.

    Parameters
    ----------
    url : str
        A URL or path that may carry a ``file://`` prefix.

    Returns
    -------
    str
        The bare filesystem path when the scheme was present, otherwise
        the input unchanged.
    """
    # ffmpeg wants a plain path for local files; drop the scheme when set.
    if url.startswith("file://"):
        return url[len("file://") :]
    return url


def _url_extension(url: str) -> str:
    """Return the lowercase extension of the URL path, without the dot."""
    path = urlparse(url).path
    _, _, ext = path.rpartition(".")
    if "." not in path:
        return ""
    return ext.lower().strip()


def _spotify_guard(url: str) -> None:
    """Reject Spotify-hosted URLs with an actionable hint.

    Parameters
    ----------
    url : str
        The URL to inspect.

    Returns
    -------
    None
        Returns silently when the host is not a Spotify domain.

    Raises
    ------
    NotImplementedError
        When ``url`` points at a Spotify host — its audio is DRM-gated and
        not retrievable; the message steers the user to the RSS feed.
    """
    # Match on the host suffix so subdomains are covered too.
    host = urlparse(url).netloc.lower()
    if any(host.endswith(h) for h in _SPOTIFY_HOSTS):
        raise NotImplementedError(
            "Spotify-protected audio is DRM-gated and not retrievable through "
            "yt-dlp (or any reliable open tool). If this podcast has a public "
            "RSS feed (most do — check the show's website, getrssfeed.com, or "
            "Podcast Index), use the .mp3 enclosure URL directly. "
            f"URL was: {url!r}"
        )


def _apple_podcasts_guard(url: str) -> None:
    """Reject Apple Podcasts catalog URLs with an actionable hint.

    Parameters
    ----------
    url : str
        The URL to inspect.

    Returns
    -------
    None
        Returns silently when the host is not an Apple Podcasts domain.

    Raises
    ------
    NotImplementedError
        When ``url`` points at ``podcasts.apple.com`` — it references the
        catalog, not the audio; the message steers the user to the RSS feed.
    """
    # Match on the host suffix so subdomains are covered too.
    host = urlparse(url).netloc.lower()
    if any(host.endswith(h) for h in _APPLE_PODCASTS_HOSTS):
        raise NotImplementedError(
            "podcasts.apple.com URLs point to Apple's catalog, not to the "
            "audio. Find the show's RSS feed (linked on the show's website, "
            "or via getrssfeed.com / Podcast Index) and pass the .mp3 "
            "enclosure URL — or the RSS URL directly (podcast-helper auto-picks "
            "the latest episode from a feed). An Apple→RSS resolver is on "
            "the roadmap for podcast-helper v0.3.0. "
            f"URL was: {url!r}"
        )


def _looks_like_feed_url(url: str) -> bool:
    """Cheap heuristic: extension suggests RSS/Atom."""
    return _url_extension(url) in _FEED_EXTS


class _ResolvedSource(TypedDict):
    """Internal: what ``_resolve_source`` returns for the ffmpeg leg."""

    direct_url: str
    headers: dict[str, str]
    is_live: bool
    source_kind: str  # "file" / "direct_audio" / "rss" / "ytdlp:<extractor>"


def _resolve_via_ytdlp(
    url: str,
    *,
    cookies_from_browser: str | None,
) -> _ResolvedSource:
    """Resolve a URL via yt-dlp's ``bestaudio*`` selector.

    If yt-dlp identifies the URL with the ``generic`` extractor, that
    means the URL is already a direct media link — we return it as-is,
    using the user's headers only.
    """
    ydl_opts: dict = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "bestaudio*/best",
        # Live streams: prefer HLS over DASH (ffmpeg's HLS demuxer is the
        # most battle-tested path).
        "hls_prefer_native": False,
    }
    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    if info is None:
        raise RuntimeError(f"yt-dlp could not extract info for URL: {url!r}")

    if "entries" in info and info["entries"]:
        info = info["entries"][0]

    extractor = (info.get("extractor") or "").lower()
    direct_url = info.get("url")
    if not direct_url:
        raise RuntimeError(
            f"yt-dlp resolved {url!r} but produced no direct URL (extractor={extractor!r})"
        )

    is_live = bool(info.get("is_live") or info.get("live_status") == "is_live")
    ytdlp_headers = dict(info.get("http_headers") or {})

    return {
        "direct_url": direct_url,
        "headers": ytdlp_headers,
        "is_live": is_live,
        "source_kind": f"ytdlp:{extractor}" if extractor != "generic" else "direct_audio",
    }


def _resolve_source(
    url: str,
    *,
    user_headers: dict[str, str] | None,
    cookies_from_browser: str | None,
) -> _ResolvedSource:
    """Auto-detect ``url`` and return everything needed to feed ffmpeg.

    Routing:

    1. Spotify host / Apple Podcasts host → ``NotImplementedError`` with hint.
    2. Local file or ``file://`` → return as direct, no resolution.
    3. Known direct-audio extension (.mp3, .m4a, …, .m3u8) → return as direct.
    4. Known feed extension (.xml, .rss, .atom) → import :mod:`.feed` lazily,
       fetch the latest episode, recurse on its ``enclosure_url``.
    5. Otherwise → yt-dlp resolution (generic extractor → direct, specific
       extractor → resolved direct URL + headers).

    User-provided headers always override yt-dlp's per matching key.
    """
    _spotify_guard(url)
    _apple_podcasts_guard(url)

    # 2. Local file
    if _is_local_file(url):
        return {
            "direct_url": _strip_file_scheme(url),
            "headers": dict(user_headers or {}),
            "is_live": False,
            "source_kind": "file",
        }

    # 3. Direct audio URL by extension
    if _url_extension(url) in _DIRECT_AUDIO_EXTS:
        return {
            "direct_url": url,
            "headers": dict(user_headers or {}),
            "is_live": url.endswith(".m3u8"),  # HLS is typically live (but not always)
            "source_kind": "direct_audio",
        }

    # 4. Feed URL — pick latest episode and recurse on its enclosure.
    if _looks_like_feed_url(url):
        from .feed import latest_episode  # lazy import — avoids cycle at import time

        episode = latest_episode(url)
        return _resolve_source(
            episode["enclosure_url"],
            user_headers=user_headers,
            cookies_from_browser=cookies_from_browser,
        )

    # 5. Default: ask yt-dlp.
    resolved = _resolve_via_ytdlp(url, cookies_from_browser=cookies_from_browser)
    # User headers win over yt-dlp's (caller knows better, e.g. custom UA).
    merged = dict(resolved["headers"])
    if user_headers:
        merged.update(user_headers)
    resolved["headers"] = merged
    return resolved


# ---------------------------------------------------------------------------
# ffmpeg PCM streaming pipeline
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# v0.2.0 — speed= and record_to= helpers
# ---------------------------------------------------------------------------


def _build_atempo_chain(speed: float) -> str:
    """
    Build an ``atempo=...`` filter chain that applies ``speed`` to the
    audio without changing pitch.

    ``atempo`` is bounded by ffmpeg to ``[0.5, 100.0]``. Outside that
    range, the trick is to chain multiple ``atempo`` filters whose
    product equals the requested speed — e.g. ``speed=0.25`` becomes
    ``atempo=0.5,atempo=0.5``.

    Parameters
    ----------
    speed : float
        Target playback rate (1.0 = unchanged; > 1.0 = faster;
        0 < speed < 1.0 = slower). Caller must pre-validate ``speed > 0``.

    Returns
    -------
    str
        The filter expression to splice into ``-af`` (e.g.
        ``"atempo=2.0"`` or ``"atempo=0.5,atempo=0.5"``).
    """
    chain: list[str] = []
    remaining = speed
    if speed >= 1.0:
        # Keep doubling until we're under 100×, then apply the remainder.
        while remaining > 2.0:
            chain.append("atempo=2.0")
            remaining /= 2.0
        chain.append(f"atempo={remaining:.6f}")
    else:
        # Mirror logic for slowdown.
        while remaining < 0.5:
            chain.append("atempo=0.5")
            remaining /= 0.5
        chain.append(f"atempo={remaining:.6f}")
    return ",".join(chain)


# Output codec dispatch keyed off file extension. Compressed archive
# formats only — uncompressed (.wav, .raw) routes to PCM separately.
_ARCHIVE_CODECS: dict[str, list[str]] = {
    "mp3": ["-c:a", "libmp3lame", "-b:a", "128k"],
    "m4a": ["-c:a", "aac", "-b:a", "128k"],
    "aac": ["-c:a", "aac", "-b:a", "128k"],
    "opus": ["-c:a", "libopus", "-b:a", "96k"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "5"],
    "flac": ["-c:a", "flac"],  # lossless, no bitrate
    "wav": ["-c:a", "pcm_s16le"],  # PCM 16-bit
}


def _archive_codec_args(record_to: str) -> list[str]:
    """
    Pick the ffmpeg ``-c:a ... -b:a ...`` args for the parallel archive
    output based on ``record_to``'s extension.

    Parameters
    ----------
    record_to : str
        Path to the archive file (extension picks the codec).

    Returns
    -------
    list[str]
        ffmpeg arguments to splice into the archive output spec.

    Raises
    ------
    ValueError
        If the extension is not in the supported set.
    """
    _, _, ext = record_to.rpartition(".")
    ext = ext.lower()
    if ext not in _ARCHIVE_CODECS:
        raise ValueError(
            f"record_to={record_to!r}: unsupported archive extension {ext!r}. "
            f"Supported: {sorted(_ARCHIVE_CODECS)}"
        )
    return list(_ARCHIVE_CODECS[ext])


def _build_ffmpeg_cmd(
    direct_url: str,
    *,
    target_sample_rate: int,
    to_mono: bool,
    resample_quality: Literal["default", "high"],
    realtime: bool,
    is_live: bool,
    headers: dict[str, str],
    speed: float = 1.0,
    record_to: str | None = None,
) -> list[str]:
    """Assemble the ffmpeg command line.

    Audio filter chain:

    - ``-ar <target_sample_rate>`` triggers libswresample's polyphase
      resampler with anti-aliasing low-pass at the new Nyquist (the
      default; perfectly fine for ASR / VAD / ML).
    - ``-af aresample=<target_sample_rate>:resampler=soxr:precision=28``
      uses libsoxr at 28-bit precision (~10× slower, audiophile-grade)
      when ``resample_quality="high"``.
    - ``-ac 1`` applies the standard ffmpeg downmix matrix when ``to_mono``.
    - When ``to_mono=False``, the channel count of the source is
      preserved verbatim.
    - ``speed != 1.0`` adds ``atempo=...`` to the filter chain (pitch
      preserved). For ``record_to`` archives, the atempo applies to
      BOTH outputs — the PCM stream and the file — so the archive is
      time-warped exactly like the live consumer hears it.
    - ``record_to=<path>`` adds a second output mapping the same audio
      stream to a compressed file (codec picked from the extension).
      Implemented via ffmpeg's native multi-output: one decode, two
      encoder paths, no extra subprocess.
    """
    cmd: list[str] = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]

    # Real-time pacing. Forced OFF for live (the source paces itself; -re
    # would double the latency by waiting on already-paced packets) and
    # OFF for any speed != 1.0 (the user explicitly asked for non-realtime).
    if realtime and not is_live and speed == 1.0:
        cmd += ["-re"]

    # HTTP headers. ffmpeg expects a single CRLF-separated string before -i.
    if headers:
        joined = "\r\n".join(f"{k}: {v}" for k, v in headers.items()) + "\r\n"
        cmd += ["-headers", joined]

    cmd += ["-i", direct_url]

    # Build the per-output audio filter chain. The atempo filter must
    # come before / be combined with aresample for soxr to operate on
    # the time-warped stream.
    af_parts: list[str] = []
    if resample_quality == "high":
        af_parts.append(f"aresample={target_sample_rate}:resampler=soxr:precision=28")
    if speed != 1.0:
        af_parts.append(_build_atempo_chain(speed))

    # ── Output 1: raw 32-bit float LE PCM to stdout (the live consumer).
    if af_parts:
        cmd += ["-af", ",".join(af_parts)]
    if resample_quality != "high":
        # Cheap path: ffmpeg's `-ar` triggers libswresample without
        # needing a filter-graph reference.
        cmd += ["-ar", str(target_sample_rate)]
    if to_mono:
        cmd += ["-ac", "1"]
    cmd += ["-f", "f32le", "-"]

    # ── Output 2 (optional): parallel compressed archive.
    if record_to is not None:
        # Re-apply the same audio filter chain so the archive matches
        # the live PCM exactly (same rate, channels, speed). ffmpeg
        # decodes the input once and feeds two independent encoder
        # paths from it.
        if af_parts:
            cmd += ["-af", ",".join(af_parts)]
        if resample_quality != "high":
            cmd += ["-ar", str(target_sample_rate)]
        if to_mono:
            cmd += ["-ac", "1"]
        cmd += _archive_codec_args(record_to)
        cmd += [record_to]

    return cmd


async def extract_audio_stream(
    url: str,
    *,
    target_sample_rate: int = 16000,
    to_mono: bool = True,
    resample_quality: Literal["default", "high"] = "default",
    realtime: bool = True,
    frame_ms: int = 20,
    headers: dict[str, str] | None = None,
    cookies_from_browser: str | None = None,
    speed: float = 1.0,
    record_to: str | None = None,
) -> AsyncIterator[PcmFrame]:
    """
    Yield PCM frames from any audio-bearing URL.

    Parameters
    ----------
    url : str
        File path, ``file://`` URL, direct audio URL (RSS enclosure MP3 /
        M4A / Opus / WAV / HLS m3u8), RSS feed URL (auto-picks latest
        episode), or any ``yt-dlp``-supported URL (YouTube, Vimeo,
        SoundCloud, Twitch VOD / live, etc.). Spotify-protected and
        Apple Podcasts catalog URLs raise ``NotImplementedError`` early
        with hints to the right workaround.
    target_sample_rate : int, default 16000
        Exact output sample rate in Hz. Conversion uses libswresample
        (default) or libsoxr (``resample_quality="high"``); both apply a
        Shannon-correct anti-aliasing low-pass before decimation.
    to_mono : bool, default True
        - True: ffmpeg standard downmix to one channel; ``pcm.shape == (n_samples,)``.
        - False: source's native channel count preserved; ``pcm.shape == (n_samples, n_channels)``.
    resample_quality : ``"default"`` | ``"high"``, default ``"default"``
        ``"high"`` triggers ``aresample=...:resampler=soxr:precision=28``
        (~10× slower, inaudible artefacts). Default libswresample is
        more than enough for ASR / VAD / ML.
    realtime : bool, default True
        Pace decoding at wall-clock (ffmpeg's ``-re``). Forced OFF for
        live streams (they pace themselves; ``-re`` would only add latency).
    frame_ms : int, default 20
        Frame duration in milliseconds. ``20`` matches Silero VAD's
        native frame size, avoiding a downstream re-buffer.
    headers : dict[str, str], optional
        HTTP headers ffmpeg should send. Merged on top of yt-dlp's
        per-source headers (user keys win).
    cookies_from_browser : str, optional
        ``"firefox"`` / ``"chrome"`` / ``"safari"`` / etc. — passed to
        yt-dlp's ``--cookies-from-browser`` for age-gated or
        members-only sources.
    speed : float, default 1.0
        Playback rate for **VOD only**. Implemented via ffmpeg's
        ``atempo=`` filter so the pitch is preserved (no chipmunk
        effect). ``1.0`` = unchanged; ``> 1.0`` = faster (e.g. ``2.0``
        for 2× ASR throughput on long episodes); ``0 < speed < 1.0`` =
        slower (e.g. ``0.5`` for half-speed transcription proofing).
        Outside ``[0.5, 100]`` the chain wraps multiple ``atempo``
        filters whose product equals ``speed``. **Raises ``ValueError``
        on live streams** — you can't fast-forward past the live edge,
        and slowing down lets the consumer fall behind unboundedly.
        Implicitly disables the ``-re`` realtime pacing when
        ``speed != 1.0``.
    record_to : str, optional
        If set, ffmpeg writes a **parallel compressed archive** of the
        same audio to this path while the live PCM stream is consumed.
        Implemented via ffmpeg's native multi-output: one decode, two
        encoder paths, no extra subprocess. Codec is picked from the
        extension:

        - ``.mp3`` → ``libmp3lame`` (128 kbps)
        - ``.m4a`` / ``.aac`` → ``aac`` (128 kbps)
        - ``.opus`` → ``libopus`` (96 kbps)
        - ``.ogg`` → ``libvorbis`` (quality 5)
        - ``.flac`` → ``flac`` (lossless)
        - ``.wav`` → ``pcm_s16le``

        Unknown extensions raise ``ValueError``. The archive is
        ``target_sample_rate`` / ``to_mono`` / ``speed`` -coherent
        with the live PCM (same filter chain). For live sources, the
        archive grows for the duration of the stream.

    Yields
    ------
    PcmFrame
        Successive frames in absolute stream time.

    Raises
    ------
    NotImplementedError
        For Spotify-protected URLs (DRM) and Apple Podcasts catalog URLs
        (point to the show's RSS feed instead).
    RuntimeError
        If yt-dlp can't resolve the URL (private / removed / geo-blocked).
    FileNotFoundError
        If ffmpeg is not on PATH.
    ValueError
        If ``speed != 1.0`` and the source is live, if ``speed <= 0``,
        or if ``record_to``'s extension is not in the supported set.

    Examples
    --------
    >>> import asyncio, podcast_helper as ph
    >>> async def main():
    ...     async for frame in ph.extract_audio_stream(
    ...         "https://www.youtube.com/watch?v=YE7VzlLtp-4",
    ...         target_sample_rate=16000, to_mono=True,
    ...     ):
    ...         # frame["pcm"]: np.float32, shape (320,) for 20ms @ 16kHz
    ...         pass
    >>> asyncio.run(main())
    """
    if frame_ms <= 0:
        raise ValueError(f"frame_ms must be > 0, got {frame_ms}")
    if target_sample_rate <= 0:
        raise ValueError(f"target_sample_rate must be > 0, got {target_sample_rate}")
    if resample_quality not in ("default", "high"):
        raise ValueError(f"resample_quality must be 'default' or 'high', got {resample_quality!r}")

    resolved = _resolve_source(
        url,
        user_headers=headers,
        cookies_from_browser=cookies_from_browser,
    )

    # v0.2.0 — speed= validation. atempo is only meaningful for VOD; on
    # a live stream the playhead is at the live edge so "faster" means
    # nothing (you'd have to time-travel forward) and "slower" means
    # the consumer falls behind unboundedly. Surface that explicitly
    # before spawning ffmpeg.
    if speed != 1.0:
        if speed <= 0:
            raise ValueError(f"speed must be > 0, got {speed}")
        if resolved["is_live"]:
            raise ValueError(
                "speed != 1.0 is invalid for live streams (the playhead is "
                "at the live edge — you can't fast-forward past it, and "
                "slowing down lets the consumer fall behind unboundedly). "
                f"is_live=True for URL: {url!r}"
            )

    cmd = _build_ffmpeg_cmd(
        resolved["direct_url"],
        target_sample_rate=target_sample_rate,
        to_mono=to_mono,
        resample_quality=resample_quality,
        realtime=realtime,
        is_live=resolved["is_live"],
        headers=resolved["headers"],
        speed=speed,
        record_to=record_to,
    )
    osh.debug(
        f"podcast-helper: source={resolved['source_kind']} "
        f"is_live={resolved['is_live']} cmd={shlex.join(cmd)}"
    )

    samples_per_frame = max(1, (target_sample_rate * frame_ms) // 1000)
    # We don't know the channel count up front when to_mono=False — ffmpeg
    # decides from the source. We'll discover it on the first read by
    # asking for `samples_per_frame * 4` bytes (mono) and bailing if the
    # read returns more channels than that (we re-stream with the right
    # block size). Practically: probe the source channel count via the
    # resolved info? Cheaper: hardcode mono OR assume the most common
    # case (mono if to_mono, otherwise infer from a first read).
    #
    # Pragmatic path: when to_mono=False, we ask ffmpeg directly and
    # rely on the user knowing the source's channel count. We yield
    # whatever bytes arrive, reshaped to (-1, channels) where channels
    # is detected from a quick ffprobe-like one-shot on first read.
    #
    # Simpler still: when to_mono=False, the channel-count is fixed at
    # whatever the *source* presents. Most podcasts are mono or stereo.
    # We read big enough chunks and reshape on the fly assuming 2 — and
    # if the source is actually mono+to_mono=False, the reshape will
    # appear "stereo with L==R". That's wrong silently. Better: probe
    # via ffprobe once when to_mono=False.
    #
    # For v0.1.0 simplicity: in to_mono=False mode we probe channel
    # count via ffprobe before launching ffmpeg.
    n_channels = (
        1
        if to_mono
        else _probe_channel_count(
            resolved["direct_url"],
            headers=resolved["headers"],
        )
    )
    bytes_per_sample = 4  # float32 LE
    bytes_per_frame = samples_per_frame * n_channels * bytes_per_sample

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    assert proc.stdout is not None
    assert proc.stderr is not None

    t_abs_s = 0.0
    seconds_per_frame = samples_per_frame / target_sample_rate

    try:
        while True:
            try:
                raw = await proc.stdout.readexactly(bytes_per_frame)
            except asyncio.IncompleteReadError as exc:
                if exc.partial:
                    # Pad the trailing partial frame with silence so the
                    # caller sees a clean fixed-size final frame.
                    pad = bytes_per_frame - len(exc.partial)
                    raw = exc.partial + (b"\x00" * pad)
                else:
                    break

            arr = np.frombuffer(raw, dtype=np.float32).copy()
            if n_channels > 1:
                arr = arr.reshape((-1, n_channels))

            yield {"t_abs_s": t_abs_s, "pcm": arr, "voiced": None}
            t_abs_s += seconds_per_frame
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        err = (await proc.stderr.read()).decode("utf-8", errors="replace").strip()
        if err and proc.returncode not in (0, None):
            osh.warning(f"podcast-helper ffmpeg stderr: {err}")


def _probe_channel_count(direct_url: str, *, headers: dict[str, str]) -> int:
    """Return the source's channel count via ``ffprobe``.

    Used when ``to_mono=False`` so we know how to reshape the raw bytes.
    """
    import subprocess

    cmd = [
        "ffprobe",
        "-hide_banner",
        "-loglevel",
        "error",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=channels",
        "-of",
        "default=nokey=1:noprint_wrappers=1",
    ]
    if headers:
        joined = "\r\n".join(f"{k}: {v}" for k, v in headers.items()) + "\r\n"
        cmd += ["-headers", joined]
    cmd += [direct_url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=10)
        if proc.returncode == 0 and proc.stdout.strip().isdigit():
            return max(1, int(proc.stdout.strip()))
    except (subprocess.TimeoutExpired, OSError):
        pass
    osh.warning(
        "podcast-helper: ffprobe failed to detect channel count; assuming stereo (2). "
        "If the source is mono, set to_mono=True to avoid silently doubled reshape."
    )
    return 2
