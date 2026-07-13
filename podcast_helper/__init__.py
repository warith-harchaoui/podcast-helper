"""
Podcast Helper
==============

Universal audio stream consumer — URL-in → PCM-out.

Accepts local files, direct audio URLs (RSS enclosure MP3 / M4A / Opus /
WAV / HLS m3u8), RSS feed URLs (auto-picks the latest episode), and any
yt-dlp-supported URL (YouTube, Vimeo, SoundCloud, Twitch VOD / live, …).

Refuses Spotify-DRM and Apple Podcasts catalog URLs with clear hints
toward the right workaround (RSS feed).

Main entry points
-----------------
- :func:`extract_audio_stream` — async iterator yielding :class:`PcmFrame`.
- :func:`feed` / :func:`latest_episode` — RSS / Atom parsing with the
  :class:`Episode` typed dict.

Multi-surface exposure
----------------------
The same public functions are surfaced as:

- ``podcast-helper`` — argparse CLI (:mod:`podcast_helper.cli_argparse`).
- ``podcast-helper-click`` — click CLI (:mod:`podcast_helper.cli_click`);
  needs the ``[cli]`` extra.
- FastAPI HTTP app (:mod:`podcast_helper.api`); needs the ``[api]`` extra.
- ``podcast-helper-mcp`` — Model Context Protocol server built on top of
  the FastAPI app (:mod:`podcast_helper.mcp`); needs the ``[api,mcp]`` extras.

Usage Example
-------------
>>> import asyncio
>>> import podcast_helper as ph
>>>
>>> async def main():
...     async for frame in ph.extract_audio_stream(
...         "https://feeds.npr.org/510289/podcast.xml",
...         target_sample_rate=16000,
...         to_mono=True,
...         frame_ms=20,
...     ):
...         # frame["pcm"]: np.float32 (320,) for 20ms @ 16kHz
...         pass
>>> asyncio.run(main())

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

__author__ = "Warith Harchaoui, Ph.D."
__email__ = "warithmetics@deraison.ai"

__all__ = [
    # streaming
    "extract_audio_stream",
    "PcmFrame",
    # feed
    "feed",
    "latest_episode",
    "Episode",
]

from .feed import Episode, feed, latest_episode
from .streaming import PcmFrame, extract_audio_stream
