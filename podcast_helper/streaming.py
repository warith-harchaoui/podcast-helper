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
import logging
import os
import shlex
from typing import AsyncIterator, Literal, Optional, TypedDict
from urllib.parse import urlparse

import numpy as np
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
    voiced: Optional[bool]


# ---------------------------------------------------------------------------
# Constants — URL classification
# ---------------------------------------------------------------------------

# File extensions we treat as direct audio without probing yt-dlp.
_DIRECT_AUDIO_EXTS = frozenset({
    "mp3", "m4a", "aac", "opus", "ogg", "oga", "wav", "flac",
    "wma", "aiff", "aif", "ape", "ac3", "amr",
    "m3u8",  # HLS manifest — ffmpeg handles natively
})

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
    if os.path.sep in url and os.path.isfile(url):
        return True
    return os.path.isfile(url)


def _strip_file_scheme(url: str) -> str:
    if url.startswith("file://"):
        return url[len("file://"):]
    return url


def _url_extension(url: str) -> str:
    """Return the lowercase extension of the URL path, without the dot."""
    path = urlparse(url).path
    _, _, ext = path.rpartition(".")
    if "." not in path:
        return ""
    return ext.lower().strip()


def _spotify_guard(url: str) -> None:
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
    cookies_from_browser: Optional[str],
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
            f"yt-dlp resolved {url!r} but produced no direct URL "
            f"(extractor={extractor!r})"
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
    user_headers: Optional[dict[str, str]],
    cookies_from_browser: Optional[str],
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


def _build_ffmpeg_cmd(
    direct_url: str,
    *,
    target_sample_rate: int,
    to_mono: bool,
    resample_quality: Literal["default", "high"],
    realtime: bool,
    is_live: bool,
    headers: dict[str, str],
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
    """
    cmd: list[str] = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]

    # Real-time pacing. Forced OFF for live (the source paces itself; -re
    # would double the latency by waiting on already-paced packets).
    if realtime and not is_live:
        cmd += ["-re"]

    # HTTP headers. ffmpeg expects a single CRLF-separated string before -i.
    if headers:
        joined = "\r\n".join(f"{k}: {v}" for k, v in headers.items()) + "\r\n"
        cmd += ["-headers", joined]

    cmd += ["-i", direct_url]

    # Audio filter / resampler choice.
    if resample_quality == "high":
        cmd += ["-af", f"aresample={target_sample_rate}:resampler=soxr:precision=28"]
    else:
        cmd += ["-ar", str(target_sample_rate)]

    # Channel handling — explicit downmix or preserve source.
    if to_mono:
        cmd += ["-ac", "1"]
    # else: omit -ac entirely so ffmpeg preserves the source channel count.

    # Output: raw 32-bit float little-endian PCM to stdout.
    cmd += ["-f", "f32le", "-"]
    return cmd


async def extract_audio_stream(
    url: str,
    *,
    target_sample_rate: int = 16000,
    to_mono: bool = True,
    resample_quality: Literal["default", "high"] = "default",
    realtime: bool = True,
    frame_ms: int = 20,
    headers: Optional[dict[str, str]] = None,
    cookies_from_browser: Optional[str] = None,
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
        raise ValueError(
            f"resample_quality must be 'default' or 'high', got {resample_quality!r}"
        )

    resolved = _resolve_source(
        url,
        user_headers=headers,
        cookies_from_browser=cookies_from_browser,
    )

    cmd = _build_ffmpeg_cmd(
        resolved["direct_url"],
        target_sample_rate=target_sample_rate,
        to_mono=to_mono,
        resample_quality=resample_quality,
        realtime=realtime,
        is_live=resolved["is_live"],
        headers=resolved["headers"],
    )
    logging.debug(
        "podcast-helper: source=%s is_live=%s cmd=%s",
        resolved["source_kind"], resolved["is_live"], shlex.join(cmd),
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
    n_channels = 1 if to_mono else _probe_channel_count(
        resolved["direct_url"], headers=resolved["headers"],
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
            logging.warning("podcast-helper ffmpeg stderr: %s", err)


def _probe_channel_count(direct_url: str, *, headers: dict[str, str]) -> int:
    """Return the source's channel count via ``ffprobe``.

    Used when ``to_mono=False`` so we know how to reshape the raw bytes.
    """
    import subprocess
    cmd = ["ffprobe", "-hide_banner", "-loglevel", "error",
           "-select_streams", "a:0",
           "-show_entries", "stream=channels",
           "-of", "default=nokey=1:noprint_wrappers=1"]
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
    logging.warning(
        "podcast-helper: ffprobe failed to detect channel count; assuming stereo (2). "
        "If the source is mono, set to_mono=True to avoid silently doubled reshape."
    )
    return 2
