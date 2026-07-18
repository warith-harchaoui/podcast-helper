"""
Podcast Helper — click-based command-line interface.

Twin of :mod:`podcast_helper.cli_argparse`: same public surface (identical
subcommand names, identical flag semantics), but implemented with
:mod:`click` so users who already have a click-native shell setup
(bash / zsh completion via ``click.shell_completion``, colored ``--help``,
nested command groups) can plug it in without friction. Installed as
the ``podcast-helper-click`` entry point in ``pyproject.toml``.

Design notes
------------
- Subcommands mirror ``podcast-helper`` (the argparse twin) so both CLIs
  can be introspected identically by higher layers (FastAPI, MCP).
- Flags reuse the argparse names (``--url`` / ``--output`` / …) rather
  than a more idiomatic click positional style — consistency across
  the two CLIs beats micro-idiomaticity here.
- Errors from the library propagate unchanged; click handles the
  formatting.

Usage Example
-------------
>>> #   podcast-helper-click feed    --url https://feeds.npr.org/510289/podcast.xml
>>> #   podcast-helper-click latest  --url https://feeds.npr.org/510289/podcast.xml --json
>>> #   podcast-helper-click stream  --url ep.mp3 --output ep.wav --sample-rate 16000
>>> #   podcast-helper-click record  --url https://feeds.npr.org/510289/podcast.xml --output ep.mp3
>>> #   podcast-helper-click probe   --url https://youtu.be/dQw4w9WgXcQ

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import asyncio
import json
import sys

try:
    import click
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The click CLI requires the [cli] extra. Install with: pip install 'podcast-helper[cli]'"
    ) from exc

# Same underlying functions as the argparse twin — one source of truth.
from . import extract_audio_stream, feed, latest_episode

# ---------------------------------------------------------------------------
# Top-level group
#
# ``invoke_without_command=False`` forces the user to name a subcommand;
# ``context_settings`` widens the help output so long option lists stay
# readable on modern terminals.
# ---------------------------------------------------------------------------


@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 100},
)
@click.version_option(package_name="podcast-helper", prog_name="podcast-helper-click")
def cli() -> None:
    """Podcast Helper — click twin of the argparse CLI. Same subcommands."""
    # Nothing to do at the group level — every subcommand carries its
    # own arguments and side effects.


# ---------------------------------------------------------------------------
# feed
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--url", required=True, help="Feed URL.")
@click.option(
    "--max-episodes", type=int, default=None, help="Cap episodes returned (default: all)."
)
def feed_cmd(url: str, max_episodes: int | None) -> None:
    """Dump an RSS / Atom podcast feed as JSON."""
    episodes = feed(url, max_episodes=max_episodes)
    click.echo(json.dumps(episodes, indent=2, ensure_ascii=False))


# Register under `feed` name (Python fn can't shadow the import).
cli.add_command(feed_cmd, name="feed")


# ---------------------------------------------------------------------------
# latest
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--url", required=True, help="Feed URL.")
@click.option(
    "--json", "as_json", is_flag=True, default=False, help="Print full Episode dict as JSON."
)
def latest(url: str, as_json: bool) -> None:
    """Print the latest episode's enclosure URL (or full Episode as JSON)."""
    ep = latest_episode(url)
    if as_json:
        click.echo(json.dumps(ep, indent=2, ensure_ascii=False))
    else:
        click.echo(ep["enclosure_url"])


# ---------------------------------------------------------------------------
# stream
# ---------------------------------------------------------------------------


