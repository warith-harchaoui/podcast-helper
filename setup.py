# -*- coding: utf-8 -*-
"""setuptools shim — actual configuration lives in pyproject.toml.

Kept for compatibility with `pip install git+https://...` URLs that some
tools still resolve via setup.py introspection.
"""
from pathlib import Path

from setuptools import setup

long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="podcast-helper",
    version="0.1.0",
    description=(
        "Podcast Helper — universal audio stream consumer. URL-in → PCM-out "
        "for local files, direct audio URLs, RSS feed enclosures, and "
        "yt-dlp-supported sources (YouTube, Vimeo, Twitch, SoundCloud, …)."
    ),
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Warith HARCHAOUI",
    author_email="Warith HARCHAOUI <warithmetics@deraison.ai>",
    url="https://github.com/warith-harchaoui/podcast-helper",
    packages=["podcast_helper"],
    package_data={"": ["*"]},
    install_requires=[
        "yt-helper @ git+https://github.com/warith-harchaoui/yt-helper.git@v1.1.0",
        "feedparser>=6.0,<7",
        "podcastparser>=0.6,<1",
        "requests>=2.28,<3",
        "numpy>=1.24",
    ],
    extras_require={
        "dev": ["pytest>=8.0", "pytest-asyncio>=0.23"],
    },
    python_requires=">=3.10,<3.14",
)
