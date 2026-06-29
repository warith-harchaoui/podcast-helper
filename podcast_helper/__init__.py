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

Author:
- Warith HARCHAOUI (https://linkedin.com/in/warith-harchaoui)
"""

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
