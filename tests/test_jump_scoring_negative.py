"""
Negative and edge-case tests for jump_scoring (GitHub #31 Phase 1 — Layer A).

Expected values follow README.md — Output Format — Jump scoring (documented formulas).
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from jump_scoring import (  # noqa: E402
    HIP_HEIGHT_MAX_CM,
    HIP_HEIGHT_MIN_CM,
    LANDING_KNEE_OPT_HIGH,
    LANDING_KNEE_OPT_LOW,
    STANCE_OPT_HIGH,
    STANCE_OPT_LOW,
    TAKEOFF_ANGLE_OPT_HIGH,
    TAKEOFF_ANGLE_OPT_LOW,
    compute_jump_score,
    session_jump_score_stats,
)


# --- README § Jump scoring — formula helpers (oracle for assertions) -------------


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def expected_jump_quality_score(h_cm: float) -> float:
    """Linear map 8 cm → 0, 45 cm → 100; clamp outside [8, 45]."""
    if HIP_HEIGHT_MAX_CM <= HIP_HEIGHT_MIN_CM:
        raise ValueError("invalid HIP height band")
    t = _clamp01((h_cm - HIP_HEIGHT_MIN_CM) / (HIP_HEIGHT_MAX_CM - HIP_HEIGHT_MIN_CM))
    return 100.0 * t


def expected_landing_one_knee(angle: float) -> float:
    """README: 100 in [130°, 155°]; −4 pt/° below 130; −5 pt/° above 155."""
    if LANDING_KNEE_OPT_LOW <= angle <= LANDING_KNEE_OPT_HIGH:
        return 100.0
    if angle < LANDING_KNEE_OPT_LOW:
        return max(0.0, 100.0 - (LANDING_KNEE_OPT_LOW - angle) * 4.0)
    return max(0.0, 100.0 - (angle - LANDING_KNEE_OPT_HIGH) * 5.0)


def expected_landing_both(left: float, right: float) -> float:
    return (expected_landing_one_knee(left) + expected_landing_one_knee(right)) / 2.0


class TestDegenerateComputeJumpScore:
    def test_empty_metrics_and_takeoff_returns_error_breakdown(self):
        out = compute_jump_score({}, {})
        assert out["score"] == 0
        assert out["score_breakdown"]["_error"] == "no scoring inputs available"

    def test_no_scoreable_channels_same_as_empty(self):
        """Missing knee/height/drift/velocity; takeoff_form needs stance or angle."""
        out = compute_jump_score({"knee_angles": {}}, {})
        assert out["score"] == 0
        assert "_error" in out["score_breakdown"]


class TestRenormalizationAndPartialTakeoffForm:
    def test_uncalibrated_session_only_landing_and_height_in_breakdown(self):
        """Only channels with data appear; weights renormalized (README Jump scoring)."""
        metrics = {
            "knee_angles": {"left": 140.0, "right": 140.0},
            "jump_height_est_cm": 26.5,
        }
        out = compute_jump_score(metrics, {})
        bd = out["score_breakdown"]
        assert set(bd.keys()) == {"landing_quality", "jump_quality"}
        lq = expected_landing_both(140.0, 140.0)
        jq = expected_jump_quality_score(26.5)
        w_l, w_j = 0.25 / 0.5, 0.25 / 0.5
        assert pytest.approx(bd["landing_quality"], abs=0.05) == round(lq, 1)
        assert pytest.approx(bd["jump_quality"], abs=0.05) == round(jq, 1)
        expected_total = w_l * lq + w_j * jq
        assert out["score"] == int(round(max(0.0, min(100.0, expected_total))))

    def test_takeoff_form_stance_only_equals_stance_subscore(self):
        """README: mean of available parts → single part is that sub-score alone."""
        metrics = {"takeoff_angle_deg": None}
        takeoff = {"stance_width_cm": 28.0}
        out = compute_jump_score(metrics, takeoff)
        assert out["score_breakdown"]["takeoff_form"] == 100.0

    def test_takeoff_form_angle_only_equals_angle_subscore(self):
        metrics = {"takeoff_angle_deg": 26.0}
        out = compute_jump_score(metrics, {})
        assert out["score_breakdown"]["takeoff_form"] == 100.0


class TestJumpQualityBoundaries:
    @pytest.mark.parametrize("h_cm", [HIP_HEIGHT_MIN_CM, HIP_HEIGHT_MAX_CM, 7.0, 50.0])
    def test_jump_quality_hinge_and_clamps(self, h_cm):
        metrics = {"jump_height_est_cm": h_cm}
        out = compute_jump_score(metrics, {})
        exp = round(expected_jump_quality_score(h_cm), 1)
        assert out["score_breakdown"]["jump_quality"] == exp


class TestLandingBoundaries:
    def test_band_edges_one_hundred_each_knee(self):
        for a in (LANDING_KNEE_OPT_LOW, LANDING_KNEE_OPT_HIGH):
            metrics = {"knee_angles": {"left": a, "right": a}}
            out = compute_jump_score(metrics, {})
            assert out["score_breakdown"]["landing_quality"] == 100.0

    @pytest.mark.parametrize("angle", [129.9, 155.1])
    def test_just_outside_band_penalty(self, angle):
        metrics = {"knee_angles": {"left": angle, "right": angle}}
        out = compute_jump_score(metrics, {})
        expected = expected_landing_both(angle, angle)
        assert out["score_breakdown"]["landing_quality"] == round(expected, 1)


class TestApproachBoundaries:
    @pytest.mark.parametrize(
        "v,expected",
        [
            (150.0, 0.0),
            (350.0, 100.0),
            (620.0, 100.0),
            (800.0, 0.0),
        ],
    )
    def test_hinge_velocities(self, v, expected):
        metrics = {}
        takeoff = {"approach_velocity_cms": v}
        out = compute_jump_score(metrics, takeoff)
        assert out["score_breakdown"]["approach_control"] == pytest.approx(expected, abs=0.05)


class TestDriftBoundaries:
    def test_zero_and_forty_cm(self):
        for mag, exp in [(0.0, 100.0), (40.0, 0.0)]:
            metrics = {"drift_cm": {"magnitude": mag}}
            out = compute_jump_score(metrics, {})
            assert out["score_breakdown"]["drift_stability"] == pytest.approx(exp, abs=0.05)


class TestTakeoffFormPiecewise:
    def test_stance_mid_and_band_edges(self):
        for w in (18.0, 38.0, 28.0):
            out = compute_jump_score({}, {"stance_width_cm": w})
            assert out["score_breakdown"]["takeoff_form"] == 100.0

    def test_angle_band_edges(self):
        for a in (TAKEOFF_ANGLE_OPT_LOW, TAKEOFF_ANGLE_OPT_HIGH):
            out = compute_jump_score({"takeoff_angle_deg": a}, {})
            assert out["score_breakdown"]["takeoff_form"] == 100.0


class TestSessionJumpScoreStatsEmpty:
    """§4.8 — empty history → all null rollups."""

    def test_empty_history_all_null(self):
        out = session_jump_score_stats([])
        assert out == {
            "avg_jump_score": None,
            "best_jump_num": None,
            "best_jump_score": None,
            "worst_jump_num": None,
            "worst_jump_score": None,
        }


class TestSessionJumpScoreStatsRollups:
    """SESSION_SUMMARY score stats — README tie-breaking and skipped rows."""

    def test_tie_best_and_worst_use_earlier_jump_num(self):
        """README: on tie for highest/lowest, earlier jump_num in file order wins."""
        history = [
            {"event": "JUMP", "jump_num": 1, "metrics": {"score": 72}},
            {"event": "JUMP", "jump_num": 2, "metrics": {"score": 72}},
        ]
        out = session_jump_score_stats(history)
        assert out["best_jump_num"] == 1
        assert out["worst_jump_num"] == 1
        assert out["best_jump_score"] == 72.0
        assert out["worst_jump_score"] == 72.0
        assert out["avg_jump_score"] == 72.0

    def test_jumps_without_score_skipped(self):
        history = [
            {"event": "JUMP", "jump_num": 1, "metrics": {}},
            {"event": "JUMP", "jump_num": 2, "metrics": {"score": 80}},
        ]
        out = session_jump_score_stats(history)
        assert out["avg_jump_score"] == 80.0
        assert out["best_jump_num"] == 2
        assert out["worst_jump_num"] == 2

    def test_non_jump_events_ignored(self):
        history = [
            {"event": "SESSION_SUMMARY", "jump_num": 0, "metrics": {"score": 99}},
            {"event": "JUMP", "jump_num": 1, "metrics": {"score": 50}},
        ]
        out = session_jump_score_stats(history)
        assert out["avg_jump_score"] == 50.0


class TestRenormalizationStability:
    """Issue #33 optional: scoring unchanged when inactive metric keys differ."""

    def test_extra_non_scoring_metric_keys_same_result(self):
        core = {
            "knee_angles": {"left": 140.0, "right": 138.0},
            "jump_height_est_cm": 35.0,
        }
        takeoff = {}
        minimal = compute_jump_score(dict(core), takeoff)
        extra = compute_jump_score(
            {**core, "air_time_sec": 0.42, "landing_knee_flexion_rate_degs": None},
            takeoff,
        )
        assert minimal == extra
