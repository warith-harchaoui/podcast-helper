"""
Unit tests for ``podcast_helper.feed``.

The parsing primitives (``_parse_duration``, ``_safe_int``,
``_epoch_to_iso``, ``_try_podcastparser``, ``_try_feedparser``) run
offline against in-process RSS XML; no network. End-to-end ``feed(url)``
/ ``latest_episode(url)`` against real podcast feeds is covered by the
``integration`` marker (network).

Author
------
Project maintainers.
"""

from __future__ import annotations

import pytest

from podcast_helper.feed import (
    _epoch_to_iso,
    _parse_duration,
    _safe_int,
    _try_feedparser,
    _try_podcastparser,
)

# ---------------------------------------------------------------------------
# Sample RSS bytes (synthetic — covers iTunes extension + multi-episode order)
# ---------------------------------------------------------------------------

_SAMPLE_RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Test Show</title>
    <link>https://example.com/show</link>
    <description>A test podcast.</description>
    <itunes:image href="https://example.com/show-cover.jpg" />
    <image>
      <url>https://example.com/show-cover.jpg</url>
      <title>Test Show</title>
      <link>https://example.com/show</link>
    </image>
    <item>
      <title>Episode 2 -- newer</title>
      <description>The newer one.</description>
      <link>https://example.com/show/ep2</link>
      <guid isPermaLink="false">ep2-guid</guid>
      <pubDate>Wed, 15 Jan 2025 08:00:00 +0000</pubDate>
      <itunes:duration>01:23:45</itunes:duration>
      <enclosure url="https://cdn.example.com/ep2.mp3" length="48000000" type="audio/mpeg" />
    </item>
    <item>
      <title>Episode 1 -- older</title>
      <description>The older one.</description>
      <link>https://example.com/show/ep1</link>
      <guid isPermaLink="false">ep1-guid</guid>
      <pubDate>Mon, 01 Jan 2025 08:00:00 +0000</pubDate>
      <itunes:duration>3600</itunes:duration>
      <enclosure url="https://cdn.example.com/ep1.mp3" length="30000000" type="audio/mpeg" />
    </item>
  </channel>
</rss>
"""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_parse_duration_seconds_int() -> None:
    """A bare integer number of seconds passes through unchanged."""
    assert _parse_duration(3600) == 3600


def test_parse_duration_seconds_str() -> None:
    """A numeric string of seconds parses to the same integer."""
    assert _parse_duration("3600") == 3600


def test_parse_duration_mmss() -> None:
    """The ``MM:SS`` iTunes form expands to total seconds."""
    assert _parse_duration("12:34") == 12 * 60 + 34


def test_parse_duration_hhmmss() -> None:
    """The ``HH:MM:SS`` iTunes form expands to total seconds."""
    assert _parse_duration("01:23:45") == 5025


def test_parse_duration_garbage() -> None:
    """Unparseable / empty / ``None`` durations degrade to ``0``, never raise."""
    # These are the three "no usable duration" shapes real feeds ship.
    assert _parse_duration("not-a-duration") == 0
    assert _parse_duration("") == 0
    assert _parse_duration(None) == 0


def test_safe_int_handles_garbage() -> None:
    """``_safe_int`` coerces valid ints and falls back to ``0`` otherwise."""
    # Valid int and numeric string both round-trip.
    assert _safe_int(42) == 42
    assert _safe_int("42") == 42
    # Garbage and ``None`` sink to the ``0`` sentinel instead of raising.
    assert _safe_int("nope") == 0
    assert _safe_int(None) == 0


def test_epoch_to_iso() -> None:
    """A Unix epoch renders as an ISO 8601 UTC string with ``+00:00`` offset."""
    # 2025-01-01T00:00:00Z = 1735689600
    iso = _epoch_to_iso(1735689600)
    assert iso.startswith("2025-01-01T00:00:00")
    assert "+00:00" in iso


def test_epoch_to_iso_zero_returns_empty() -> None:
    """The ``0`` / ``None`` "no date" sentinels render as an empty string."""
    assert _epoch_to_iso(0) == ""
    assert _epoch_to_iso(None) == ""


# ---------------------------------------------------------------------------
# podcastparser path on synthetic RSS
# ---------------------------------------------------------------------------


def test_podcastparser_returns_two_episodes() -> None:
    """The primary parser extracts both items and honours the Episode schema."""
    episodes = _try_podcastparser(_SAMPLE_RSS, "https://example.com/feed.xml")
    assert episodes is not None
    assert len(episodes) == 2
    # Schema invariants
    for ep in episodes:
        for key in (
            "guid",
            "title",
            "enclosure_url",
            "enclosure_type",
            "published_at",
            "duration_seconds",
        ):
            assert key in ep
        assert ep["enclosure_url"].endswith(".mp3")


def test_podcastparser_extracts_durations() -> None:
    """Both iTunes duration forms (``HH:MM:SS`` and bare seconds) are parsed."""
    episodes = _try_podcastparser(_SAMPLE_RSS, "https://example.com/feed.xml")
    durations = sorted(e["duration_seconds"] for e in episodes)
    assert durations == [3600, 5025]


def test_podcastparser_extracts_guids() -> None:
    """Each ``<guid>`` is carried through to the Episode ``guid`` field."""
    episodes = _try_podcastparser(_SAMPLE_RSS, "https://example.com/feed.xml")
    guids = {e["guid"] for e in episodes}
    assert guids == {"ep1-guid", "ep2-guid"}


# ---------------------------------------------------------------------------
# feedparser fallback path
# ---------------------------------------------------------------------------


def test_feedparser_returns_two_episodes() -> None:
    """The feedparser fallback parses the same feed into the Episode schema."""
    episodes = _try_feedparser(_SAMPLE_RSS)
    assert len(episodes) == 2
    for ep in episodes:
        assert ep["enclosure_url"].endswith(".mp3")
        assert ep["enclosure_type"] == "audio/mpeg"


# ---------------------------------------------------------------------------
# Integration — real podcast feed (network, slow, gated)
# ---------------------------------------------------------------------------


SAMPLE_FEED_URL = "https://feeds.npr.org/510289/podcast.xml"  # NPR Up First


@pytest.mark.integration
def test_feed_returns_episodes_sorted_newest_first() -> None:
    """A real feed returns episodes ordered newest-first by ``published_at``."""
    from podcast_helper import feed as feed_module

    eps = feed_module.feed(SAMPLE_FEED_URL, max_episodes=5)
    assert len(eps) > 0
    assert all(e["enclosure_url"] for e in eps[:1])
    # Sorted newest first by published_at — non-empty dates should be monotonic decreasing.
    dates = [e["published_at"] for e in eps if e["published_at"]]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.integration
def test_latest_episode_has_audio_enclosure() -> None:
    """The latest-episode convenience always lands on a real audio enclosure."""
    from podcast_helper import latest_episode

    ep = latest_episode(SAMPLE_FEED_URL)
    assert ep["enclosure_url"].startswith("http")
    assert ep["enclosure_type"].startswith("audio/") or ep["enclosure_url"].endswith(".mp3")
