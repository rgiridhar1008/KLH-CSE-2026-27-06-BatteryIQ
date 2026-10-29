from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from batteryiq.baseline import BatteryBaseline, build_battery_baselines, construct_baseline  # noqa: E402
from batteryiq.screening import (  # noqa: E402
    AnomalyScreeningConfig,
    ScreeningWindowResult,
    apply_event_policy,
    evaluate_window,
    extract_window_features,
)


def make_frame(n: int = 200, include_temperature: bool = True) -> pd.DataFrame:
    frame = {f"vol_{i}": np.full(n, 3.30) for i in range(1, 9)}
    frame["cur"] = np.zeros(n)
    if include_temperature:
        frame.update({f"temp_{i}": np.full(n, 30.0) for i in range(1, 9)})
    return pd.DataFrame(frame)


def test_baseline_construction_uses_earliest_configured_samples():
    baseline = construct_baseline(make_frame(25), "real_world_02-03", "01", baseline_samples=100)
    assert baseline.requested_samples == 100
    assert baseline.used_samples == 25
    assert set(baseline.features) == {
        "voltage_mean", "voltage_std", "voltage_spread", "current_mean", "current_std",
        "voltage_rate", "current_rate", "temperature_mean", "temperature_std",
        "temperature_spread", "temperature_rate",
    }


def test_baseline_is_battery_specific():
    first = make_frame(20)
    second = make_frame(20)
    second.loc[:, "vol_1"] = 3.80
    baselines = build_battery_baselines(
        [
            ("real_world_02-03/battery_01_cells_001-008_t_00000-00019.csv", first),
            ("real_world_02-03/battery_02_cells_009-016_t_00000-00019.csv", second),
        ],
        baseline_samples=20,
    )
    assert len(baselines) == 2
    assert baselines[("real_world_02-03", "01")].features["voltage_mean"] != baselines[("real_world_02-03", "02")].features["voltage_mean"]


def test_normal_synthetic_window_has_low_score():
    frame = make_frame()
    baseline = construct_baseline(frame.iloc[:100], "d", "1", 100)
    result = evaluate_window(frame.iloc[100:150], baseline, AnomalyScreeningConfig(trigger_threshold=1.0))
    assert result.anomaly_score < 1e-12
    assert result.suspicious is False


def test_injected_voltage_deviation_increases_score():
    frame = make_frame()
    baseline = construct_baseline(frame.iloc[:100], "d", "1", 100)
    normal = evaluate_window(frame.iloc[100:150], baseline, AnomalyScreeningConfig())
    altered = frame.iloc[100:150].copy()
    altered.loc[:, "vol_1"] += 0.2
    anomalous = evaluate_window(altered, baseline, AnomalyScreeningConfig())
    assert anomalous.anomaly_score > normal.anomaly_score
    assert anomalous.suspicious is True


def test_injected_current_deviation_increases_score():
    frame = make_frame()
    baseline = construct_baseline(frame.iloc[:100], "d", "1", 100)
    altered = frame.iloc[100:150].copy()
    altered.loc[:, "cur"] = 50.0
    result = evaluate_window(altered, baseline, AnomalyScreeningConfig())
    assert result.deviations["current"] is not None
    assert result.suspicious is True


def test_injected_temperature_deviation_increases_score():
    frame = make_frame()
    baseline = construct_baseline(frame.iloc[:100], "d", "1", 100)
    altered = frame.iloc[100:150].copy()
    altered.loc[:, "temp_1"] = 40.0
    result = evaluate_window(altered, baseline, AnomalyScreeningConfig())
    assert result.deviations["temperature"] is not None
    assert result.suspicious is True


def test_trigger_threshold_is_configurable():
    frame = make_frame()
    baseline = construct_baseline(frame.iloc[:100], "d", "1", 100)
    altered = frame.iloc[100:150].copy()
    altered.loc[:, "vol_1"] += 0.2
    assert evaluate_window(altered, baseline, AnomalyScreeningConfig(trigger_threshold=1e9)).suspicious is False
    assert evaluate_window(altered, baseline, AnomalyScreeningConfig(trigger_threshold=1.0)).suspicious is True


def test_cooldown_suppresses_adjacent_trigger_windows():
    result = ScreeningWindowResult(2.0, True, ("voltage",), {}, {"voltage": 2.0}, ("voltage",))
    decisions = apply_event_policy([result, result, result], min_trigger_windows=1, cooldown_windows=1)
    assert decisions == [True, False, True]


def test_missing_temperature_does_not_crash_or_create_temperature_component():
    frame = make_frame(include_temperature=False)
    baseline = construct_baseline(frame.iloc[:100], "d", "1", 100)
    result = evaluate_window(frame.iloc[100:150], baseline, AnomalyScreeningConfig())
    assert result.deviations["temperature"] is None
    assert "temperature" not in result.available_components


def test_zero_variation_baseline_remains_finite_and_stable():
    frame = make_frame()
    baseline = construct_baseline(frame.iloc[:100], "d", "1", 100)
    result = evaluate_window(frame.iloc[100:150], baseline, AnomalyScreeningConfig())
    assert baseline.scales["voltage_spread"] == 1e-6
    assert np.isfinite(result.anomaly_score)
    assert result.anomaly_score == 0.0


def test_quantized_voltage_spread_uses_observed_variation_not_tiny_mad():
    frame = make_frame(150)
    spreads = np.concatenate((np.full(45, 0.0030), np.full(50, 0.0030001), np.full(5, 0.0050)))
    frame.loc[:99, "vol_2"] = 3.30 + spreads
    baseline = construct_baseline(frame.iloc[:100], "d", "1", 100)
    conventional_std = float(np.std(spreads))
    assert baseline.scales["voltage_spread"] == pytest.approx(conventional_std)

    altered = frame.iloc[100:150].copy()
    altered.loc[:, "vol_2"] = 3.33
    result = evaluate_window(altered, baseline, AnomalyScreeningConfig())
    assert result.deviations["voltage"] is not None
    assert result.deviations["voltage"] < 100.0
    assert np.isfinite(result.anomaly_score)


def test_rate_features_use_matching_baseline_references_and_are_deterministic():
    frame = make_frame(4)
    frame.loc[:, "vol_1"] = [3.30, 3.50, 3.30, 3.50]
    frame.loc[:, "cur"] = [0.0, 2.0, 0.0, 2.0]
    for column in [f"temp_{index}" for index in range(1, 9)]:
        frame.loc[:, column] = [30.0, 32.0, 30.0, 32.0]
    values = extract_window_features(frame)
    features = {
        "voltage_mean": values["V_mean"], "voltage_std": values["V_std"],
        "voltage_spread": values["V_spread"], "voltage_rate": 0.0,
        "current_mean": values["I_mean"], "current_std": values["I_std"],
        "current_rate": 0.0, "temperature_mean": values["T_mean"],
        "temperature_std": values["T_std"], "temperature_spread": values["T_spread"] + 5.0,
        "temperature_rate": 0.0,
    }
    baseline = BatteryBaseline("d", "1", 4, 4, features, {name: 1.0 for name in features})
    first = evaluate_window(frame, baseline, AnomalyScreeningConfig())
    second = evaluate_window(frame, baseline, AnomalyScreeningConfig())

    assert first.deviations["voltage"] == pytest.approx(values["V_rate"] / 4.0)
    assert first.deviations["current"] == pytest.approx(values["I_rate"] / 3.0)
    assert first.deviations["temperature"] == pytest.approx((5.0 + values["T_rate"]) / 4.0)
    assert first.anomaly_score == second.anomaly_score
