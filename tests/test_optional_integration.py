"""
Optional integration coverage from ``docs/issue-33-test-strategy-plan.md`` §6 —
subprocess entrypoint with synthetic video + mocked tracker (no GPU).
"""

import json
import os
import subprocess
import sys

import cv2
import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(os.path.dirname(__file__), "run_main_mocked_subprocess.py")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SEQUENCE_PATH = os.path.join(FIXTURES_DIR, "single_jump_sequence.json")


def _fixture_frame_count():
    with open(SEQUENCE_PATH) as f:
        return len(json.load(f))


def _make_synthetic_video(path: str, n_frames: int, fps: float = 10.0) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    writer = cv2.VideoWriter(path, fourcc, fps, (640, 480))
    for _ in range(n_frames):
        writer.write(np.zeros((480, 640, 3), dtype=np.uint8))
    writer.release()


@pytest.mark.timeout(120)
class TestMainSubprocessMockTracker:
    def test_subprocess_exit_zero_and_json_schema(self, tmp_path):
        n = _fixture_frame_count()
        video_path = tmp_path / "pipe.avi"
        out_path = tmp_path / "nested" / "out.json"
        _make_synthetic_video(str(video_path), n_frames=n)

        result = subprocess.run(
            [sys.executable, SCRIPT, str(video_path), str(out_path), "1"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
        assert result.returncode == 0, result.stderr + result.stdout

        assert out_path.is_file()
        with open(out_path) as f:
            data = json.load(f)

        types = [e["event"] for e in data]
        assert types[0] == "SESSION_SUMMARY"
        assert "JUMP" in types
        summary = data[0]
        assert summary["jump_count"] >= 1
        assert "avg_jump_score" in summary
