"""Shared evaluation helpers for baseline-relative event-trigger experiments."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from pathlib import Path
from statistics import mean, median
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import yaml

from ddp_downsampling.config import PipelineConfig
from ddp_downsampling.downsampling import downsample_dataframe, find_csv_files, normalise_input_columns

from .baseline import BatteryBaseline, BatteryFileIdentity, build_battery_baselines, parse_battery_identity
from .screening import AnomalyScreeningConfig, ScreeningWindowResult, apply_event_policy, evaluate_window


@dataclass(frozen=True)
class LoadedBatteryFile:
    source_file: str
    frame: pd.DataFrame
    identity: BatteryFileIdentity


@dataclass(frozen=True)
class WindowObservation:
    source_file: str
    directory: str
    battery_id: str
    cell_range: str
    start_sample: int
    end_sample: int
    global_start: int
    window: pd.DataFrame
    baseline: BatteryBaseline
    screening: ScreeningWindowResult


def load_screening_config(path: Path) -> AnomalyScreeningConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    baseline = raw.get("baseline", {}) or {}
    screening = raw.get("screening", {}) or {}
    weights = screening.get("weights", {}) or {}
    return AnomalyScreeningConfig(
        baseline_samples=max(1, int(baseline.get("samples", raw.get("baseline_samples", 1000)))),
        baseline_strategy=str(baseline.get("strategy", "initial")),
        window_size=max(1, int(raw.get("window_size", screening.get("window_size", 50)))),
        window_step=max(1, int(raw.get("window_step", screening.get("window_step", 50)))),
        trigger_threshold=float(screening.get("trigger_threshold", screening.get("score_threshold", 1.0))),
        min_trigger_windows=max(1, int(screening.get("min_trigger_windows", 1))),
        cooldown_windows=max(0, int(screening.get("cooldown_windows", 0))),
        weights={str(key): float(value) for key, value in (weights or {"voltage": 1.0, "current": 1.0, "temperature": 1.0}).items()},
    )


def load_battery_files(input_dir: Path, max_files: Optional[int] = None) -> List[LoadedBatteryFile]:
    files = find_csv_files(input_dir)
    if max_files is not None:
        files = files[: max(0, int(max_files))]
    loaded: List[LoadedBatteryFile] = []
    for source in files:
        relative = source.relative_to(input_dir).as_posix()
        frame = normalise_input_columns(pd.read_csv(source))
        loaded.append(
            LoadedBatteryFile(
                source_file=relative,
                frame=frame,
                identity=parse_battery_identity(relative, len(frame)),
            )
        )
    return loaded


def collect_window_observations(
    records: Sequence[LoadedBatteryFile],
    config: AnomalyScreeningConfig,
) -> Tuple[List[WindowObservation], Dict[Tuple[str, str], BatteryBaseline]]:
    """Build baselines and collect post-baseline screening windows."""
    baseline_records = [(record.source_file, record.frame) for record in records]
    baselines = build_battery_baselines(
        baseline_records, config.baseline_samples, strategy=config.baseline_strategy
    )
    grouped: Dict[Tuple[str, str], List[LoadedBatteryFile]] = {}
    for record in records:
        key = (record.identity.directory, record.identity.battery_id)
        grouped.setdefault(key, []).append(record)

    observations: List[WindowObservation] = []
    size = max(1, int(config.window_size))
    step = max(1, int(config.window_step))
    for key, group in grouped.items():
        group.sort(key=lambda record: record.identity.sample_start)
        baseline = baselines[key]
        group_offset = 0
        for record in group:
            frame = record.frame
            for local_start in range(0, len(frame), step):
                local_end = min(len(frame), local_start + size)
                if local_end <= local_start:
                    continue
                global_start = group_offset + local_start
                # Do not evaluate windows that contain the baseline prefix.
                # With the default 1,000/50 settings this boundary is exact;
                # skipping a crossing window avoids baseline leakage for other
                # configurations too.
                if global_start < baseline.used_samples:
                    continue
                window = frame.iloc[local_start:local_end].copy()
                result = evaluate_window(window, baseline, config)
                observations.append(
                    WindowObservation(
                        source_file=record.source_file,
                        directory=record.identity.directory,
                        battery_id=record.identity.battery_id,
                        cell_range=record.identity.cell_range,
                        start_sample=record.identity.sample_start + local_start,
                        end_sample=record.identity.sample_start + local_end - 1,
                        global_start=global_start,
                        window=window,
                        baseline=baseline,
                        screening=result,
                    )
                )
            group_offset += len(frame)
    observations.sort(key=lambda item: (item.directory, item.battery_id, item.global_start))
    return observations, baselines


def _ddp_result(
    observation: WindowObservation,
    ddp_config: PipelineConfig,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    ddp_input = observation.window.copy()
    ddp_input["orig_idx"] = np.arange(
        observation.start_sample,
        observation.start_sample + len(ddp_input),
        dtype=float,
    )
    result = downsample_dataframe(ddp_input, ddp_config)
    retained = result.downsampled_df.copy()
    retained.insert(0, "source_file", observation.source_file)
    retained.insert(1, "battery_id", observation.battery_id)
    retained.insert(2, "directory", observation.directory)
    retained.insert(3, "event_start_sample", observation.start_sample)
    retained.insert(4, "event_end_sample", observation.end_sample)
    retained_count = int(len(retained))
    input_count = int(len(observation.window))
    metrics = {
        "ddp_executed": True,
        "input_rows": input_count,
        "retained_rows": retained_count,
        "retention_percent": (100.0 * retained_count / input_count) if input_count else 0.0,
        "compression_ratio": (input_count / retained_count) if retained_count else None,
    }
    return retained, metrics


def _empty_ddp_metrics(input_rows: int) -> Dict[str, Any]:
    return {
        "ddp_executed": False,
        # ``input_rows`` is specifically the number passed to DDP. For a
        # skipped window no DDP input exists, so keep this value at zero.
        "input_rows": 0,
        "retained_rows": 0,
        "retention_percent": 0.0,
        "compression_ratio": None,
    }


def _base_event_row(observation: WindowObservation) -> Dict[str, Any]:
    result = observation.screening
    row: Dict[str, Any] = {
        "source_file": observation.source_file,
        "directory": observation.directory,
        "battery_id": observation.battery_id,
        "cell_range": observation.cell_range,
        "start_sample": observation.start_sample,
        "end_sample": observation.end_sample,
        "anomaly_score": result.anomaly_score,
        "suspicious": result.suspicious,
        "triggered_features": "|".join(result.triggered_features),
        "baseline_reference": observation.baseline.reference,
        "baseline_samples_used": observation.baseline.used_samples,
        "ai_status": "AI_SKIPPED",
        "event_reason": "below_threshold",
    }
    row.update(result.feature_values)
    row.update({f"deviation_{key}": value for key, value in result.deviations.items()})
    row.update(_empty_ddp_metrics(len(observation.window)))
    return row


def evaluate_observations(
    observations: Sequence[WindowObservation],
    config: AnomalyScreeningConfig,
    ddp_config: Optional[PipelineConfig] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any], pd.DataFrame]:
    """Apply persistence/cooldown, run DDP for trigger events, and summarize."""
    ddp_config = ddp_config or PipelineConfig()
    grouped: Dict[Tuple[str, str], List[WindowObservation]] = {}
    for observation in observations:
        grouped.setdefault((observation.directory, observation.battery_id), []).append(observation)

    rows: List[Dict[str, Any]] = []
    retained_frames: List[pd.DataFrame] = []
    for key, group in grouped.items():
        group.sort(key=lambda item: item.global_start)
        decisions = apply_event_policy(
            [item.screening for item in group],
            min_trigger_windows=config.min_trigger_windows,
            cooldown_windows=config.cooldown_windows,
        )
        for observation, trigger in zip(group, decisions):
            row = _base_event_row(observation)
            if trigger:
                retained, metrics = _ddp_result(observation, ddp_config)
                retained_frames.append(retained)
                row.update(metrics)
                row["ai_status"] = "AI_REQUIRED"
                row["event_reason"] = "threshold_persistence"
            elif observation.screening.suspicious:
                row["event_reason"] = "cooldown_or_persistence"
            rows.append(row)

    event_frame = pd.DataFrame(rows)
    if not event_frame.empty:
        event_frame = event_frame.sort_values(["directory", "battery_id", "start_sample"]).reset_index(drop=True)
    retained_frame = pd.concat(retained_frames, ignore_index=True) if retained_frames else pd.DataFrame()
    if not retained_frame.empty and {"source_file", "orig_idx"}.issubset(retained_frame.columns):
        retained_frame = retained_frame.drop_duplicates(subset=["source_file", "orig_idx"], keep="first")
    summary = summarize_event_frame(event_frame, retained_frame)
    per_battery = summarize_per_battery(event_frame, retained_frame)
    return event_frame, retained_frame, summary, per_battery


def summarize_event_frame(event_frame: pd.DataFrame, retained_frame: pd.DataFrame) -> Dict[str, Any]:
    total = int(len(event_frame))
    triggered = int((event_frame["ai_status"] == "AI_REQUIRED").sum()) if total else 0
    skipped = total - triggered
    raw_anomalous = int(event_frame["suspicious"].sum()) if total else 0
    input_rows = int(event_frame["input_rows"].sum()) if total and "input_rows" in event_frame else 0
    retained_rows = int(len(retained_frame))
    scores = event_frame["anomaly_score"].astype(float).tolist() if total else []
    return {
        "total_windows": total,
        "triggered_windows": triggered,
        "skipped_windows": skipped,
        "raw_anomalous_windows": raw_anomalous,
        "inference_avoidance_percent": (100.0 * skipped / total) if total else 0.0,
        "mean_anomaly_score": float(mean(scores)) if scores else 0.0,
        "median_anomaly_score": float(median(scores)) if scores else 0.0,
        "maximum_anomaly_score": float(max(scores)) if scores else 0.0,
        "ddp_input_rows": input_rows,
        "ddp_retained_rows": retained_rows,
        "ddp_retention_percent": (100.0 * retained_rows / input_rows) if input_rows else 0.0,
        "ddp_compression_ratio": (input_rows / retained_rows) if retained_rows else None,
    }


def summarize_per_battery(event_frame: pd.DataFrame, retained_frame: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "directory", "battery_id", "total_windows", "triggered_windows", "skipped_windows",
        "inference_avoidance_percent", "mean_anomaly_score", "median_anomaly_score",
        "maximum_anomaly_score", "baseline_samples_used", "ddp_input_rows", "ddp_retained_rows",
        "ddp_retention_percent", "ddp_compression_ratio",
    ]
    if event_frame.empty:
        return pd.DataFrame(columns=columns)
    rows: List[Dict[str, Any]] = []
    for (directory, battery_id), group in event_frame.groupby(["directory", "battery_id"], sort=True):
        retained = retained_frame[
            (retained_frame.get("directory", pd.Series(dtype=object)) == directory)
            & (retained_frame.get("battery_id", pd.Series(dtype=object)) == battery_id)
        ] if not retained_frame.empty else pd.DataFrame()
        total = len(group); triggered = int((group["ai_status"] == "AI_REQUIRED").sum())
        input_rows = int(group["input_rows"].sum()); retained_rows = len(retained)
        rows.append({
            "directory": directory,
            "battery_id": battery_id,
            "total_windows": int(total),
            "triggered_windows": triggered,
            "skipped_windows": int(total - triggered),
            "inference_avoidance_percent": 100.0 * (total - triggered) / total if total else 0.0,
            "mean_anomaly_score": float(group["anomaly_score"].mean()),
            "median_anomaly_score": float(group["anomaly_score"].median()),
            "maximum_anomaly_score": float(group["anomaly_score"].max()),
            "baseline_samples_used": int(group["baseline_samples_used"].iloc[0]),
            "ddp_input_rows": input_rows,
            "ddp_retained_rows": int(retained_rows),
            "ddp_retention_percent": 100.0 * retained_rows / input_rows if input_rows else 0.0,
            "ddp_compression_ratio": input_rows / retained_rows if retained_rows else None,
        })
    return pd.DataFrame(rows, columns=columns)


def threshold_sensitivity(
    observations: Sequence[WindowObservation],
    config: AnomalyScreeningConfig,
    thresholds: Sequence[float],
) -> pd.DataFrame:
    """Calculate exploratory threshold counts without selecting a winner."""
    rows: List[Dict[str, Any]] = []
    grouped: Dict[Tuple[str, str], List[WindowObservation]] = {}
    for observation in observations:
        grouped.setdefault((observation.directory, observation.battery_id), []).append(observation)
    for threshold in thresholds:
        total = 0; triggered = 0
        for group in grouped.values():
            group.sort(key=lambda item: item.global_start)
            adjusted = [replace(item.screening, suspicious=item.screening.anomaly_score >= float(threshold)) for item in group]
            decisions = apply_event_policy(adjusted, config.min_trigger_windows, config.cooldown_windows)
            total += len(decisions); triggered += sum(decisions)
        skipped = total - triggered
        rows.append({
            "threshold": float(threshold),
            "total_windows": int(total),
            "triggered_windows": int(triggered),
            "skipped_windows": int(skipped),
            "inference_avoidance_percent": 100.0 * skipped / total if total else 0.0,
        })
    return pd.DataFrame(rows)
