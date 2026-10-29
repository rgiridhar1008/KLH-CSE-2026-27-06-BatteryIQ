"""Compare the legacy anomaly score calculation with the corrected calculation.

The legacy calculation is reproduced here solely for before/after experiment
comparison. It does not change raw data, DDP configuration, or the corrected
production implementation.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from batteryiq.baseline import feature_series  # noqa: E402
from batteryiq.evaluation import (  # noqa: E402
    collect_window_observations,
    load_battery_files,
    load_screening_config,
)
from batteryiq.screening import extract_window_features  # noqa: E402


LEGACY_FEATURES = (
    "voltage_mean", "voltage_std", "voltage_spread", "current_mean",
    "current_std", "temperature_mean", "temperature_std", "temperature_spread",
)


def _finite_mean(values: np.ndarray) -> Optional[float]:
    finite = values[np.isfinite(values)]
    return float(np.mean(finite)) if finite.size else None


def _finite_std(values: np.ndarray) -> Optional[float]:
    finite = values[np.isfinite(values)]
    return float(np.std(finite)) if finite.size else None


def _legacy_scale(values: np.ndarray, fallback: Optional[float]) -> Optional[float]:
    finite = values[np.isfinite(values)]
    if not finite.size:
        return None
    mad = float(np.median(np.abs(finite - np.median(finite))))
    scale = 1.4826 * mad
    if not np.isfinite(scale) or scale <= 1e-12:
        scale = float(fallback or 0.0)
    return max(scale, 1e-6)


def _legacy_baseline(frame: pd.DataFrame, samples: int) -> Tuple[Dict[str, Optional[float]], Dict[str, Optional[float]]]:
    series = feature_series(frame.iloc[:samples])
    features: Dict[str, Optional[float]] = {}
    scales: Dict[str, Optional[float]] = {}
    for name in LEGACY_FEATURES:
        values = series[name]
        value = _finite_std(values) if name == "current_std" else _finite_mean(values)
        features[name] = value
        scales[name] = _legacy_scale(values, value)
    return features, scales


def _normalised(value: Optional[float], reference: Optional[float], scale: Optional[float]) -> Optional[float]:
    if value is None or reference is None or scale is None:
        return None
    if not (np.isfinite(value) and np.isfinite(reference) and np.isfinite(scale)):
        return None
    return float(abs(value - reference) / max(abs(scale), 1e-6))


def _mean_components(values: Sequence[Optional[float]]) -> Optional[float]:
    finite = [value for value in values if value is not None and np.isfinite(value)]
    return float(np.mean(finite)) if finite else None


def _legacy_score(window: pd.DataFrame, features: Mapping[str, Optional[float]], scales: Mapping[str, Optional[float]]) -> Dict[str, float]:
    values = extract_window_features(window)
    voltage = _mean_components([
        _normalised(values["V_mean"], features["voltage_mean"], scales["voltage_mean"]),
        _normalised(values["V_std"], features["voltage_std"], scales["voltage_std"]),
    ])
    voltage_spread = _normalised(values["V_spread"], features["voltage_spread"], scales["voltage_spread"])
    current = _mean_components([
        _normalised(values["I_mean"], features["current_mean"], scales["current_mean"]),
        _normalised(values["I_std"], features["current_std"], scales["current_std"]),
        _normalised(values["I_rate"], features["current_std"], scales["current_std"]),
    ])
    temperature = _mean_components([
        _normalised(values["T_mean"], features["temperature_mean"], scales["temperature_mean"]),
        _normalised(values["T_std"], features["temperature_std"], scales["temperature_std"]),
        _normalised(values["T_spread"], features["temperature_spread"], scales["temperature_spread"]),
        _normalised(values["T_rate"], features["temperature_spread"], scales["temperature_spread"]),
    ])
    components = {
        "legacy_deviation_voltage": voltage,
        "legacy_deviation_voltage_spread": voltage_spread,
        "legacy_deviation_current": current,
        "legacy_deviation_temperature": temperature,
    }
    available = [value for value in components.values() if value is not None]
    components["legacy_anomaly_score"] = float(np.mean(available)) if available else 0.0
    return components


def _summary(values: pd.Series) -> Dict[str, float]:
    return {
        "maximum": float(values.max()),
        "mean": float(values.mean()),
        "median": float(values.median()),
        "p95": float(np.percentile(values, 95)),
        "p99": float(np.percentile(values, 99)),
    }


def _component_summary(frame: pd.DataFrame, columns: Sequence[str]) -> Dict[str, Dict[str, float]]:
    return {
        column: _summary(frame[column].astype(float))
        for column in columns
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare legacy and corrected anomaly-score behavior.")
    parser.add_argument("--input-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data" / "processed" / "batteryiq_results")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "batteryiq.yaml")
    parser.add_argument("--max-files", type=int, default=10)
    return parser


def main() -> int:
    args = _parser().parse_args()
    config = load_screening_config(args.config)
    records = load_battery_files(args.input_dir, args.max_files)
    observations, _ = collect_window_observations(records, config)

    legacy_baselines = {}
    for key in {(record.identity.directory, record.identity.battery_id) for record in records}:
        group = sorted(
            [record for record in records if (record.identity.directory, record.identity.battery_id) == key],
            key=lambda record: record.identity.sample_start,
        )
        combined = pd.concat([record.frame for record in group], ignore_index=True)
        legacy_baselines[key] = _legacy_baseline(combined, config.baseline_samples)

    rows = []
    for observation in observations:
        key = (observation.directory, observation.battery_id)
        old_features, old_scales = legacy_baselines[key]
        row = {
            "source_file": observation.source_file,
            "battery_id": observation.battery_id,
            "start_sample": observation.start_sample,
            "end_sample": observation.end_sample,
            **_legacy_score(observation.window, old_features, old_scales),
            "corrected_anomaly_score": observation.screening.anomaly_score,
            **{f"corrected_deviation_{name}": value for name, value in observation.screening.deviations.items()},
        }
        rows.append(row)
    comparison = pd.DataFrame(rows)
    old_columns = ["legacy_deviation_voltage", "legacy_deviation_voltage_spread", "legacy_deviation_current", "legacy_deviation_temperature"]
    new_columns = ["corrected_deviation_voltage", "corrected_deviation_current", "corrected_deviation_temperature"]
    report = {
        "files_processed": len(records),
        "windows": len(comparison),
        "legacy_score": _summary(comparison["legacy_anomaly_score"]),
        "corrected_score": _summary(comparison["corrected_anomaly_score"]),
        "legacy_component_distributions": _component_summary(comparison, old_columns),
        "corrected_component_distributions": _component_summary(comparison, new_columns),
        "interpretation": "This is a numerical comparison only. Lower scores do not by themselves establish better detection.",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "anomaly_score_before_after_windows.csv"
    json_path = args.output_dir / "anomaly_score_before_after_comparison.json"
    comparison.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Before/after anomaly-score comparison (no detection-quality claim):")
    print(pd.DataFrame([report["legacy_score"], report["corrected_score"]], index=["legacy", "corrected"]).to_string())
    print("\nComponent distributions:")
    print(json.dumps({"legacy": report["legacy_component_distributions"], "corrected": report["corrected_component_distributions"]}, indent=2))
    print(f"Window comparison: {csv_path}")
    print(f"Summary: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
