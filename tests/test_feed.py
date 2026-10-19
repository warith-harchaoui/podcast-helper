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

import importlib

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
    # NOTE: `from podcast_helper import feed` binds the *function* re-exported
    # by __init__.py (`from .feed import ..., feed, ...`), not the `feed`
    # submodule — the package-level name shadows the submodule of the same
    # name. Call it directly rather than via a `.feed` attribute access.
    from podcast_helper import feed

    eps = feed(SAMPLE_FEED_URL, max_episodes=5)
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


# ---------------------------------------------------------------------------
# A cap is a cap, not a slice
# ---------------------------------------------------------------------------
# `episodes[:-1]` is "everything but the last", so a negative max_episodes used
# to be reinterpreted as "drop the N oldest episodes" -- the opposite of a cap.
# With 5 episodes, -1 returned 4 and -3 returned 2: neither an error nor an
# empty list. Because the list is sorted newest-first the dropped ones are the
# oldest, so the caller got *almost* everything, which is the hardest version of
# this to notice.


def _fake_feed(monkeypatch, n: int = 5):
    """Point `feed()` at a synthetic episode list, bypassing the network."""
    # `from podcast_helper import feed` yields the re-exported *function*, not
    # this module -- __init__ shadows the module name with its public API. Import
    # it explicitly so the monkeypatching below targets the module's globals.
    feed_mod = importlib.import_module("podcast_helper.feed")

    episodes = [
        {"title": f"ep{i}", "published_at": f"2026-01-{5 - i:02d}", "audio_url": "u"}
        for i in range(n)
    ]
    monkeypatch.setattr(feed_mod, "_fetch_feed_bytes", lambda url, **kw: b"<rss/>")
    monkeypatch.setattr(
        feed_mod, "_try_podcastparser", lambda raw, url: [dict(e) for e in episodes]
    )
    return feed_mod.feed


@pytest.mark.parametrize("bad", [-1, -3, -100])
def test_feed_rejects_a_negative_cap(monkeypatch, bad: int) -> None:
    feed_fn = _fake_feed(monkeypatch)
    with pytest.raises(ValueError, match="must be >= 0"):
        feed_fn("http://example.com/rss", max_episodes=bad)


@pytest.mark.parametrize(("cap", "expected"), [(None, 5), (5, 5), (3, 3), (1, 1), (0, 0)])
def test_feed_honours_a_valid_cap(monkeypatch, cap, expected: int) -> None:
    """Zero is a coherent cap (return nothing); None means no cap."""
    feed_fn = _fake_feed(monkeypatch)
    assert len(feed_fn("http://example.com/rss", max_episodes=cap)) == expected


def test_feed_keeps_the_newest_when_capped(monkeypatch) -> None:
    """A cap must drop the oldest, not an arbitrary end of the list."""
    feed_fn = _fake_feed(monkeypatch)
    got = feed_fn("http://example.com/rss", max_episodes=2)
    assert [e["title"] for e in got] == ["ep0", "ep1"]


# ---------------------------------------------------------------------------
# A duration cannot be negative, however the feed spells it
# ---------------------------------------------------------------------------
# The numeric branch already clamped at 0, but the string branches did not: an
# <itunes:duration> of "-100" returned -100 and "-1:30" returned -30, while the
# integer -100 returned 0. Same value, different answer depending on spelling.


@pytest.mark.parametrize("raw", [-5, -5.0, "-100", "-1:30", "-1:00:00"])
def test_parse_duration_never_returns_a_negative(raw) -> None:
    assert _parse_duration(raw) == 0


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("3600", 3600), ("60:00", 3600), ("01:00:00", 3600), (90, 90), ("", 0), ("abc", 0)],
)
def test_parse_duration_still_parses_the_valid_forms(raw, expected: int) -> None:
    assert _parse_duration(raw) == expected
