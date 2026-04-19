"""Tests for `main` CLI parsing and output path helpers (no YOLO / video I/O)."""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import build_arg_parser, ensure_output_parent_dir, parse_main_args


class TestParseMainArgs:
    def test_default_output_uses_video_stem(self):
        args = parse_main_args(["--video", "clips/SessionA/match.webm"])
        assert args.output == os.path.join("output", "match_analysis.json")

    def test_explicit_output_preserved(self):
        args = parse_main_args(
            ["--video", "a.mov", "--output", "reports/out.json"],
        )
        assert args.output == "reports/out.json"

    def test_flags_parse(self):
        args = parse_main_args(
            ["--video", "v.mp4", "--calibrate", "--player_id", "7", "--show", "--debug"],
        )
        assert args.calibrate is True
        assert args.player_id == 7
        assert args.show is True
        assert args.debug is True


class TestEnsureOutputParentDir:
    def test_creates_nested_directories(self, tmp_path):
        out = tmp_path / "a" / "b" / "c" / "out.json"
        ensure_output_parent_dir(str(out))
        assert (tmp_path / "a" / "b" / "c").is_dir()
        assert not out.exists()

    def test_noop_when_no_parent_in_path(self):
        """Filename only (current directory) — no mkdir call needed for parent."""
        ensure_output_parent_dir("out.json")


def test_build_arg_parser_matches_main_flags():
    """Guarantee `parse_main_args` stays aligned with advertised CLI."""
    parser = build_arg_parser()
    assert "--video" in parser.format_help()
    assert "--calibrate" in parser.format_help()
    assert "--output" in parser.format_help()


@pytest.mark.timeout(30)
def test_main_module_help_exits_zero():
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    result = subprocess.run(
        [sys.executable, "main.py", "--help"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Volleyball Mechanics Analyzer" in result.stdout
