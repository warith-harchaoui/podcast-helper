"""
Podcast Helper — argparse-based command-line interface.

Thin wrapper around the pure functions in :mod:`podcast_helper` that
exposes the whole toolkit as subcommands under a single ``podcast-helper``
entry point. Written with :mod:`argparse` from the standard library so
the CLI works out of the box on any Python install that has the package
installed — no extra dependency required.

Subcommands
-----------
- ``feed``            — dump an RSS / Atom podcast feed as JSON (episode list)
- ``latest``          — print the latest episode's enclosure URL (or full JSON)
- ``stream``          — decode any audio-bearing URL to raw PCM on stdout or a WAV
- ``record``          — decode + archive to a compressed file (mp3/m4a/opus/…)
- ``probe``           — resolve any URL and print how podcast-helper classified it

Usage Example
-------------
>>> #   podcast-helper feed    --url https://feeds.npr.org/510289/podcast.xml
>>> #   podcast-helper latest  --url https://feeds.npr.org/510289/podcast.xml
>>> #   podcast-helper stream  --url episode.mp3 --output episode.wav --sample-rate 16000
>>> #   podcast-helper record  --url https://feeds.npr.org/510289/podcast.xml --output ep.mp3
>>> #   podcast-helper probe   --url https://youtu.be/dQw4w9WgXcQ

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence

# Import the pure functions here — every subcommand is a thin dispatch
# on top of these, no logic duplication with the library core.
from . import extract_audio_stream, feed, latest_episode

# ---------------------------------------------------------------------------
# Subcommand handlers
#
# Each handler receives the parsed ``argparse.Namespace`` and returns a
# process exit code (``0`` on success). Handlers translate CLI arguments
# into keyword arguments for the underlying library function, print
# machine-friendly output (JSON for structured data, path for file
# outputs), and let exceptions propagate as non-zero exit codes.
# ---------------------------------------------------------------------------


def _handle_feed(ns: argparse.Namespace) -> int:
    """Handle the ``feed`` subcommand: dump a podcast feed as JSON.

    Parameters
    ----------
    ns : argparse.Namespace
        Parsed arguments; uses ``ns.url`` and ``ns.max_episodes``.

    Returns
    -------
    int
        Process exit code (``0`` on success).
    """
    # Dump every episode as JSON — one array so `jq` / downstream pipelines
    # can filter cleanly. Episodes come back most-recent first from feed().
    episodes = feed(ns.url, max_episodes=ns.max_episodes)
    print(json.dumps(episodes, indent=2, ensure_ascii=False))
    return 0


def _handle_latest(ns: argparse.Namespace) -> int:
    """Handle the ``latest`` subcommand: print the latest episode.

    Parameters
    ----------
    ns : argparse.Namespace
        Parsed arguments; uses ``ns.url`` and the ``ns.json`` flag.

    Returns
    -------
    int
        Process exit code (``0`` on success). Prints the enclosure URL by
        default, or the full ``Episode`` dict as JSON when ``--json`` is set.
    """
    # latest_episode() returns an Episode dict. We support two output
    # modes: plain URL (default; friendly for shell chaining) or full
    # JSON (for scripts that want the metadata too).
    ep = latest_episode(ns.url)
    if ns.json:
        print(json.dumps(ep, indent=2, ensure_ascii=False))
    else:
        print(ep["enclosure_url"])
    return 0


async def _stream_to_stdout(ns: argparse.Namespace) -> None:
    """Stream decoded PCM frames to stdout as raw ``f32le`` bytes.

    Parameters
    ----------
    ns : argparse.Namespace
        Parsed arguments; supplies the URL and every streaming knob
        (sample rate, mono/stereo, realtime pacing, frame size, speed).

    Returns
    -------
    None
        Frames are written to ``sys.stdout.buffer`` for their side effect.
    """
    # Emit raw f32le PCM samples to stdout — this is the "URL-in → PCM-out"
    # promise of the library, exposed as a shell primitive. A downstream
    # `ffplay -f f32le -ar <rate> -ac <ch> -i -` will play it back verbatim.
    stdout_writer = sys.stdout.buffer
    async for frame in extract_audio_stream(
        ns.url,
        target_sample_rate=ns.sample_rate,
        to_mono=ns.mono,
        realtime=ns.realtime,
        frame_ms=ns.frame_ms,
        speed=ns.speed,
    ):
        # frame["pcm"] is float32 np.ndarray — tobytes() gives the exact
        # little-endian bytes ffmpeg wrote.
        stdout_writer.write(frame["pcm"].tobytes())


async def _stream_to_wav(ns: argparse.Namespace) -> None:
    """Stream a URL straight to a compressed archive on disk.

    Parameters
    ----------
    ns : argparse.Namespace
        Parsed arguments; uses the URL, the streaming knobs, and
        ``ns.output`` as the ``record_to=`` archive path.

    Returns
    -------
    None
        The on-disk archive at ``ns.output`` is the deliverable; PCM
        frames are consumed and discarded.
    """
    # Delegate to `record_to=` — ffmpeg opens two outputs (PCM to stdout
    # and compressed archive on disk). We only care about the archive
    # here so we sink the PCM frames without keeping them in memory.
    async for _ in extract_audio_stream(
        ns.url,
        target_sample_rate=ns.sample_rate,
        to_mono=ns.mono,
        realtime=ns.realtime,
        frame_ms=ns.frame_ms,
        speed=ns.speed,
        record_to=ns.output,
    ):
        # Intentionally discard — the on-disk archive is the deliverable.
        pass


def _handle_stream(ns: argparse.Namespace) -> int:
    """Handle the ``stream`` subcommand: PCM to stdout or archive to disk.

    Parameters
    ----------
    ns : argparse.Namespace
        Parsed arguments; ``ns.output`` selects the archive path (when set)
        versus raw PCM on stdout.

    Returns
    -------
    int
        Process exit code (``0`` on success).
    """
    # stream is streamy — needs an event loop. When --output is set we
    # ride the parallel-archive path; otherwise raw PCM to stdout.
    if ns.output:
        asyncio.run(_stream_to_wav(ns))
        print(ns.output, file=sys.stderr)
    else:
        asyncio.run(_stream_to_stdout(ns))
    return 0


def _handle_record(ns: argparse.Namespace) -> int:
    """Handle the ``record`` subcommand: archive a URL to a compressed file.

    Parameters
    ----------
    ns : argparse.Namespace
        Parsed arguments; ``ns.output`` (the archive path) is required.

    Returns
    -------
    int
        Process exit code: ``0`` on success, ``2`` when ``--output`` is
        missing.
    """
    # Alias for `stream --output ...` — kept as its own subcommand so
    # the intent ("give me a compressed archive of this URL") is
    # obvious in shell scripts.
    if not ns.output:
        print("error: --output is required for record", file=sys.stderr)
        return 2

    async def _run() -> None:
        """Pull the whole stream once, sinking PCM so the archive is written.

        Returns
        -------
        None
            Runs the archive-only decode for its on-disk side effect.
        """
        async for _ in extract_audio_stream(
            ns.url,
            target_sample_rate=ns.sample_rate,
            to_mono=ns.mono,
            realtime=False,  # archive is a one-shot pull, never realtime
            frame_ms=ns.frame_ms,
            speed=ns.speed,
            record_to=ns.output,
        ):
            pass

    asyncio.run(_run())
    print(ns.output)
    return 0


def _handle_probe(ns: argparse.Namespace) -> int:
    """Handle the ``probe`` subcommand: report how a URL is classified.

    Parameters
    ----------
    ns : argparse.Namespace
        Parsed arguments; uses ``ns.url`` and the ``ns.show_url`` flag.

    Returns
    -------
    int
        Process exit code (``0`` on success). Prints a JSON payload with the
        source kind, live flag and header count; the resolved direct URL is
        included only when ``--show-url`` is set (may carry signed tokens).
    """
    # Expose the internal source-resolution routing so operators can
    # tell whether their URL will be handled as file / direct / rss /
    # yt-dlp-<extractor>. Handy for debugging weird podcast networks.
    from .streaming import _resolve_source  # internal but stable across releases

    resolved = _resolve_source(
        ns.url,
        user_headers=None,
        cookies_from_browser=None,
    )
    # Redact the direct_url by default (may contain time-limited signatures).
    payload = {
        "source_kind": resolved["source_kind"],
        "is_live": resolved["is_live"],
        "header_count": len(resolved["headers"]),
    }
    if ns.show_url:
        payload["direct_url"] = resolved["direct_url"]
    print(json.dumps(payload, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Parser construction
#
# One helper per subcommand keeps ``build_parser`` readable and lets the
# click twin (:mod:`podcast_helper.cli_click`) mirror the exact same flag
# names without any risk of drift.
# ---------------------------------------------------------------------------


def _add_feed(sub: argparse._SubParsersAction) -> None:
    """Register the ``feed`` subcommand on the subparsers action.

    Parameters
    ----------
    sub : argparse._SubParsersAction
        The subparsers container returned by ``add_subparsers``.

    Returns
    -------
    None
        The subparser is attached to ``sub`` in place.
    """
    p = sub.add_parser("feed", help="Dump an RSS / Atom podcast feed as JSON.")
    p.add_argument("--url", required=True, help="Feed URL.")
    p.add_argument(
        "--max-episodes",
        type=int,
        default=None,
        dest="max_episodes",
        help="Cap the number of episodes returned (default: all).",
    )
    p.set_defaults(func=_handle_feed)


def _add_latest(sub: argparse._SubParsersAction) -> None:
    """Register the ``latest`` subcommand on the subparsers action.

    Parameters
    ----------
    sub : argparse._SubParsersAction
        The subparsers container returned by ``add_subparsers``.

    Returns
    -------
    None
        The subparser is attached to ``sub`` in place.
    """
    p = sub.add_parser("latest", help="Print the latest episode's enclosure URL.")
    p.add_argument("--url", required=True, help="Feed URL.")
    p.add_argument("--json", action="store_true", help="Print the full Episode dict as JSON.")
    p.set_defaults(func=_handle_latest)


def _stream_common_args(p: argparse.ArgumentParser) -> None:
    """Attach the streaming flags shared by ``stream`` and ``record``.

    Parameters
    ----------
    p : argparse.ArgumentParser
        The subparser to extend with URL and decoding knobs (sample rate,
        mono/stereo, frame size, playback speed).

    Returns
    -------
    None
        Arguments are added to ``p`` in place.
    """
    # Shared streaming knobs — apply to `stream` and `record` alike.
    p.add_argument("--url", required=True, help="Audio-bearing URL.")
    p.add_argument(
        "--sample-rate",
        type=int,
        default=16000,
        dest="sample_rate",
        help="Target sample rate in Hz (default 16000).",
    )
    p.add_argument("--mono", action="store_true", default=True, help="Downmix to mono (default).")
    p.add_argument(
        "--stereo",
        dest="mono",
        action="store_false",
        help="Preserve source's native channel count.",
    )
    p.add_argument(
        "--frame-ms",
        type=int,
        default=20,
        dest="frame_ms",
        help="Frame duration in ms (default 20 — matches Silero VAD).",
    )
    p.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Playback rate (VOD only). 1.0 = unchanged. Pitch-preserving.",
    )


def _add_stream(sub: argparse._SubParsersAction) -> None:
    """Register the ``stream`` subcommand on the subparsers action.

    Parameters
    ----------
    sub : argparse._SubParsersAction
        The subparsers container returned by ``add_subparsers``.

    Returns
    -------
    None
        The subparser is attached to ``sub`` in place.
    """
    p = sub.add_parser(
        "stream",
        help="Decode any audio-bearing URL to raw f32le PCM on stdout, or a compressed archive on disk.",
    )
    _stream_common_args(p)
    p.add_argument(
        "--output",
        default=None,
        help="Optional compressed archive (mp3/m4a/opus/ogg/flac/wav). Extension picks the codec.",
    )
    p.add_argument(
        "--realtime",
        action="store_true",
        default=True,
        help="Pace decoding at wall-clock (ffmpeg -re; default).",
    )
    p.add_argument(
        "--no-realtime", dest="realtime", action="store_false", help="Decode as fast as possible."
    )
    p.set_defaults(func=_handle_stream)


def _add_record(sub: argparse._SubParsersAction) -> None:
    """Register the ``record`` subcommand on the subparsers action.

    Parameters
    ----------
    sub : argparse._SubParsersAction
        The subparsers container returned by ``add_subparsers``.

    Returns
    -------
    None
        The subparser is attached to ``sub`` in place.
    """
    p = sub.add_parser(
        "record",
        help="Archive any audio-bearing URL to a compressed file (mp3/m4a/opus/ogg/flac/wav).",
    )
    _stream_common_args(p)
    p.add_argument(
        "--output", required=True, help="Output archive path (mp3/m4a/opus/ogg/flac/wav)."
    )
    p.set_defaults(func=_handle_record)


def _add_probe(sub: argparse._SubParsersAction) -> None:
    """Register the ``probe`` subcommand on the subparsers action.

    Parameters
    ----------
    sub : argparse._SubParsersAction
        The subparsers container returned by ``add_subparsers``.

    Returns
    -------
    None
        The subparser is attached to ``sub`` in place.
    """
    p = sub.add_parser("probe", help="Report how podcast-helper classified a URL.")
    p.add_argument("--url", required=True, help="URL to classify.")
    p.add_argument(
        "--show-url",
        action="store_true",
        dest="show_url",
        help="Include the resolved direct URL in the JSON output (may contain signed tokens).",
    )
    p.set_defaults(func=_handle_probe)


def build_parser() -> argparse.ArgumentParser:
    """
    Assemble the top-level ``podcast-helper`` argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Fully wired parser with every subcommand attached.
    """
    parser = argparse.ArgumentParser(
        prog="podcast-helper",
        description=(
            "Podcast Helper — universal audio stream consumer. URL-in → PCM-out for "
            "local files, direct audio URLs, RSS feeds, and yt-dlp-supported sources."
        ),
    )
    # Every non-trivial CLI benefits from `--version`. We resolve it
    # lazily to avoid a hard failure if importlib.metadata blows up.
    try:
        from importlib.metadata import version as _pkg_version

        parser.add_argument(
            "--version",
            action="version",
            version=f"%(prog)s {_pkg_version('podcast-helper')}",
        )
    except Exception:  # pragma: no cover — never fatal
        pass

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    _add_feed(subparsers)
    _add_latest(subparsers)
    _add_stream(subparsers)
    _add_record(subparsers)
    _add_probe(subparsers)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    Entry point invoked by ``podcast-helper`` (see ``[project.scripts]``).

    Parameters
    ----------
    argv : sequence of str, optional
        Arguments to parse. Defaults to ``sys.argv[1:]`` when None.

    Returns
    -------
    int
        Process exit code (``0`` on success).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
