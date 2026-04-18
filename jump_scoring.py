"""
Composite jump quality score (0–100) from per-jump metrics.

Thresholds and weights are documented in README.md — Output Format — Jump scoring.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# --- Reference bands (see README) -------------------------------------------------

# Landing: soft knee bend at contact (degrees per knee)
LANDING_KNEE_OPT_LOW = 130.0
LANDING_KNEE_OPT_HIGH = 155.0

# Height: linear map from HIP_HEIGHT_MIN_CM (0 pts) to HIP_HEIGHT_MAX_CM (100 pts)
HIP_HEIGHT_MIN_CM = 8.0
HIP_HEIGHT_MAX_CM = 45.0

# Drift: magnitude in cm; score hits 0 at this magnitude
DRIFT_MAGNITUDE_ZERO_SCORE_CM = 40.0

# Approach velocity (cm/s): plateau band, then linear taper to zero outside
APPROACH_PLATEAU_LOW = 350.0
APPROACH_PLATEAU_HIGH = 620.0
APPROACH_HARD_LOW = 150.0
APPROACH_HARD_HIGH = 800.0

# Stance width at takeoff (cm)
STANCE_OPT_LOW = 18.0
STANCE_OPT_HIGH = 38.0

# Takeoff trajectory angle (degrees); null without calibration-derived velocity
TAKEOFF_ANGLE_OPT_LOW = 12.0
TAKEOFF_ANGLE_OPT_HIGH = 40.0

# Base channel weights (redistributed when a channel has no data)
_BASE_WEIGHTS: Dict[str, float] = {
    "landing_quality": 0.25,
    "jump_quality": 0.25,
    "drift_stability": 0.20,
    "approach_control": 0.15,
    "takeoff_form": 0.15,
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _score_landing_knees(knee: Dict[str, Any]) -> Optional[float]:
    try:
        left = float(knee["left"])
        right = float(knee["right"])
    except (KeyError, TypeError, ValueError):
        return None

    def one(angle: float) -> float:
        if LANDING_KNEE_OPT_LOW <= angle <= LANDING_KNEE_OPT_HIGH:
            return 100.0
        if angle < LANDING_KNEE_OPT_LOW:
            return max(0.0, 100.0 - (LANDING_KNEE_OPT_LOW - angle) * 4.0)
        return max(0.0, 100.0 - (angle - LANDING_KNEE_OPT_HIGH) * 5.0)

    return (one(left) + one(right)) / 2.0


def _score_jump_height_cm(h_cm: Optional[float]) -> Optional[float]:
    if h_cm is None:
        return None
    try:
        h = float(h_cm)
    except (TypeError, ValueError):
        return None
    if HIP_HEIGHT_MAX_CM <= HIP_HEIGHT_MIN_CM:
        return None
    t = _clamp01((h - HIP_HEIGHT_MIN_CM) / (HIP_HEIGHT_MAX_CM - HIP_HEIGHT_MIN_CM))
    return 100.0 * t


def _score_drift(metrics: Dict[str, Any]) -> Optional[float]:
    drift = metrics.get("drift_cm")
    if not drift or not isinstance(drift, dict):
        return None
    try:
        mag = float(drift["magnitude"])
    except (KeyError, TypeError, ValueError):
        return None
    if DRIFT_MAGNITUDE_ZERO_SCORE_CM <= 0:
        return None
    return max(0.0, 100.0 - (mag / DRIFT_MAGNITUDE_ZERO_SCORE_CM) * 100.0)


def _score_approach_velocity(v: Optional[float]) -> Optional[float]:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if APPROACH_PLATEAU_LOW <= x <= APPROACH_PLATEAU_HIGH:
        return 100.0
    if x < APPROACH_PLATEAU_LOW:
        if x <= APPROACH_HARD_LOW:
            return 0.0
        return 100.0 * (x - APPROACH_HARD_LOW) / (APPROACH_PLATEAU_LOW - APPROACH_HARD_LOW)
    if x >= APPROACH_PLATEAU_HIGH:
        if x >= APPROACH_HARD_HIGH:
            return 0.0
        return 100.0 * (APPROACH_HARD_HIGH - x) / (APPROACH_HARD_HIGH - APPROACH_PLATEAU_HIGH)
    return 100.0


def _score_stance_width_cm(w: Optional[float]) -> Optional[float]:
    if w is None:
        return None
    try:
        s = float(w)
    except (TypeError, ValueError):
        return None
    mid = 0.5 * (STANCE_OPT_LOW + STANCE_OPT_HIGH)
    half = 0.5 * (STANCE_OPT_HIGH - STANCE_OPT_LOW)
    if half <= 0:
        return None
    dist = abs(s - mid)
    if dist <= half:
        return 100.0
    extra = dist - half
    return max(0.0, 100.0 - extra * 8.0)


def _score_takeoff_angle_deg(a: Optional[float]) -> Optional[float]:
    if a is None:
        return None
    try:
        ang = float(a)
    except (TypeError, ValueError):
        return None
    if TAKEOFF_ANGLE_OPT_LOW <= ang <= TAKEOFF_ANGLE_OPT_HIGH:
        return 100.0
    if ang < TAKEOFF_ANGLE_OPT_LOW:
        return max(0.0, 100.0 - (TAKEOFF_ANGLE_OPT_LOW - ang) * 5.0)
    return max(0.0, 100.0 - (ang - TAKEOFF_ANGLE_OPT_HIGH) * 4.0)


def _score_takeoff_form(metrics: Dict[str, Any], takeoff: Dict[str, Any]) -> Optional[float]:
    stance = _score_stance_width_cm(takeoff.get("stance_width_cm"))
    angle = _score_takeoff_angle_deg(metrics.get("takeoff_angle_deg"))
    parts = [p for p in (stance, angle) if p is not None]
    if not parts:
        return None
    return sum(parts) / len(parts)


def _normalize_weights(active: List[str]) -> Dict[str, float]:
    raw = {k: _BASE_WEIGHTS[k] for k in active if k in _BASE_WEIGHTS}
    s = sum(raw.values())
    if s <= 0:
        return {}
    return {k: v / s for k, v in raw.items()}


def compute_jump_score(metrics: Dict[str, Any], takeoff: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return score (0–100 int) and per-channel sub-scores (0–100 floats).

    Channels without required inputs are omitted; remaining weights are renormalized.
    """
    channels: Dict[str, Optional[float]] = {
        "landing_quality": _score_landing_knees(metrics.get("knee_angles") or {}),
        "jump_quality": _score_jump_height_cm(metrics.get("jump_height_est_cm")),
        "drift_stability": _score_drift(metrics),
        "approach_control": _score_approach_velocity(takeoff.get("approach_velocity_cms")),
        "takeoff_form": _score_takeoff_form(metrics, takeoff),
    }

    active = [name for name, val in channels.items() if val is not None]
    if not active:
        return {
            "score": 0,
            "score_breakdown": {"_error": "no scoring inputs available"},
        }

    weights = _normalize_weights(active)
    total = 0.0
    breakdown: Dict[str, Any] = {}
    for name in active:
        w = weights.get(name, 0.0)
        sub = float(channels[name])
        breakdown[name] = round(sub, 1)
        total += w * sub

    score = int(round(max(0.0, min(100.0, total))))
    return {
        "score": score,
        "score_breakdown": breakdown,
    }


def session_jump_score_stats(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate score fields for SESSION_SUMMARY from completed JUMP entries."""
    pairs: List[Tuple[int, float]] = []
    for entry in history:
        if entry.get("event") != "JUMP":
            continue
        m = entry.get("metrics") or {}
        if "score" not in m:
            continue
        try:
            sc = float(m["score"])
            num = int(entry["jump_num"])
        except (KeyError, TypeError, ValueError):
            continue
        pairs.append((num, sc))

    if not pairs:
        return {
            "avg_jump_score": None,
            "best_jump_num": None,
            "best_jump_score": None,
            "worst_jump_num": None,
            "worst_jump_score": None,
        }

    avg = sum(s for _, s in pairs) / len(pairs)
    best_num, best_s = max(pairs, key=lambda x: x[1])
    worst_num, worst_s = min(pairs, key=lambda x: x[1])
    return {
        "avg_jump_score": round(avg, 1),
        "best_jump_num": best_num,
        "best_jump_score": round(best_s, 1),
        "worst_jump_num": worst_num,
        "worst_jump_score": round(worst_s, 1),
    }
