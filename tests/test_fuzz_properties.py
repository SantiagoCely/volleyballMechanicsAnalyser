"""
Property-style fuzz tests (Hypothesis). Tagged @pytest.mark.fuzz — excluded from the
default fast CI gate; run locally with: pytest tests/test_fuzz_properties.py -m fuzz -v

"""

import itertools
import os
import sys

import pytest
from hypothesis import given, settings, strategies as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analyzer import JumpAnalyzer
from jump_scoring import compute_jump_score


# Bounded: keeps CI optional job and local runs predictable
_FUZZ_SETTINGS = settings(max_examples=60, deadline=None)

# --- jump_scoring -----------------------------------------------------------------


def _metrics_strategy():
    drift = st.one_of(
        st.none(),
        st.fixed_dictionaries(
            {"magnitude": st.floats(0.0, 200.0, allow_nan=False, allow_infinity=False)},
        ),
    )
    knee_angles = st.one_of(
        st.none(),
        st.dictionaries(
            keys=st.sampled_from(["left", "right"]),
            values=st.floats(0.0, 200.0, allow_nan=False, allow_infinity=False),
            max_size=4,
        ),
    )
    return st.fixed_dictionaries(
        {
            "air_time_sec": st.floats(0.0, 5.0, allow_nan=False, allow_infinity=False),
            "jump_height_est_cm": st.floats(-5.0, 80.0, allow_nan=False, allow_infinity=False),
            "jump_height_est_inch": st.floats(0.0, 40.0, allow_nan=False, allow_infinity=False),
            "takeoff_angle_deg": st.one_of(
                st.none(),
                st.floats(0.0, 90.0, allow_nan=False, allow_infinity=False),
            ),
            "knee_angles": knee_angles,
            "knee_symmetry_deg": st.floats(0.0, 180.0, allow_nan=False, allow_infinity=False),
            "min_landing_knee_angle_deg": st.one_of(
                st.none(),
                st.floats(0.0, 180.0, allow_nan=False, allow_infinity=False),
            ),
            "landing_absorption_duration_sec": st.one_of(
                st.none(),
                st.floats(0.0, 3.0, allow_nan=False, allow_infinity=False),
            ),
            "landing_knee_flexion_rate_degs": st.one_of(
                st.none(),
                st.floats(0.0, 500.0, allow_nan=False, allow_infinity=False),
            ),
            "peak_wrist_height_ratio": st.one_of(
                st.none(),
                st.floats(-2.0, 4.0, allow_nan=False, allow_infinity=False),
            ),
            "arm_swing_symmetry_px": st.one_of(
                st.none(),
                st.floats(0.0, 500.0, allow_nan=False, allow_infinity=False),
            ),
            "drift_cm": drift,
        },
    )


def _takeoff_strategy():
    pos = st.one_of(
        st.none(),
        st.lists(st.floats(-2000.0, 2000.0, allow_nan=False), min_size=2, max_size=2),
    )
    return st.fixed_dictionaries(
        {
            "pos": pos,
            "approach_velocity_cms": st.one_of(
                st.none(),
                st.floats(-100.0, 1200.0, allow_nan=False, allow_infinity=False),
            ),
            "stance_width_cm": st.one_of(
                st.none(),
                st.floats(0.0, 200.0, allow_nan=False, allow_infinity=False),
            ),
            "crouch_depth_deg": st.one_of(
                st.none(),
                st.floats(0.0, 180.0, allow_nan=False, allow_infinity=False),
            ),
            "crouch_duration_sec": st.one_of(
                st.none(),
                st.floats(0.0, 5.0, allow_nan=False, allow_infinity=False),
            ),
            "trunk_lean_deg": st.none(),
        },
    )


@pytest.mark.fuzz
@pytest.mark.timeout(180)
@_FUZZ_SETTINGS
@given(metrics=_metrics_strategy(), takeoff=_takeoff_strategy())
def test_compute_jump_score_no_exceptions_bounded_score(metrics, takeoff):
    result = compute_jump_score(metrics, takeoff)
    assert isinstance(result, dict)
    assert "score" in result
    assert isinstance(result["score"], int)
    assert 0 <= result["score"] <= 100
    assert "score_breakdown" in result


@pytest.mark.fuzz
@pytest.mark.timeout(180)
@_FUZZ_SETTINGS
@given(metrics=_metrics_strategy(), takeoff=_takeoff_strategy())
def test_compute_jump_score_breakdown_numeric_channels(metrics, takeoff):
    """When scoring succeeds (non-error breakdown), channel values are bounded."""
    result = compute_jump_score(metrics, takeoff)
    bd = result["score_breakdown"]
    if "_error" in bd:
        assert bd["_error"] == "no scoring inputs available"
        return
    for _name, val in bd.items():
        assert isinstance(val, (int, float))
        assert 0.0 <= float(val) <= 100.0


# --- JumpAnalyzer.analyze_frame sequences ----------------------------------------

_hip_y = st.floats(180.0, 650.0, allow_nan=False, allow_infinity=False)
_knees = st.tuples(
    st.floats(95.0, 185.0, allow_nan=False, allow_infinity=False),
    st.floats(95.0, 185.0, allow_nan=False, allow_infinity=False),
)
_court = st.one_of(
    st.none(),
    st.tuples(
        st.floats(-2000.0, 2000.0, allow_nan=False, allow_infinity=False),
        st.floats(-2000.0, 2000.0, allow_nan=False, allow_infinity=False),
    ),
)


@st.composite
def _mono_times_and_rows(draw):
    """Strictly increasing frame_time; first frame establishes baseline."""
    n = draw(st.integers(min_value=3, max_value=22))
    dts = draw(
        st.lists(
            st.floats(0.02, 1.8, allow_nan=False, allow_infinity=False),
            min_size=n,
            max_size=n,
        ),
    )
    times = list(itertools.accumulate(dts))
    hips = draw(st.lists(_hip_y, min_size=n, max_size=n))
    knees_list = draw(st.lists(_knees, min_size=n, max_size=n))
    courts = draw(st.lists(_court, min_size=n, max_size=n))
    return list(zip(times, hips, knees_list, courts))


@pytest.mark.fuzz
@pytest.mark.timeout(180)
@_FUZZ_SETTINGS
@given(rows=_mono_times_and_rows())
def test_analyze_frame_sequence_no_exceptions_jump_count_monotone(rows):
    """Short random streams: no crash; jump_count never decreases."""
    prev = JumpAnalyzer()
    prev_c = -1
    for frame_time, hip_y, knee_angles, court_pos in rows:
        prev.analyze_frame(
            1,
            knee_angles,
            hip_y,
            court_pos=court_pos,
            frame_time=frame_time,
            foot_court_pos=None,
            upper_body=None,
        )
        assert prev.jump_count >= prev_c
        prev_c = prev.jump_count


@pytest.mark.fuzz
@pytest.mark.timeout(180)
@_FUZZ_SETTINGS
@given(rows=_mono_times_and_rows())
def test_analyze_frame_history_jump_nums_consistent(rows):
    """Each JUMP event jump_num <= analyzer.jump_count at end of stream."""
    a = JumpAnalyzer()
    for frame_time, hip_y, knee_angles, court_pos in rows:
        a.analyze_frame(
            1,
            knee_angles,
            hip_y,
            court_pos=court_pos,
            frame_time=frame_time,
            foot_court_pos=None,
            upper_body=None,
        )
    for entry in a.history:
        if entry.get("event") == "JUMP":
            assert entry["jump_num"] <= a.jump_count
