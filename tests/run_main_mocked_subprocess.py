#!/usr/bin/env python3
"""
Run ``main.main()`` with ``tracker.PlayerTracker`` mocked (no YOLO load).

Used by integration tests to exercise the real ``main`` module (VideoCapture loop,
``save_logs``) in a **subprocess** with a clean interpreter.

Usage (repo root)::

    python tests/run_main_mocked_subprocess.py <video.avi> <output.json> [player_id]

``single_jump_sequence.json`` drives ``process_frame`` return values; the video should
have at least as many frames as the fixture rows (tests align frame counts).
"""

from __future__ import annotations

import json
import os
import sys
from unittest.mock import MagicMock, patch

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SEQUENCE_PATH = os.path.join(FIXTURES_DIR, "single_jump_sequence.json")


def _load_fixture():
    with open(SEQUENCE_PATH) as f:
        return json.load(f)


def _build_side_effect(frames):
    side_effects = []
    for row in frames:
        foot = (
            (tuple(row["foot_court_pos"][0]), tuple(row["foot_court_pos"][1]))
            if row["foot_court_pos"]
            else None
        )
        side_effects.append(
            (
                1,
                tuple(row["knee_angles"]),
                float(row["hip_y"]),
                tuple(row["court_pos"]),
                foot,
                None,
            )
        )
    return side_effects


def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: run_main_mocked_subprocess.py <video> <output.json> [player_id]",
            file=sys.stderr,
        )
        sys.exit(2)
    video_path = os.path.abspath(sys.argv[1])
    output_path = os.path.abspath(sys.argv[2])
    player_id = sys.argv[3] if len(sys.argv) > 3 else "1"

    frames = _load_fixture()
    side_effects = _build_side_effect(frames)
    mock_inst = MagicMock()
    mock_inst.target_player_id = int(player_id)
    mock_inst.process_frame.side_effect = side_effects

    with patch("tracker.PlayerTracker", return_value=mock_inst):
        import main as main_module

        sys.argv = [
            "main",
            "--video",
            video_path,
            "--player_id",
            player_id,
            "--output",
            output_path,
        ]
        main_module.main()


if __name__ == "__main__":
    main()
