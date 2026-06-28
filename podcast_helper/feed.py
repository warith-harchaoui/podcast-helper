"""
podcast_helper.feed
===================

Lightweight RSS / Atom feed reader for podcasts. Returns episodes in a
homogeneous :class:`Episode` shape regardless of feed flavour (iTunes
extensions, Atom, Podcasting 2.0).

Uses :mod:`podcastparser` as primary parser (podcast-aware: iTunes
extensions, transcripts, chapters URL), with a :mod:`feedparser`
fallback for feeds podcastparser refuses (unusual Atom variants).

Public surface
--------------
- :class:`Episode` — typed dict (guid, title, enclosure_url, …)
- :func:`feed` — return episodes ordered most-recent first (via
  ``published_at``)
- :func:`latest_episode` — convenience for the first non-empty enclosure

Author
------
Warith HARCHAOUI — https://harchaoui.org/warith
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, List, Optional, TypedDict

import feedparser
import podcastparser
import requests


# ---------------------------------------------------------------------------
# Public type
# ---------------------------------------------------------------------------


class Episode(TypedDict):
    """One podcast episode, normalised across feed flavours.

    Keys
    ----
    guid : str
        Stable episode identifier (RSS ``<guid>`` or yt-dlp-style fallback).
        Empty string if the feed didn't ship one.
    title : str
        Episode title.
    description : str
        Long-form description / show notes. May contain HTML.
    link : str
        Episode webpage / show notes URL (NOT the audio URL).
    published_at : str
        ISO 8601 timestamp (``YYYY-MM-DDTHH:MM:SS+00:00`` UTC).
        Empty string if not provided.
    duration_seconds : int
        Reported duration. ``0`` when missing.
    enclosure_url : str
        Direct audio URL (the actual media file). This is what you feed
        to :func:`podcast_helper.extract_audio_stream`.
    enclosure_type : str
        MIME type of the enclosure (``"audio/mpeg"``, ``"audio/x-m4a"``, …).
    enclosure_size_bytes : int
        Reported file size of the enclosure. ``0`` when missing.
    image_url : str
        Episode-level cover art URL; falls back to the show's image.
    """

    guid: str
    title: str
    description: str
    link: str
    published_at: str
    duration_seconds: int
    enclosure_url: str
    enclosure_type: str
    enclosure_size_bytes: int
    image_url: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _fetch_feed_bytes(url: str, *, timeout: float = 15.0) -> bytes:
    """GET ``url`` with a browser-like UA and return the raw body."""
    resp = requests.get(
        url,
        headers={"User-Agent": _USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8"},
        timeout=timeout,
    )
    resp.raise_for_status()
    return resp.content


def _safe_int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _epoch_to_iso(epoch: Optional[float]) -> str:
    """Convert a Unix epoch (float or int) into ISO 8601 UTC. Empty on error."""
    if epoch is None or epoch == 0:
        return ""
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat()
    except (OSError, ValueError, OverflowError):
        return ""


def _struct_time_to_iso(st: Any) -> str:
    """feedparser surfaces dates as ``time.struct_time`` — render ISO."""
    if st is None:
        return ""
    try:
        import calendar
        return _epoch_to_iso(calendar.timegm(st))
    except (TypeError, ValueError):
        return ""


# ---------------------------------------------------------------------------
# Parsing — podcastparser primary, feedparser fallback
# ---------------------------------------------------------------------------


def _episode_from_podcastparser(item: dict, *, feed_image: str) -> Episode:
    """Project one podcastparser episode dict into an :class:`Episode`."""
    enclosures = item.get("enclosures") or []
    # podcastparser surfaces enclosures as a list of {url, mime_type, file_size}.
    # We pick the first audio entry; fall back to the first one if no MIME is set.
    chosen: dict = {}
    for enc in enclosures:
        mime = (enc.get("mime_type") or "").lower()
        if mime.startswith("audio/"):
            chosen = enc
            break
    if not chosen and enclosures:
        chosen = enclosures[0]

    published_iso = _epoch_to_iso(item.get("published"))

    return {
        "guid": item.get("guid") or "",
        "title": item.get("title") or "",
        "description": item.get("description") or item.get("subtitle") or "",
        "link": item.get("link") or "",
        "published_at": published_iso,
        "duration_seconds": _safe_int(item.get("total_time")),
        "enclosure_url": chosen.get("url", "") if isinstance(chosen, dict) else "",
        "enclosure_type": chosen.get("mime_type", "") if isinstance(chosen, dict) else "",
        "enclosure_size_bytes": _safe_int(chosen.get("file_size")) if isinstance(chosen, dict) else 0,
        "image_url": item.get("episode_art_url") or feed_image,
    }


def _episode_from_feedparser(entry: Any, *, feed_image: str) -> Episode:
    """Fallback projection from a feedparser entry."""
    # feedparser entries expose enclosures via .enclosures (list of FeedParserDict)
    chosen = None
    for enc in getattr(entry, "enclosures", None) or entry.get("enclosures", []) or []:
        mime = (enc.get("type") or "").lower()
        if mime.startswith("audio/"):
            chosen = enc
            break
    if not chosen:
        encs = getattr(entry, "enclosures", None) or entry.get("enclosures", [])
        if encs:
            chosen = encs[0]

    published_iso = _struct_time_to_iso(getattr(entry, "published_parsed", None) or entry.get("published_parsed"))

    # iTunes duration may be "MM:SS", "HH:MM:SS", or seconds as a string.
    duration_raw = entry.get("itunes_duration") or entry.get("duration") or 0
    duration = _parse_duration(duration_raw)

    # Image: itunes_image / media_thumbnail / image
    image_url = ""
    itunes_image = entry.get("itunes_image")
    if isinstance(itunes_image, dict):
        image_url = itunes_image.get("href") or ""
    if not image_url:
        thumbs = entry.get("media_thumbnail")
        if thumbs and isinstance(thumbs, list) and thumbs:
            image_url = thumbs[0].get("url", "")
    if not image_url:
        image_url = feed_image

    return {
        "guid": entry.get("id") or entry.get("guid") or "",
        "title": entry.get("title") or "",
        "description": entry.get("summary") or entry.get("description") or "",
        "link": entry.get("link") or "",
        "published_at": published_iso,
        "duration_seconds": duration,
        "enclosure_url": chosen.get("href", "") if chosen else "",
        "enclosure_type": chosen.get("type", "") if chosen else "",
        "enclosure_size_bytes": _safe_int(chosen.get("length")) if chosen else 0,
        "image_url": image_url,
    }


def _parse_duration(raw: Any) -> int:
    """Parse iTunes duration: ``"3600"`` / ``"01:00:00"`` / ``"60:00"`` / int."""
    if isinstance(raw, (int, float)):
        return max(0, int(raw))
    if not isinstance(raw, str) or not raw.strip():
        return 0
    parts = raw.strip().split(":")
    try:
        if len(parts) == 1:
            return int(float(parts[0]))
        if len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        if len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except (ValueError, TypeError):
        pass
    return 0


def _try_podcastparser(raw_body: bytes, url: str) -> Optional[List[Episode]]:
    """Run podcastparser; return None on failure (so caller can fall back)."""
    try:
        parsed = podcastparser.parse(url, BytesIO(raw_body))
    except Exception as exc:
        logging.debug("podcastparser refused %s: %s", url, exc)
        return None
    feed_image = parsed.get("cover_url") or ""
    episodes: List[Episode] = []
    for item in parsed.get("episodes") or []:
        ep = _episode_from_podcastparser(item, feed_image=feed_image)
        episodes.append(ep)
    return episodes


def _try_feedparser(raw_body: bytes) -> List[Episode]:
    """Fallback parse via feedparser. Returns possibly empty list on weird feeds."""
    parsed = feedparser.parse(raw_body)
    feed_image = ""
    img = parsed.feed.get("image")
    if isinstance(img, dict):
        feed_image = img.get("href") or img.get("url") or ""
    elif isinstance(img, str):
        feed_image = img

    episodes: List[Episode] = []
    for entry in parsed.entries or []:
        episodes.append(_episode_from_feedparser(entry, feed_image=feed_image))
    return episodes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def feed(url: str, *, max_episodes: Optional[int] = None) -> List[Episode]:
    """
    Fetch an RSS / Atom podcast feed and return its episodes.

    Episodes are sorted **most recent first** by ``published_at`` (ISO);
    episodes without a parseable date sink to the bottom but keep their
    relative order.

    Parameters
    ----------
    url : str
        Feed URL (RSS or Atom).
    max_episodes : int, optional
        Cap the number of episodes returned. ``None`` (default) returns
        everything the feed advertises.

    Returns
    -------
    list[Episode]
        Possibly empty if the feed has no episodes / no audio enclosures.

    Raises
    ------
    requests.HTTPError
        If the GET request returns a non-2xx status.
    RuntimeError
        If neither podcastparser nor feedparser could extract any episode
        (genuinely broken feed).
    """
    raw = _fetch_feed_bytes(url)

    episodes = _try_podcastparser(raw, url)
    if episodes is None or not episodes:
        episodes = _try_feedparser(raw)

    if not episodes:
        raise RuntimeError(
            f"Could not extract any episode from feed: {url!r}. "
            "Neither podcastparser nor feedparser returned entries."
        )

    # Sort newest first. Missing dates → empty string → naturally sinks to end.
    episodes.sort(key=lambda e: e["published_at"], reverse=True)

    if max_episodes is not None:
        episodes = episodes[:max_episodes]
    return episodes


def latest_episode(url: str) -> Episode:
    """
    Return the most recent episode of a podcast feed with a non-empty
    audio enclosure URL.

    Convenience around :func:`feed` for the common "I just want the
    latest" case. Skips items without an audio enclosure (some feeds
    publish text-only "trailer" items).

    Parameters
    ----------
    url : str
        Feed URL.

    Returns
    -------
    Episode

    Raises
    ------
    requests.HTTPError
        If the GET request returns a non-2xx status.
    RuntimeError
        If the feed parses but no episode has an audio enclosure.
    """
    episodes = feed(url)
    for ep in episodes:
        if ep["enclosure_url"]:
            return ep
    raise RuntimeError(
        f"Feed {url!r} parsed but no episode has an audio enclosure. "
        "Check that the feed has real podcast items (not just metadata)."
    )
