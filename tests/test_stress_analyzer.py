"""
Long synthetic streams without the tracker — bounded wall time via pytest-timeout.

Tagged ``@pytest.mark.stress`` — excluded from the default PR gate (see README).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analyzer import JumpAnalyzer


@pytest.mark.stress
@pytest.mark.timeout(180)
def test_many_grounded_frames_monotone_jump_count():
    """Thousands of grounded frames — jump_count stays stable (no phantom jumps)."""
    a = JumpAnalyzer()
    base_hip = 420.0
    a.analyze_frame(1, (172.0, 172.0), base_hip, court_pos=None, frame_time=0.0)
    prev = a.jump_count
    for i in range(1, 8000):
        a.analyze_frame(
            1,
            (172.0, 172.0),
            base_hip + (i % 5) * 0.01,
            court_pos=None,
            frame_time=i * 0.04,
        )
        assert a.jump_count >= prev
        assert a.jump_count == prev
        prev = a.jump_count


@pytest.mark.stress
@pytest.mark.timeout(180)
def test_long_walk_sequence_jump_count_monotone():
    """Many grounded frames with small hip noise — stay below jump/landing thresholds."""
    a = JumpAnalyzer()
    a.analyze_frame(1, (170.0, 170.0), 400.0, court_pos=(0.0, 0.0), frame_time=0.0)
    jc = a.jump_count
    for i in range(1, 3000):
        t = i * 0.05
        hip = 400.0 + float((i % 5)) * 0.2
        a.analyze_frame(
            1,
            (168.0, 168.0),
            hip,
            court_pos=(float(i % 50), 0.0),
            frame_time=t,
        )
        assert a.jump_count == jc
        for e in a.history:
            if e.get("event") == "JUMP":
                assert e["jump_num"] <= a.jump_count
