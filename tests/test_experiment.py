from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import batteryiq.experiment as experiment  # noqa: E402
from batteryiq.baseline import construct_baseline  # noqa: E402
from batteryiq.evaluation import WindowObservation  # noqa: E402
from batteryiq.experiment import StatisticalBaselineDiagnosticModel, run_ai_mode_comparison  # noqa: E402
from batteryiq.screening import AnomalyScreeningConfig, evaluate_window  # noqa: E402


def _frame(n: int = 200, temperature: bool = True) -> pd.DataFrame:
    result = {f"vol_{number}": np.full(n, 3.30) for number in range(1, 9)}
    result["cur"] = np.zeros(n)
    if temperature:
        result.update({f"temp_{number}": np.full(n, 30.0) for number in range(1, 9)})
    return pd.DataFrame(result)


def _observation(window: pd.DataFrame, baseline, start: int, config: AnomalyScreeningConfig) -> WindowObservation:
    return WindowObservation(
        source_file="d/battery_01_cells_001-008_t_00000-00199.csv",
        directory="d",
        battery_id="01",
        cell_range="001-008",
        start_sample=start,
        end_sample=start + len(window) - 1,
        global_start=start,
        window=window,
        baseline=baseline,
        screening=evaluate_window(window, baseline, config),
    )


def _observations() -> tuple[list[WindowObservation], AnomalyScreeningConfig]:
    frame = _frame()
    config = AnomalyScreeningConfig(trigger_threshold=1.0)
    baseline = construct_baseline(frame.iloc[:100], "d", "01", 100)
    normal = _observation(frame.iloc[100:150].copy(), baseline, 100, config)
    altered = frame.iloc[150:200].copy()
    altered.loc[:, "vol_1"] += 0.2
    triggered = _observation(altered, baseline, 150, config)
    assert normal.screening.suspicious is False
    assert triggered.screening.suspicious is True
    return [normal, triggered], config


@pytest.fixture
def lightweight_ddp(monkeypatch):
    calls: list[int] = []

    def fake_downsample(frame, config):
        calls.append(len(frame))
        return SimpleNamespace(downsampled_df=frame.iloc[:2].copy())

    monkeypatch.setattr(experiment, "downsample_dataframe", fake_downsample)
    return calls


def test_always_on_calls_level2_for_every_window_and_shared_windows(lightweight_ddp):
    observations, config = _observations()
    frame, _ = run_ai_mode_comparison(observations, config)
    always = frame[frame["mode"] == "always_on"]
    event = frame[frame["mode"] == "event_triggered"]
    assert always["ai_called"].all()
    assert len(always) == len(observations)
    assert set(zip(always.source_file, always.start_sample)) == set(zip(event.source_file, event.start_sample))


def test_event_triggered_calls_only_suspicious_and_skips_ddp(lightweight_ddp):
    observations, config = _observations()
    frame, summary = run_ai_mode_comparison(observations, config)
    event = frame[frame["mode"] == "event_triggered"].sort_values("start_sample")
    assert event["ai_called"].tolist() == [False, True]
    assert event["ddp_called"].tolist() == [False, True]
    assert summary["event_triggered_ddp_calls"] == 1
    # Always-on executes DDP twice; event-triggered executes it only once.
    assert len(lightweight_ddp) == 3


def test_invocation_avoidance_and_level2_coverage_metrics(lightweight_ddp):
    observations, config = _observations()
    _, summary = run_ai_mode_comparison(observations, config)
    assert summary["always_on_ai_calls"] == 2
    assert summary["event_triggered_ai_calls"] == 1
    assert summary["ai_calls_avoided"] == 1
    assert summary["inference_avoidance_percent"] == pytest.approx(50.0)
    assert summary["level2_anomaly_windows"] == 1
    assert summary["level2_anomalies_reached_by_event_trigger"] == 1
    assert summary["level2_anomaly_coverage_percent"] == pytest.approx(100.0)


def test_statistical_level2_result_is_deterministic_and_not_a_fault_label():
    observations, _ = _observations()
    model = StatisticalBaselineDiagnosticModel()
    first = model.diagnose(observations[1].window, {"baseline": observations[1].baseline})
    second = model.diagnose(observations[1].window, {"baseline": observations[1].baseline})
    assert first == second
    assert first.model_name == "STATISTICAL BASELINE DIAGNOSTIC MODEL"
    assert first.severity in {"NONE", "LOW", "MEDIUM", "HIGH"}


def test_missing_temperature_is_supported_by_level2_and_experiment(lightweight_ddp):
    frame = _frame(150, temperature=False)
    config = AnomalyScreeningConfig(trigger_threshold=1.0)
    baseline = construct_baseline(frame.iloc[:100], "d", "01", 100)
    observation = _observation(frame.iloc[100:150].copy(), baseline, 100, config)
    result = StatisticalBaselineDiagnosticModel().diagnose(observation.window, {"baseline": baseline})
    comparison, summary = run_ai_mode_comparison([observation], config)
    assert np.isfinite(result.anomaly_score)
    assert summary["total_windows"] == 1
    assert comparison["level2_anomaly_score"].notna().sum() == 1
