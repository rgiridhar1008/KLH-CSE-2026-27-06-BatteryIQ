from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ddp_downsampling.config import PipelineConfig  # noqa: E402
from ddp_downsampling.ddp_metrics import compute_vdd_cdd  # noqa: E402
from ddp_downsampling.downsampling import (  # noqa: E402
    build_index_sets,
    compute_grades,
    downsample_dataframe,
)


def test_vdd_cdd_calculation_is_finite():
    voltage = np.array([[3.70, 3.70], [3.71, 3.69], [3.72, 3.68]], dtype=float)
    current = np.array([1.0, 2.0, 3.0], dtype=float)
    vdd, cdd = compute_vdd_cdd(
        voltage,
        current,
        alpha=0.3,
        beta=2.0,
        use_square_wave_vdd=False,
        voltage_square_wave_amplitude=0.0,
        use_square_wave_cdd=False,
        current_square_wave_amplitude=0.0,
        current_range_floor=2.0,
    )
    assert np.isfinite(vdd) and vdd >= 0.0
    assert np.isfinite(cdd) and cdd >= 0.0


def test_strict_high_mid_low_grades(monkeypatch):
    import ddp_downsampling.downsampling as module

    values = iter([(1.0, 1.0), (0.0, 0.0), (0.5, 0.0)])
    monkeypatch.setattr(module, "compute_vdd_cdd", lambda *args, **kwargs: next(values))
    cfg = PipelineConfig(
        ddp_window_size=1,
        ddp_step_size=1,
        vdd_thres=0.5,
        cdd_thres=0.5,
        enable_square_wave_vdd=False,
        enable_square_wave_cdd=False,
    )
    _, _, grades = compute_grades(
        np.ones((3, 2), dtype=float), np.ones(3, dtype=float), cfg
    )
    assert grades.tolist() == [2, 0, 1]


def test_sampling_intervals_are_one_five_and_thirty_rows():
    cfg = PipelineConfig(
        sampling_interval_high_s=1.0,
        sampling_interval_mid_s=5.0,
        sampling_interval_low_s=30.0,
        overlap_mode="exclusive",
    )
    base = np.array([2, 2] + [1] * 10 + [0] * 30)
    result = build_index_sets(base, base, dt=1.0, cfg=cfg)
    assert result["high"].tolist() == [0, 1]
    assert result["mid"].tolist() == [2, 7]
    assert result["low"].tolist() == [12]


def test_alias_loader_preserves_temperature_and_output_invariants():
    frame = pd.DataFrame(
        {
            "time": np.arange(8, dtype=float),
            "current": np.ones(8),
            "voltage_1": np.linspace(3.70, 3.71, 8),
            "voltage_2": np.linspace(3.70, 3.69, 8),
            "temperature": np.full(8, 25.0),
        }
    )
    cfg = PipelineConfig(
        min_length_high=1,
        min_length_mid=1,
        min_length_low=1,
        vdd_thres=-1.0,
        cdd_thres=-1.0,
        enable_square_wave_vdd=False,
        enable_square_wave_cdd=False,
    )
    result = downsample_dataframe(frame, cfg)
    output = result.downsampled_df
    assert {"orig_idx", "orig_row", "temperature", "vdd", "cdd"}.issubset(output.columns)
    assert output["orig_idx"].is_unique
    assert len(output) <= len(frame)
