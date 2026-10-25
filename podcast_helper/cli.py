"""
Podcast Helper — command-line interface.

The package's one command line: every public function reachable as a
subcommand under ``podcast-helper``. Built with :mod:`click`, so
bash / zsh completion (``click.shell_completion``), colored ``--help``
and nested groups come for free. Installed as the ``podcast-helper``
entry point in ``pyproject.toml``.

Design notes
------------
- Subcommand names and flag names match the FastAPI / MCP surfaces, so a
  recipe written for one door transposes to the others by copy-paste.
- Flags are long options (``--url`` / ``--output`` / …) rather than click
  positionals: the HTTP surface names its fields the same way, and the
  symmetry is worth more than the few saved keystrokes.
- A library exception is caught by the ``main()`` entry point (not
  click's own error handling, which only special-cases
  ``ClickException``/``Abort``) and printed as a clean ``Error: ...``
  line + exit 1, instead of a raw Python traceback.

Usage Example
-------------
>>> #   podcast-helper feed    --url https://feeds.npr.org/510289/podcast.xml
>>> #   podcast-helper latest  --url https://feeds.npr.org/510289/podcast.xml --json
>>> #   podcast-helper stream  --url ep.mp3 --output ep.wav --sample-rate 16000
>>> #   podcast-helper record  --url https://feeds.npr.org/510289/podcast.xml --output ep.mp3
>>> #   podcast-helper probe   --url https://youtu.be/dQw4w9WgXcQ

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import asyncio
import json
import sys

import click

# The library functions themselves — every subcommand is a thin dispatch on
# top of them, with no logic of its own.
from . import extract_audio_stream, feed, latest_episode

# ---------------------------------------------------------------------------
# Top-level group
#
# A bare ``podcast-helper`` prints the help rather than doing anything: click
# groups require a subcommand unless told otherwise, and that is what we want.
# ``max_content_width`` widens the help so the long option lists on ``stream``
# and ``record`` stay readable on a modern terminal.
# ---------------------------------------------------------------------------


@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 100},
)
# ``-V`` beside ``--version``: the capital is the suite's convention, leaving
# ``-v`` free for a future ``--verbose``. ``package_name`` because the package
# exposes no ``__version__`` of its own, so the distribution metadata is the
# only place the number lives.
@click.version_option(None, "-V", "--version", package_name="podcast-helper")
def cli() -> None:
    """Podcast Helper — any audio URL in, PCM frames or an archive out.

    Feeds, direct audio links, local files and every yt-dlp source
    (YouTube, SoundCloud, Twitch, ...) go in through the same --url.
    """
    # Nothing to do at the group level — every subcommand carries its
    # own arguments and side effects.


# ---------------------------------------------------------------------------
# feed
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--url", required=True, help="Feed URL.")
@click.option(
    # IntRange(min=0) so a negative cap fails at parse time, before the feed is
    # fetched: episodes[:-1] would otherwise read as "drop the oldest".
    "--max-episodes",
    type=click.IntRange(min=0),
    default=None,
    help="Cap episodes returned (default: all).",
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


def main() -> None:
    """Console entry point (``podcast-helper``).

    click's own ``main()`` only special-cases ``ClickException``/``Abort``
    (and a broken pipe); a plain library exception would otherwise
    propagate as a raw Python traceback instead of a clean CLI error. This
    wraps the whole invocation and translates that last case into a
    one-line stderr message + exit 1 — click's own control flow (usage
    errors, ``--help``, an explicit ``sys.exit`` in a subcommand) already
    raises ``SystemExit``, a ``BaseException`` this does not catch, so it
    passes through untouched.
    """
    try:
        cli()
    except Exception as err:  # noqa: BLE001 — last resort: see docstring
        click.echo(f"Error: {err}", err=True)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
