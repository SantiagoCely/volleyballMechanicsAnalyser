"""
§4.16 JSON contract — Phase 5 (GitHub #31).

Nullable coaching fields must round-trip as JSON `null`, never string "null",
NaN, or Infinity (README / CLAUDE.md nullable verification).
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def _walk_no_string_null(obj: object) -> None:
    """After json.loads, no nullable metric should be the literal string 'null'."""
    if isinstance(obj, dict):
        for v in obj.values():
            _walk_no_string_null(v)
    elif isinstance(obj, list):
        for x in obj:
            _walk_no_string_null(x)
    elif isinstance(obj, str):
        assert obj != "null", "nullable field must be JSON null, not the string 'null'"


# Representative fragments mirroring analyzer / jump_scoring output (README contract)


def _payload_metrics_full_nullable() -> dict:
    return {
        "air_time_sec": 0.512,
        "jump_height_est_cm": 25.0,
        "jump_height_est_inch": 9.8,
        "takeoff_angle_deg": None,
        "knee_angles": {"left": 145.0, "right": 148.0},
        "knee_symmetry_deg": 3.0,
        "min_landing_knee_angle_deg": None,
        "landing_absorption_duration_sec": None,
        "landing_knee_flexion_rate_degs": None,
        "peak_wrist_height_ratio": None,
        "arm_swing_symmetry_px": None,
        "score": 73,
        "score_breakdown": {
            "landing_quality": 100.0,
            "jump_quality": 62.0,
        },
    }


def _payload_takeoff_nullable() -> dict:
    return {
        "pos": None,
        "trunk_lean_deg": None,
    }


def _payload_session_summary_nulls() -> dict:
    return {
        "event": "SESSION_SUMMARY",
        "video": None,
        "jump_count": 0,
        "jump_height_variability_cm": None,
        "air_time_variability_sec": None,
        "avg_jump_score": None,
        "best_jump_num": None,
        "best_jump_score": None,
        "worst_jump_num": None,
        "worst_jump_score": None,
    }


def _payload_score_breakdown_degenerate() -> dict:
    return {
        "score": 0,
        "score_breakdown": {"_error": "no scoring inputs available"},
    }


def _payload_metrics_with_drift() -> dict:
    return {
        "drift_cm": {
            "forward_back": 12.3,
            "side_to_side": -4.0,
            "magnitude": 13.1,
        },
        "com_flight_drift_cm": 2.5,
        "takeoff_angle_deg": 28.4,
    }


@pytest.mark.parametrize(
    "payload",
    [
        _payload_metrics_full_nullable(),
        _payload_takeoff_nullable(),
        _payload_session_summary_nulls(),
        _payload_score_breakdown_degenerate(),
        _payload_metrics_with_drift(),
    ],
)
def test_representative_dicts_strict_json_roundtrip(payload: dict) -> None:
    """json.dumps with allow_nan=False; loads reproduces structure; no NaN/Infinity tokens."""
    raw = json.dumps(payload, allow_nan=False)
    assert "NaN" not in raw
    assert "Infinity" not in raw
    restored = json.loads(raw)
    assert restored == payload
    _walk_no_string_null(restored)


@pytest.mark.parametrize(
    "payload",
    [
        _payload_metrics_full_nullable(),
        _payload_session_summary_nulls(),
    ],
)
def test_nullable_fields_use_json_null_not_quoted_string(payload: dict) -> None:
    """Serialized JSON must use bare `null`, not '"null"' as a string value."""
    raw = json.dumps(payload, allow_nan=False)
    assert ': "null"' not in raw
    assert ": null" in raw or raw.count("null") >= 1


def test_save_logs_output_passes_strict_roundtrip(tmp_path) -> None:
    """End-to-end: JumpAnalyzer.save_logs produces strict JSON parseable with allow_nan=False."""
    from analyzer import JumpAnalyzer

    out = tmp_path / "out.json"
    a = JumpAnalyzer()
    a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
    a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
    a.analyze_frame(1, (140, 145), 400, frame_time=0.6)
    a.save_logs(str(out), video_name="contract.mov")

    text = out.read_text(encoding="utf8")
    json.loads(text)  # valid JSON
    assert "NaN" not in text
    assert "Infinity" not in text
