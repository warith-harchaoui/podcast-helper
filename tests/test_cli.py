"""
Smoke tests for the ``podcast-helper`` command line.

These tests exercise the CLI *parsing* layer and the subcommands that do
not need ffmpeg or the network (heavier round-trips belong to the
integration suite). The goal is to prevent regressions in the entry
point — flag names, subcommand names, dispatch wiring, and the shape of
what reaches stdout — without pulling in the full ffmpeg + feed stack.

``click`` is a core dependency of the package, so there is nothing to
skip on here: if ``podcast_helper`` imports, so does its CLI.

Usage Example
-------------
>>> #   pytest tests/test_cli.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import sys

import numpy as np
import pytest
from click.testing import CliRunner

import podcast_helper.cli as cli_mod

# Every subcommand the CLI must expose. Named once so a renamed or dropped
# verb fails here rather than in somebody's shell script.
_EXPECTED_SUBCOMMANDS = {"feed", "latest", "stream", "record", "probe"}


def _run_argv(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
    """Invoke ``main()`` the way the console script does, and return the exit code.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Used to replace ``sys.argv`` for the duration of the call.
    argv : list of str
        Arguments after the program name.

    Returns
    -------
    int
        The process exit code the real command would have produced.

    Notes
    -----
    ``CliRunner.invoke`` is the usual way to drive a click command, but it
    captures stdout as *text* and swallows exceptions — so it can neither
    carry raw PCM bytes intact nor exercise ``main()``'s own error
    handling, which is the actual console-script entry point. Driving
    ``main()`` with a replaced ``sys.argv`` keeps both: pair it with
    ``capsysbinary`` to read the real byte stream back.
    """
    monkeypatch.setattr(sys, "argv", ["podcast-helper", *argv])
    try:
        cli_mod.main()
    except SystemExit as exc:  # click exits this way on success and on usage errors
        return int(exc.code or 0)
    return 0


# ---------------------------------------------------------------------------
# Shape of the CLI: subcommands, help, version
# ---------------------------------------------------------------------------


def test_group_exposes_every_expected_subcommand():
    """The group must carry all five verbs (catches a dropped registration)."""
    assert _EXPECTED_SUBCOMMANDS.issubset(set(cli_mod.cli.commands.keys()))


def test_help_exits_zero():
    """``podcast-helper --help`` should exit 0 and name the tool."""
    result = CliRunner().invoke(cli_mod.cli, ["--help"])
    assert result.exit_code == 0
    assert "podcast" in result.output.lower()


def test_dash_h_is_an_alias_for_help():
    """``-h`` must work: it is what people type, and click does not add it by default."""
    short = CliRunner().invoke(cli_mod.cli, ["-h"])
    long = CliRunner().invoke(cli_mod.cli, ["--help"])
    assert short.exit_code == 0
    assert short.output == long.output


def test_version_has_both_a_short_and_a_long_form():
    """``-V`` and ``--version`` must print the same line.

    The short form is capital so a future ``--verbose`` can own ``-v``.
    """
    short = CliRunner().invoke(cli_mod.cli, ["-V"])
    long = CliRunner().invoke(cli_mod.cli, ["--version"])
    assert short.exit_code == 0
    assert "version" in short.output.lower()
    assert short.output == long.output


@pytest.mark.parametrize("sub", sorted(_EXPECTED_SUBCOMMANDS))
def test_subcommand_help_exits_zero(sub):
    """Every subcommand's ``--help`` should exit 0 (no wiring bug)."""
    result = CliRunner().invoke(cli_mod.cli, [sub, "--help"])
    assert result.exit_code == 0


@pytest.mark.parametrize("sub", sorted(_EXPECTED_SUBCOMMANDS))
def test_subcommand_help_does_not_leak_a_numpydoc_block(sub):
    r"""Help text must not reflow a numpydoc ``Parameters`` block at the user.

    click renders the whole docstring, so a numpydoc section on a command
    body reaches the terminal as one run-on paragraph
    ("Parameters ---------- url : str ..."). A command whose docstring needs
    such a block must cut the help with a ``\f`` line. This guard says so
    out loud instead of leaving it to a reviewer's eye.
    """
    output = CliRunner().invoke(cli_mod.cli, [sub, "--help"]).output
    assert "----" not in output
    for section in ("Parameters", "Returns", "Raises"):
        assert section not in output


# ---------------------------------------------------------------------------
# Behaviour of the entry point itself
# ---------------------------------------------------------------------------


def test_main_prints_clean_error_on_a_real_library_exception(capsys, monkeypatch):
    """A library exception (the Spotify-DRM guard) prints ``Error: ...`` + exit 1.

    ``CliRunner.invoke`` catches exceptions itself, so it never exercises
    ``main()`` — the actual console-script entry point. Drive it directly.
    """
    code = _run_argv(monkeypatch, ["probe", "--url", "https://open.spotify.com/episode/abc123"])
    assert code == 1
    assert "Error:" in capsys.readouterr().err


def test_stream_writes_exactly_the_raw_pcm_bytes_to_stdout(monkeypatch, capsysbinary):
    """``stream`` (no ``--output``) writes the concatenated f32le bytes, nothing else.

    This is the whole point of the subcommand: a shell pipeline reads the
    pipe as a byte stream, so one stray character on stdout corrupts the
    audio. Asserting on the exact bytes is the only way to see that, and it
    is why this test drives ``main()`` rather than ``CliRunner``, whose
    text capture would re-encode them.
    """
    frames = [
        np.array([0.1, -0.2, 0.3], dtype=np.float32),
        np.array([0.4, 0.5], dtype=np.float32),
    ]

    async def fake_stream(url, **_kwargs):
        """Stand in for the ffmpeg-backed decoder, yielding two known frames."""
        for pcm in frames:
            yield {"pcm": pcm, "t_abs_s": 0.0}

    monkeypatch.setattr(cli_mod, "extract_audio_stream", fake_stream)

    assert _run_argv(monkeypatch, ["stream", "--url", "ep.mp3", "--no-realtime"]) == 0
    captured = capsysbinary.readouterr()
    assert captured.out == np.concatenate(frames).tobytes()
    assert captured.err == b""


def test_stream_with_output_keeps_stdout_clean_and_names_the_file_on_stderr(
    monkeypatch, capsysbinary, tmp_path
):
    """With ``--output``, the archive path goes to stderr so stdout stays a data channel.

    Same reason as above: a caller may well be piping stdout somewhere even
    when an archive is also being written, so the one human-readable line
    must not land in it.
    """
    archive = tmp_path / "ep.mp3"

    async def fake_stream(url, **kwargs):
        """Stand in for the decoder's ``record_to=`` path; checks it got the path."""
        assert kwargs["record_to"] == str(archive)
        yield {"pcm": np.array([0.0], dtype=np.float32), "t_abs_s": 0.0}

    monkeypatch.setattr(cli_mod, "extract_audio_stream", fake_stream)

    code = _run_argv(
        monkeypatch,
        ["stream", "--url", "ep.mp3", "--no-realtime", "--output", str(archive)],
    )
    assert code == 0
    captured = capsysbinary.readouterr()
    assert captured.out == b""
    assert captured.err.strip() == str(archive).encode()
