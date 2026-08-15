"""
Smoke tests for the argparse and click CLIs.

These tests exercise the CLI *parsing* layer and the trivial subcommands
that do not need ffmpeg / the network (heavier round-trips belong to
the integration suite). The goal here is to prevent regressions in the
CLI entry points — flag names, subcommand names, dispatch wiring —
without pulling in the full ffmpeg + feed stack.

Usage Example
-------------
>>> #   pytest tests/test_cli.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import pytest

# The click CLI needs the ``click`` runtime dep, which lives in the
# ``[cli]`` optional extra. Skip cleanly if it is not installed.
click = pytest.importorskip("click")

from click.testing import CliRunner  # noqa: E402

# The set of subcommand names both CLIs must expose. Defined once so
# the two parametrized suites stay in lockstep.
_EXPECTED_SUBCOMMANDS = {"feed", "latest", "stream", "record", "probe"}


def test_argparse_parser_builds_without_error():
    """Building the parser should never fail (imports, subcommand wiring)."""
    from podcast_helper.cli_argparse import build_parser

    parser = build_parser()
    # A parser with at least one subcommand exposes them via _subparsers.
    # We assert on the expected list of subcommand names to catch drift.
    subparsers_action = next(
        a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction"
    )
    assert _EXPECTED_SUBCOMMANDS.issubset(set(subparsers_action.choices.keys()))


def test_argparse_help_exits_zero(capsys):
    """``podcast-helper --help`` should exit with code 0 and print usage."""
    from podcast_helper.cli_argparse import main

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "podcast-helper" in captured.out.lower()


@pytest.mark.parametrize("sub", sorted(_EXPECTED_SUBCOMMANDS))
def test_argparse_subcommand_help_exits_zero(sub, capsys):
    """Every subcommand's ``--help`` should exit 0 (no wiring bug)."""
    from podcast_helper.cli_argparse import main

    with pytest.raises(SystemExit) as exc:
        main([sub, "--help"])
    assert exc.value.code == 0


def test_click_group_has_expected_subcommands():
    """The click group must expose the same subcommands as the argparse CLI."""
    from podcast_helper.cli_click import cli

    assert _EXPECTED_SUBCOMMANDS.issubset(set(cli.commands.keys()))


def test_click_help_exits_zero():
    """``podcast-helper-click --help`` should exit 0."""
    from podcast_helper.cli_click import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "podcast" in result.output.lower()


@pytest.mark.parametrize("sub", sorted(_EXPECTED_SUBCOMMANDS))
def test_click_subcommand_help_exits_zero(sub):
    """Every click subcommand's ``--help`` should exit 0."""
    from podcast_helper.cli_click import cli

    runner = CliRunner()
    result = runner.invoke(cli, [sub, "--help"])
    assert result.exit_code == 0


def test_argparse_main_prints_clean_error_on_a_real_library_exception(capsys):
    """A library exception (Spotify guard) prints ``Error: ...`` + exit 1, not a traceback."""
    from podcast_helper.cli_argparse import main

    code = main(["probe", "--url", "https://open.spotify.com/episode/abc123"])
    assert code == 1
    err = capsys.readouterr().err
    assert "Error:" in err


def test_click_main_prints_clean_error_on_a_real_library_exception(capsys, monkeypatch):
    # CliRunner.invoke (used by every test above) catches exceptions itself,
    # so it never exercises main() -- the actual `podcast-helper-click`
    # console-script entry point. Drive main() directly.
    from podcast_helper.cli_click import main

    monkeypatch.setattr(
        "sys.argv",
        ["podcast-helper-click", "probe", "--url", "https://open.spotify.com/episode/abc123"],
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1
    assert "Error:" in capsys.readouterr().err
