"""Level-1 lightweight screening and event-trigger utilities.

The screening layer is a research extension around the unchanged author-code
DDP baseline. Its thresholds are configuration values and are not claimed to
be optimal or scientifically validated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ScreeningConfig:
    window_size: int = 50
    window_step: int = 50
    thresholds: Mapping[str, float] = field(
        default_factory=lambda: {
            "voltage_spread": 0.05,
            "voltage_spread_change": 0.02,
            "current_change": 25.0,
            "current_rate": 25.0,
            "temperature_spread": 5.0,
            "temperature_change": 3.0,
            "temperature_rate": 3.0,
            "voltage_rate": 0.02,
        }
    )
    min_triggered_features: int = 1
    score_threshold: float = 1.0


@dataclass(frozen=True)
class ScreeningResult:
    screening_score: float
    suspicious: bool
    triggered_features: Tuple[str, ...]
    features: Mapping[str, float]


def _numeric_matrix(df: pd.DataFrame, columns: Sequence[str]) -> np.ndarray:
    if not columns:
        return np.empty((len(df), 0), dtype=float)
    return df[list(columns)].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)


def _max_abs_diff(values: np.ndarray) -> float:
    if values.size < 2:
        return 0.0
    diff = np.diff(values, axis=0)
    finite = np.abs(diff[np.isfinite(diff)])
    return float(finite.max()) if finite.size else 0.0


def _max_range(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    ranges = np.nanmax(values, axis=1) - np.nanmin(values, axis=1)
    finite = ranges[np.isfinite(ranges)]
    return float(finite.max()) if finite.size else 0.0


def extract_screening_features(window: pd.DataFrame) -> Dict[str, float]:
    """Extract inexpensive temporal features from one screening window.

    Missing temperature columns are valid. SOC is deliberately not expected or
    synthesized because it is absent from the BatteryData schema.
    """
    voltage_cols = sorted(
        [c for c in window.columns if str(c).lower().startswith("vol_")],
        key=lambda c: str(c).lower(),
    )
    temperature_cols = sorted(
        [c for c in window.columns if str(c).lower().startswith("temp")],
        key=lambda c: str(c).lower(),
    )
    voltage = _numeric_matrix(window, voltage_cols)
    temperature = _numeric_matrix(window, temperature_cols)
    current = pd.to_numeric(window["cur"], errors="coerce").to_numpy(dtype=float) if "cur" in window else np.empty(0)

    voltage_spreads = (
        np.nanmax(voltage, axis=1) - np.nanmin(voltage, axis=1)
        if voltage.size
        else np.empty(0)
    )
    temperature_spreads = (
        np.nanmax(temperature, axis=1) - np.nanmin(temperature, axis=1)
        if temperature.size
        else np.empty(0)
    )

    features: Dict[str, float] = {
        "voltage_spread": _max_range(voltage),
        "voltage_spread_change": _max_abs_diff(voltage_spreads.reshape(-1, 1)),
        "voltage_rate": _max_abs_diff(voltage),
        "current_change": _max_abs_diff(current.reshape(-1, 1)),
        "current_rate": _max_abs_diff(current.reshape(-1, 1)),
        "temperature_spread": _max_range(temperature),
        "temperature_spread_change": _max_abs_diff(temperature_spreads.reshape(-1, 1)),
        "temperature_change": _max_abs_diff(temperature),
        "temperature_rate": _max_abs_diff(temperature),
    }
    # Keep only the configured feature names in the final comparison, while
    # retaining all extracted values for inspection and plotting.
    return {key: (0.0 if not np.isfinite(value) else float(value)) for key, value in features.items()}


def screen_window(window: pd.DataFrame, config: ScreeningConfig) -> ScreeningResult:
    features = extract_screening_features(window)
    triggered: List[str] = []
    ratios: List[float] = []
    for name, threshold in config.thresholds.items():
        threshold_value = float(threshold)
        value = float(features.get(name, 0.0))
        if threshold_value <= 0.0:
            continue
        ratios.append(value / threshold_value)
        if value > threshold_value:
            triggered.append(name)

    score = max(ratios) if ratios else 0.0
    suspicious = len(triggered) >= max(1, int(config.min_triggered_features)) and score >= float(config.score_threshold)
    return ScreeningResult(
        screening_score=float(score),
        suspicious=bool(suspicious),
        triggered_features=tuple(triggered),
        features=features,
    )


def iter_screening_windows(
    df: pd.DataFrame, config: ScreeningConfig
) -> Iterable[Tuple[int, int, pd.DataFrame, ScreeningResult]]:
    """Yield ``(start, end, window, result)`` for each independent window."""
    size = max(1, int(config.window_size))
    step = max(1, int(config.window_step))
    for start in range(0, len(df), step):
        end = min(len(df), start + size)
        if end <= start:
            continue
        window = df.iloc[start:end].copy()
        yield start, end - 1, window, screen_window(window, config)

