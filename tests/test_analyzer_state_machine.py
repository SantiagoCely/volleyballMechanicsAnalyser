"""
Diagram-driven scenarios for JumpAnalyzer frame-to-frame state.

States of interest (conceptual): grounded → airborne (`is_jumping`) → landing →
post-landing absorption (`post_landing_active`) → grounded.

See `analyzer.py` `analyze_frame` for the authoritative transition logic.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analyzer import JumpAnalyzer


def _feed(
    analyzer,
    hip_y,
    frame_time,
    *,
    knees=(170, 175),
    court_pos=None,
):
    analyzer.analyze_frame(
        1,
        knees,
        hip_y,
        court_pos=court_pos,
        frame_time=frame_time,
        foot_court_pos=None,
        upper_body=None,
    )


@pytest.mark.timeout(60)
class TestAnalyzerStateMachine:
    """Formal transition checks using synthetic frame streams (no tracker)."""

    def test_single_jump_airborne_then_post_landing_window(self):
        """One jump: `is_jumping` while in flight; post-landing active on ground until window ends."""
        a = JumpAnalyzer()
        # Establish baseline (first frame returns early)
        _feed(a, 400.0, 0.0)
        _feed(a, 400.0, 0.04)
        assert not a.is_jumping

        _feed(a, 300.0, 0.08)
        assert a.is_jumping
        assert a.jump_count == 1

        _feed(a, 250.0, 0.10)
        assert a.is_jumping

        _feed(a, 400.0, 0.20)
        assert not a.is_jumping
        assert a.post_landing_active
        assert len(a.history) == 1
        assert a.history[0]["event"] == "JUMP"

        _feed(a, 400.0, 0.25)
        assert a.post_landing_active

        _feed(a, 400.0, 0.52)
        assert not a.post_landing_active

    def test_back_to_back_jump_interrupts_post_landing(self):
        """Second takeoff before the absorption window finishes finalizes the first landing first."""
        a = JumpAnalyzer()
        _feed(a, 400.0, 0.0)
        _feed(a, 400.0, 0.05)
        # Jump 1
        _feed(a, 300.0, 0.10)
        _feed(a, 400.0, 0.30)
        assert len(a.history) == 1
        assert a.post_landing_active

        # Jump 2 starts before 0.3 s post-landing window elapses
        _feed(a, 300.0, 0.35)
        assert a.jump_count == 2
        assert a.is_jumping
        # Prior jump's absorption should have been finalized when jump 2 started
        assert not a.post_landing_active

        _feed(a, 400.0, 0.60)
        assert len(a.history) == 2

    def test_video_ends_mid_flight_no_jump_event(self):
        """Stream ends while airborne: `jump_count` reflects start, but no JUMP until landing."""
        a = JumpAnalyzer()
        _feed(a, 400.0, 0.0)
        _feed(a, 400.0, 0.05)
        _feed(a, 300.0, 0.10)
        assert a.is_jumping
        assert a.jump_count == 1
        assert a.history == []
