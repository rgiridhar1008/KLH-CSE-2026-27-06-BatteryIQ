"""Battery-specific normal baselines for BatteryIQ research experiments.

The baseline is descriptive, not a ground-truth health model. It is built from
the earliest available samples for one ``(directory, battery_id)`` group and
never mixes batteries or collection directories.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, Iterable, Mapping, MutableMapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from ddp_downsampling.downsampling import normalise_input_columns


FILENAME_RE = re.compile(
    r"battery_(?P<battery>[^_]+)_cells_(?P<cells>[^_]+)_t_"
    r"(?P<start>\d+)-(?P<end>\d+)\.csv$",
    re.IGNORECASE,
)

BASELINE_FEATURES = (
    "voltage_mean",
    "voltage_std",
    "voltage_spread",
    "voltage_rate",
    "current_mean",
    "current_std",
    "current_rate",
    "temperature_mean",
    "temperature_std",
    "temperature_spread",
    "temperature_rate",
)


@dataclass(frozen=True)
class BatteryFileIdentity:
    source_file: str
    directory: str
    battery_id: str
    cell_range: str
    sample_start: int
    sample_end: int


@dataclass(frozen=True)
class BatteryBaseline:
    directory: str
    battery_id: str
    requested_samples: int
    used_samples: int
    features: Mapping[str, Optional[float]]
    scales: Mapping[str, Optional[float]]

    @property
    def key(self) -> Tuple[str, str]:
        return self.directory, self.battery_id

    @property
    def reference(self) -> str:
        return (
            f"directory={self.directory};battery_id={self.battery_id};"
            f"samples={self.used_samples}/{self.requested_samples}"
        )

    def as_dict(self) -> Dict[str, object]:
        return {
            "directory": self.directory,
            "battery_id": self.battery_id,
            "requested_samples": self.requested_samples,
            "used_samples": self.used_samples,
            "features": dict(self.features),
            "scales": dict(self.scales),
        }


def parse_battery_identity(source_file: str, row_count: int = 0) -> BatteryFileIdentity:
    """Parse observed filename metadata without assigning physical semantics."""
    path = Path(source_file)
    match = FILENAME_RE.search(path.name)
    if match:
        values = match.groupdict()
        return BatteryFileIdentity(
            source_file=str(source_file),
            directory=path.parent.as_posix() or ".",
            battery_id=str(values["battery"]),
            cell_range=str(values["cells"]),
            sample_start=int(values["start"]),
            sample_end=int(values["end"]),
        )
    return BatteryFileIdentity(
        source_file=str(source_file),
        directory=path.parent.as_posix() or ".",
        battery_id="unknown",
        cell_range="unknown",
        sample_start=0,
        sample_end=max(0, int(row_count) - 1),
    )


def _signal_columns(frame: pd.DataFrame, prefix: str) -> Sequence[str]:
    return sorted(
        [column for column in frame.columns if str(column).lower().startswith(prefix)],
        key=lambda column: str(column).lower(),
    )


def _numeric(frame: pd.DataFrame, columns: Sequence[str]) -> np.ndarray:
    if not columns:
        return np.empty((len(frame), 0), dtype=float)
    return frame[list(columns)].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)


def _row_mean(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return np.full(values.shape[0], np.nan, dtype=float)
    with np.errstate(all="ignore"):
        return np.nanmean(values, axis=1)


def _row_std(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return np.full(values.shape[0], np.nan, dtype=float)
    with np.errstate(all="ignore"):
        return np.nanstd(values, axis=1)


def _row_spread(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return np.full(values.shape[0], np.nan, dtype=float)
    with np.errstate(all="ignore"):
        return np.nanmax(values, axis=1) - np.nanmin(values, axis=1)


def _absolute_rate_series(values: np.ndarray) -> np.ndarray:
    """Return absolute adjacent-sample changes, preserving invalid pairs as NaN."""
    if values.size < 2:
        return np.empty(0, dtype=float)
    differences = np.abs(np.diff(values))
    valid_pairs = np.isfinite(values[:-1]) & np.isfinite(values[1:])
    return np.where(valid_pairs, differences, np.nan)


def feature_series(frame: pd.DataFrame) -> Dict[str, np.ndarray]:
    """Return per-row series used to form baseline and window summaries."""
    canonical = normalise_input_columns(frame)
    voltage = _numeric(canonical, _signal_columns(canonical, "vol_"))
    temperature = _numeric(canonical, _signal_columns(canonical, "temp"))
    current = (
        pd.to_numeric(canonical["cur"], errors="coerce").to_numpy(dtype=float)
        if "cur" in canonical
        else np.full(len(canonical), np.nan, dtype=float)
    )
    voltage_mean = _row_mean(voltage)
    current_std = current
    temperature_mean = _row_mean(temperature)
    return {
        "voltage_mean": voltage_mean,
        "voltage_std": _row_std(voltage),
        "voltage_spread": _row_spread(voltage),
        "voltage_rate": _absolute_rate_series(voltage_mean),
        "current_mean": current,
        # ``current_std`` is retained as the per-sample source series so that
        # construct_baseline can calculate its temporal baseline statistic.
        "current_std": current_std,
        "current_rate": _absolute_rate_series(current),
        "temperature_mean": temperature_mean,
        "temperature_std": _row_std(temperature),
        "temperature_spread": _row_spread(temperature),
        "temperature_rate": _absolute_rate_series(temperature_mean),
    }


def _finite_mean(values: np.ndarray) -> Optional[float]:
    finite = values[np.isfinite(values)]
    return float(np.mean(finite)) if finite.size else None


def _finite_std(values: np.ndarray) -> Optional[float]:
    finite = values[np.isfinite(values)]
    return float(np.std(finite)) if finite.size else None


def _robust_scale(values: np.ndarray) -> Optional[float]:
    """Select a stable, observed-variation scale for normalized deviations.

    The scale is ``max(1.4826 * MAD, population_standard_deviation)``.  MAD
    supplies a robust estimate while the conventional standard deviation stops
    quantized features with a nonzero but microscopic MAD from receiving an
    unrealistically small denominator.  The final ``1e-6`` value is used only
    when both estimates are numerically zero, preserving finite scores for
    truly constant baselines without overriding a nonzero observed scale.
    """
    finite = values[np.isfinite(values)]
    if not finite.size:
        return None
    median = float(np.median(finite))
    mad = float(np.median(np.abs(finite - median)))
    robust_scale = 1.4826 * mad
    conventional_scale = float(np.std(finite))
    scale = max(robust_scale, conventional_scale)
    return 1e-6 if scale <= np.finfo(float).eps else scale


def construct_baseline(
    frame: pd.DataFrame,
    directory: str,
    battery_id: str,
    baseline_samples: int = 1000,
) -> BatteryBaseline:
    """Construct one descriptive baseline from the earliest rows available."""
    requested = max(1, int(baseline_samples))
    canonical = normalise_input_columns(frame)
    used = min(len(canonical), requested)
    sample = canonical.iloc[:used].copy()
    series = feature_series(sample)
    features: Dict[str, Optional[float]] = {}
    scales: Dict[str, Optional[float]] = {}
    for name in BASELINE_FEATURES:
        values = series[name]
        if name == "current_std":
            value = _finite_std(values)
        else:
            value = _finite_mean(values)
        features[name] = value
        scales[name] = _robust_scale(values)
    return BatteryBaseline(
        directory=str(directory),
        battery_id=str(battery_id),
        requested_samples=requested,
        used_samples=used,
        features=features,
        scales=scales,
    )


def build_battery_baselines(
    records: Iterable[Tuple[str, pd.DataFrame]],
    baseline_samples: int = 1000,
    strategy: str = "initial",
) -> Dict[Tuple[str, str], BatteryBaseline]:
    """Build separate baselines for every observed ``(directory, battery_id)``.

    ``records`` contains source paths and frames. Files are ordered by their
    filename sample start before concatenation, so the baseline is drawn from
    the earliest contiguous data represented in the supplied subset. ``initial``
    is the only supported strategy; rejecting other values prevents accidental
    future-data leakage while leaving an explicit configuration extension point.
    """
    if str(strategy).lower() != "initial":
        raise ValueError(f"Unsupported baseline strategy: {strategy!r}. Only 'initial' is available.")
    grouped: MutableMapping[Tuple[str, str], list[Tuple[BatteryFileIdentity, pd.DataFrame]]] = {}
    for source_file, frame in records:
        identity = parse_battery_identity(source_file, len(frame))
        key = (identity.directory, identity.battery_id)
        grouped.setdefault(key, []).append((identity, normalise_input_columns(frame)))

    baselines: Dict[Tuple[str, str], BatteryBaseline] = {}
    for key, items in grouped.items():
        items.sort(key=lambda item: item[0].sample_start)
        combined = pd.concat([item[1] for item in items], ignore_index=True)
        baselines[key] = construct_baseline(combined, key[0], key[1], baseline_samples)
    return baselines
