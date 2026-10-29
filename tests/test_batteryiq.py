from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ddp_downsampling.battery_pipeline import RESULT_COLUMNS, process_battery_dataframe  # noqa: E402
from ddp_downsampling.config import PipelineConfig  # noqa: E402
from ddp_downsampling.event_trigger import ScreeningConfig, screen_window  # noqa: E402
from ddp_downsampling.risk_policy import apply_risk_policy, load_risk_policy  # noqa: E402


THRESHOLDS = {
    "voltage_spread": 0.05,
    "voltage_spread_change": 0.02,
    "current_change": 25.0,
    "current_rate": 25.0,
    "temperature_spread": 5.0,
    "temperature_change": 3.0,
    "temperature_rate": 3.0,
    "voltage_rate": 0.02,
}
SCREENING = ScreeningConfig(window_size=50, window_step=50, thresholds=THRESHOLDS)


def make_frame(n: int = 100, include_temperature: bool = True) -> pd.DataFrame:
    frame = {f"vol_{i}": np.full(n, 3.7) for i in range(1, 9)}
    frame["cur"] = np.zeros(n)
    if include_temperature:
        frame.update({f"temp_{i}": np.full(n, 25.0) for i in range(1, 9)})
    return pd.DataFrame(frame)


def test_normal_synthetic_data_skips_ai():
    result = screen_window(make_frame(50), SCREENING)
    assert result.suspicious is False


def test_voltage_imbalance_triggers_screening():
    frame = make_frame(50)
    frame.loc[10:20, "vol_1"] += 0.20
    result = screen_window(frame, SCREENING)
    assert result.suspicious is True
    assert "voltage_spread" in result.triggered_features


def test_current_anomaly_triggers_screening():
    frame = make_frame(50)
    frame.loc[20, "cur"] = 100.0
    result = screen_window(frame, SCREENING)
    assert result.suspicious is True
    assert "current_change" in result.triggered_features


def test_temperature_anomaly_triggers_screening():
    frame = make_frame(50)
    frame.loc[20:30, "temp_1"] = 40.0
    result = screen_window(frame, SCREENING)
    assert result.suspicious is True
    assert "temperature_spread" in result.triggered_features


def test_triggered_event_requires_placeholder_ai():
    frame = make_frame(50)
    frame.loc[10:20, "vol_1"] += 0.20
    policy = load_risk_policy(Path("config/risk_policy.yaml"))
    results, retained, summary = process_battery_dataframe(
        frame, "battery_01_cells_001-008_t_00000-00049.csv", PipelineConfig(), SCREENING, policy
    )
    assert results.iloc[0]["ai_status"] == "AI_REQUIRED"
    assert results.iloc[0]["fault_type"] == "PLACEHOLDER_ANOMALY"
    assert results.iloc[0]["risk_state"] == "WARNING"
    assert summary["ai_invocations"] == 1
    assert not retained.empty


def test_normal_event_skips_ai():
    policy = load_risk_policy(Path("config/risk_policy.yaml"))
    results, retained, summary = process_battery_dataframe(
        make_frame(50), "battery_01_cells_001-008_t_00000-00049.csv", PipelineConfig(), SCREENING, policy
    )
    assert results.iloc[0]["ai_status"] == "AI_SKIPPED"
    assert pd.isna(results.iloc[0]["fault_type"])
    assert retained.empty
    assert summary["inference_avoidance_percent"] == 100.0


def test_risk_policy_returns_supported_state():
    policy = load_risk_policy(Path("config/risk_policy.yaml"))
    output = apply_risk_policy("PLACEHOLDER_ANOMALY", "MEDIUM", 0.5, policy)
    assert output["risk_state"] in policy["states"]
    assert output["risk_action"]


def test_missing_soc_is_valid():
    result = screen_window(make_frame(50), SCREENING)
    assert result.suspicious is False


def test_missing_temperature_columns_do_not_crash():
    result = screen_window(make_frame(50, include_temperature=False), SCREENING)
    assert result.suspicious is False


def test_pipeline_output_contains_required_columns():
    frame = make_frame(50)
    frame.loc[10:20, "vol_1"] += 0.20
    policy = load_risk_policy(Path("config/risk_policy.yaml"))
    results, _, _ = process_battery_dataframe(
        frame, "battery_01_cells_001-008_t_00000-00049.csv", PipelineConfig(), SCREENING, policy
    )
    assert list(results.columns) == RESULT_COLUMNS
    assert {"source_file", "battery_id", "cell_range", "start_sample", "end_sample"}.issubset(results.columns)