async def _stream_impl(
    url: str,
    sample_rate: int,
    mono: bool,
    realtime: bool,
    frame_ms: int,
    speed: float,
    output: str | None,
) -> None:
    """Drive the streaming decode for the click ``stream`` command.

    Parameters
    ----------
    url : str
        Audio-bearing URL to decode.
    sample_rate : int
        Target sample rate in Hz.
    mono : bool
        Downmix to a single channel when ``True``.
    realtime : bool
        Pace decoding at wall-clock (ffmpeg ``-re``) when ``True``.
    frame_ms : int
        Frame duration in milliseconds.
    speed : float
        Playback rate (VOD only); ``1.0`` leaves timing unchanged.
    output : str or None
        When set, write a compressed archive to this path; otherwise stream
        raw ``f32le`` PCM to stdout.

    Returns
    -------
    None
        Runs for its side effects (stdout bytes or an on-disk archive).
    """
    # When --output is set, ffmpeg writes the parallel archive AND emits
    # PCM to stdout; we sink the PCM frames but let the archive form on
    # disk. Without --output we forward raw f32le to stdout so a shell
    # pipeline can pipe it to ffplay / VAD / ASR.
    if output is not None:
        async for _ in extract_audio_stream(
            url,
            target_sample_rate=sample_rate,
            to_mono=mono,
            realtime=realtime,
            frame_ms=frame_ms,
            speed=speed,
            record_to=output,
        ):
            pass
    else:
        stdout_writer = sys.stdout.buffer
        async for frame in extract_audio_stream(
            url,
            target_sample_rate=sample_rate,
            to_mono=mono,
            realtime=realtime,
            frame_ms=frame_ms,
            speed=speed,
        ):
            stdout_writer.write(frame["pcm"].tobytes())


@cli.command()
@click.option("--url", required=True, help="Audio-bearing URL.")
@click.option(
    "--sample-rate", type=int, default=16000, show_default=True, help="Target sample rate in Hz."
)
@click.option(
    "--mono/--stereo",
    default=True,
    show_default=True,
    help="Downmix to mono or preserve native channels.",
)
@click.option("--frame-ms", type=int, default=20, show_default=True, help="Frame duration in ms.")
@click.option(
    "--speed",
    type=float,
    default=1.0,
    show_default=True,
    help="Playback rate (VOD only, pitch-preserving).",
)
@click.option("--output", type=click.Path(), default=None, help="Optional compressed archive path.")
@click.option(
    "--realtime/--no-realtime",
    default=True,
    show_default=True,
    help="Pace decoding at wall-clock (ffmpeg -re).",
)
def stream(
    url: str,
    sample_rate: int,
    mono: bool,
    frame_ms: int,
    speed: float,
    output: str | None,
    realtime: bool,
) -> None:
    """Decode any audio-bearing URL to raw f32le PCM on stdout, or a compressed archive on disk."""
    asyncio.run(_stream_impl(url, sample_rate, mono, realtime, frame_ms, speed, output))
    if output:
        click.echo(output, err=True)


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--url", required=True, help="Audio-bearing URL.")
@click.option(
    "--output", required=True, type=click.Path(), help="Output archive (mp3/m4a/opus/ogg/flac/wav)."
)
@click.option("--sample-rate", type=int, default=16000, show_default=True)
@click.option("--mono/--stereo", default=True, show_default=True)
@click.option("--frame-ms", type=int, default=20, show_default=True)
@click.option("--speed", type=float, default=1.0, show_default=True)
def record(
    url: str, output: str, sample_rate: int, mono: bool, frame_ms: int, speed: float
) -> None:
    """Archive any audio-bearing URL to a compressed file."""

    async def _run() -> None:
        """Pull the whole stream once, sinking PCM so the archive is written.

        Returns
        -------
        None
            Runs the archive-only decode for its on-disk side effect.
        """
        async for _ in extract_audio_stream(
            url,
            target_sample_rate=sample_rate,
            to_mono=mono,
            realtime=False,  # archive pull, wall-clock pacing is pointless
            frame_ms=frame_ms,
            speed=speed,
            record_to=output,
        ):
            pass

    asyncio.run(_run())
    click.echo(output)


# ---------------------------------------------------------------------------
# probe
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--url", required=True, help="URL to classify.")
@click.option(
    "--show-url",
    is_flag=True,
    default=False,
    help="Include resolved direct URL (may contain signed tokens).",
)
def probe(url: str, show_url: bool) -> None:
    """Report how podcast-helper classified a URL."""
    from .streaming import _resolve_source  # internal but stable across releases

    resolved = _resolve_source(url, user_headers=None, cookies_from_browser=None)
    payload = {
        "source_kind": resolved["source_kind"],
        "is_live": resolved["is_live"],
        "header_count": len(resolved["headers"]),
    }
    if show_url:
        payload["direct_url"] = resolved["direct_url"]
    click.echo(json.dumps(payload, indent=2))


if __name__ == "__main__":  # pragma: no cover
    cli()
