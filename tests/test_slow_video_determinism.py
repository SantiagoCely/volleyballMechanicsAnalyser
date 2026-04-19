"""
Optional slow determinism: full ``main.py`` twice on a local clip (YOLO + pipeline).

Requires ``single_jump.mov`` at repo root (gitignored — see CLAUDE.md).
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SAMPLE_VIDEO = os.path.join(ROOT, "single_jump.mov")


@pytest.mark.slow
@pytest.mark.timeout(600)
def test_full_pipeline_twice_identical_json(tmp_path):
    """Mirrors manual ``diff`` consistency check when sample video exists."""
    if not os.path.isfile(SAMPLE_VIDEO):
        pytest.skip("single_jump.mov not present at repo root (optional asset)")

    out1 = tmp_path / "run1.json"
    out2 = tmp_path / "run2.json"
    cmd_base = [
        sys.executable,
        "main.py",
        "--video",
        SAMPLE_VIDEO,
        "--player_id",
        "1",
        "--output",
    ]
    r1 = subprocess.run(
        cmd_base + [str(out1)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=480,
        check=False,
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )
    r2 = subprocess.run(
        cmd_base + [str(out2)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=480,
        check=False,
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )
    assert r1.returncode == 0, r1.stderr + r1.stdout
    assert r2.returncode == 0, r2.stderr + r2.stdout

    with open(out1) as f:
        a = json.load(f)
    with open(out2) as f:
        b = json.load(f)
    assert a == b
