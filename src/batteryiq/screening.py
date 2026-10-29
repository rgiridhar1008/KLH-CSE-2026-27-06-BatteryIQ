"""Baseline-relative Level-1 anomaly screening.

Scores in this module are transparent engineering measurements for exploratory
experiments. They are not a validated scientific anomaly metric and are not
fault labels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .baseline import BatteryBaseline, feature_series


DEFAULT_WEIGHTS = {
    "voltage": 1.0,
    "current": 1.0,
    "temperature": 1.0,
}


@dataclass(frozen=True)
class AnomalyScreeningConfig:
    baseline_samples: int = 1000
    baseline_strategy: str = "initial"
    window_size: int = 50
    window_step: int = 50
    trigger_threshold: float = 1.0
    min_trigger_windows: int = 1
    cooldown_windows: int = 0
    weights: Mapping[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))


@dataclass(frozen=True)
class ScreeningWindowResult:
    anomaly_score: float
    suspicious: bool
    triggered_features: Tuple[str, ...]
    feature_values: Mapping[str, Optional[float]]
    deviations: Mapping[str, Optional[float]]
    available_components: Tuple[str, ...]


def _finite_mean(values: np.ndarray) -> Optional[float]:
    finite = values[np.isfinite(values)]
    return float(np.mean(finite)) if finite.size else None


def _finite_std(values: np.ndarray) -> Optional[float]:
    finite = values[np.isfinite(values)]
    return float(np.std(finite)) if finite.size else None


def _baseline_scale(baseline: BatteryBaseline, name: str) -> Optional[float]:
    scale = baseline.scales.get(name)
    if scale is None or not np.isfinite(scale) or scale <= 1e-12:
        return None
    return float(scale)


def _normalised_deviation(
    value: Optional[float],
    reference: Optional[float],
    scale: Optional[float],
) -> Optional[float]:
    if value is None or reference is None or scale is None:
        return None
    if not (np.isfinite(value) and np.isfinite(reference) and np.isfinite(scale)):
        return None
    difference = abs(value - reference)
    # Equivalent summaries can differ by a few floating-point ulps because
    # their means are accumulated over different window lengths. Treat that
    # round-off as zero rather than manufacturing an anomaly on a constant
    # baseline with a deliberately small numerical floor.
    roundoff = 4.0 * np.finfo(float).eps * max(1.0, abs(value), abs(reference))
    if difference <= roundoff:
        return 0.0
    return float(difference / abs(scale))


def extract_window_features(window: pd.DataFrame) -> Dict[str, Optional[float]]:
    """Extract the transparent scalar features used by the baseline score."""
    series = feature_series(window)
    features: Dict[str, Optional[float]] = {
        "V_mean": _finite_mean(series["voltage_mean"]),
        "V_std": _finite_mean(series["voltage_std"]),
        "V_spread": _finite_mean(series["voltage_spread"]),
        "V_rate": _finite_mean(series["voltage_rate"]),
        "I_mean": _finite_mean(series["current_mean"]),
        "I_std": _finite_std(series["current_mean"]),
        "I_rate": _finite_mean(series["current_rate"]),
        "T_mean": _finite_mean(series["temperature_mean"]),
        "T_std": _finite_mean(series["temperature_std"]),
        "T_spread": _finite_mean(series["temperature_spread"]),
        "T_rate": _finite_mean(series["temperature_rate"]),
    }
    return features


def _component_deviation(
    values: Sequence[Optional[float]],
    refs: Sequence[Optional[float]],
    scales: Sequence[Optional[float]],
) -> Optional[float]:
    deviations = [
        _normalised_deviation(value, reference, scale)
        for value, reference, scale in zip(values, refs, scales)
    ]
    finite = [value for value in deviations if value is not None and np.isfinite(value)]
    return float(np.mean(finite)) if finite else None


def evaluate_window(
    window: pd.DataFrame,
    baseline: BatteryBaseline,
    config: AnomalyScreeningConfig,
) -> ScreeningWindowResult:
    """Score one window relative to one battery-specific baseline."""
    values = extract_window_features(window)
    refs = baseline.features
    deviations: Dict[str, Optional[float]] = {
        "voltage": _component_deviation(
            [values["V_mean"], values["V_std"], values["V_spread"], values["V_rate"]],
            [refs.get("voltage_mean"), refs.get("voltage_std"), refs.get("voltage_spread"), refs.get("voltage_rate")],
            [_baseline_scale(baseline, "voltage_mean"), _baseline_scale(baseline, "voltage_std"), _baseline_scale(baseline, "voltage_spread"), _baseline_scale(baseline, "voltage_rate")],
        ),
        "current": _component_deviation(
            [values["I_mean"], values["I_std"], values["I_rate"]],
            [refs.get("current_mean"), refs.get("current_std"), refs.get("current_rate")],
            [_baseline_scale(baseline, "current_mean"), _baseline_scale(baseline, "current_std"), _baseline_scale(baseline, "current_rate")],
        ),
        "temperature": _component_deviation(
            [values["T_mean"], values["T_std"], values["T_spread"], values["T_rate"]],
            [refs.get("temperature_mean"), refs.get("temperature_std"), refs.get("temperature_spread"), refs.get("temperature_rate")],
            [_baseline_scale(baseline, "temperature_mean"), _baseline_scale(baseline, "temperature_std"), _baseline_scale(baseline, "temperature_spread"), _baseline_scale(baseline, "temperature_rate")],
        ),
    }

    weighted = []
    for component, deviation in deviations.items():
        weight = float(config.weights.get(component, 0.0))
        if deviation is not None and weight > 0.0:
            weighted.append((weight, deviation))
    if weighted:
        anomaly_score = float(sum(weight * value for weight, value in weighted) / sum(weight for weight, _ in weighted))
    else:
        anomaly_score = 0.0

    triggered = tuple(
        component
        for component, deviation in deviations.items()
        if deviation is not None and deviation >= 1.0
    )
    return ScreeningWindowResult(
        anomaly_score=anomaly_score,
        suspicious=bool(anomaly_score >= float(config.trigger_threshold)),
        triggered_features=triggered,
        feature_values=values,
        deviations=deviations,
        available_components=tuple(component for component, value in deviations.items() if value is not None),
    )


def apply_event_policy(
    screening_results: Iterable[ScreeningWindowResult],
    min_trigger_windows: int = 1,
    cooldown_windows: int = 0,
) -> List[bool]:
    """Return AI-trigger decisions after persistence and cooldown handling."""
    minimum = max(1, int(min_trigger_windows))
    cooldown = max(0, int(cooldown_windows))
    consecutive = 0
    remaining = 0
    decisions: List[bool] = []
    for result in screening_results:
        if result.suspicious:
            consecutive += 1
        else:
            consecutive = 0

        allowed = remaining == 0
        trigger = bool(result.suspicious and consecutive >= minimum and allowed)
        decisions.append(trigger)
        if remaining > 0:
            remaining -= 1
        if trigger:
            remaining = cooldown
    return decisions
