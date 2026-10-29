"""Per-file BatteryIQ screening -> triggered DDP -> diagnosis -> policy flow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np
import pandas as pd

from .config import PipelineConfig
from .diagnosis import diagnose
from .downsampling import downsample_dataframe, normalise_input_columns
from .event_trigger import ScreeningConfig, iter_screening_windows
from .risk_policy import apply_risk_policy


RESULT_COLUMNS = [
    "source_file",
    "battery_id",
    "cell_range",
    "start_sample",
    "end_sample",
    "screening_score",
    "suspicious",
    "triggered_features",
    "ai_status",
    "fault_type",
    "severity",
    "confidence",
    "risk_state",
    "risk_action",
]


@dataclass(frozen=True)
class BatteryIdentity:
    source_file: str
    battery_id: str
    cell_range: str
    file_start: int
    file_end: int


def parse_battery_identity(source_file: str, row_count: int) -> BatteryIdentity:
    name = Path(source_file).name
    match = re.search(r"battery_(?P<battery>[^_]+)_cells_(?P<cells>[^_]+)_t_(?P<start>\d+)-(?P<end>\d+)", name, re.IGNORECASE)
    if match:
        return BatteryIdentity(
            source_file=str(source_file),
            battery_id=str(match.group("battery")),
            cell_range=str(match.group("cells")),
            file_start=int(match.group("start")),
            file_end=int(match.group("end")),
        )
    return BatteryIdentity(
        source_file=str(source_file),
        battery_id="unknown",
        cell_range="unknown",
        file_start=0,
        file_end=max(0, int(row_count) - 1),
    )


def _window_metadata(identity: BatteryIdentity, start: int, end: int) -> Dict[str, Any]:
    return {
        "source_file": identity.source_file,
        "battery_id": identity.battery_id,
        "cell_range": identity.cell_range,
        "start_sample": identity.file_start + int(start),
        "end_sample": identity.file_start + int(end),
    }


def _ddp_for_window(
    window: pd.DataFrame,
    identity: BatteryIdentity,
    start: int,
    ddp_config: PipelineConfig,
) -> pd.DataFrame:
    """Run the unchanged DDP implementation on one suspicious window."""
    ddp_input = window.copy()
    # BatteryData has no calendar timestamp. Use the filename-derived absolute
    # sequential sample index and let the existing DDP implementation consume
    # its canonical ``orig_idx`` column.
    ddp_input = ddp_input.drop(columns=["time_s"], errors="ignore")
    ddp_input["orig_idx"] = np.arange(
        identity.file_start + int(start),
        identity.file_start + int(start) + len(ddp_input),
        dtype=float,
    )
    result = downsample_dataframe(ddp_input, ddp_config)
    retained = result.downsampled_df.copy()
    retained.insert(0, "source_file", identity.source_file)
    return retained


def process_battery_dataframe(
    frame: pd.DataFrame,
    source_file: str,
    ddp_config: PipelineConfig,
    screening_config: ScreeningConfig,
    risk_policy: Mapping[str, Any],
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Process one CSV independently and return window rows, retained rows, summary."""
    canonical = normalise_input_columns(frame)
    identity = parse_battery_identity(source_file, len(canonical))
    window_rows: List[Dict[str, Any]] = []
    retained_frames: List[pd.DataFrame] = []
    ai_invocations = 0
    suspicious_windows = 0

    for start, end, window, screening in iter_screening_windows(canonical, screening_config):
        metadata = _window_metadata(identity, start, end)
        suspicious = bool(screening.suspicious)
        if suspicious:
            suspicious_windows += 1
            ai_invocations += 1
            diagnosis = diagnose(window)
            policy_result = apply_risk_policy(
                diagnosis.get("fault_type"),
                diagnosis.get("severity"),
                diagnosis.get("confidence"),
                risk_policy,
            )
            retained_frames.append(_ddp_for_window(window, identity, start, ddp_config))
            row = {
                **metadata,
                "screening_score": screening.screening_score,
                "suspicious": True,
                "triggered_features": "|".join(screening.triggered_features),
                "ai_status": "AI_REQUIRED",
                "fault_type": diagnosis.get("fault_type"),
                "severity": diagnosis.get("severity"),
                "confidence": diagnosis.get("confidence"),
                **policy_result,
            }
        else:
            policy_result = apply_risk_policy(None, None, None, risk_policy)
            row = {
                **metadata,
                "screening_score": screening.screening_score,
                "suspicious": False,
                "triggered_features": "",
                "ai_status": "AI_SKIPPED",
                "fault_type": None,
                "severity": None,
                "confidence": None,
                **policy_result,
            }
        window_rows.append(row)

    window_frame = pd.DataFrame(window_rows, columns=RESULT_COLUMNS)
    if retained_frames:
        retained = pd.concat(retained_frames, ignore_index=True)
        if {"source_file", "orig_idx"}.issubset(retained.columns):
            retained = retained.drop_duplicates(subset=["source_file", "orig_idx"], keep="first")
    else:
        retained = pd.DataFrame()

    total_windows = len(window_rows)
    ai_skipped = total_windows - ai_invocations
    summary = {
        "source_file": identity.source_file,
        "input_rows": int(len(canonical)),
        "total_windows": int(total_windows),
        "suspicious_windows": int(suspicious_windows),
        "ai_invocations": int(ai_invocations),
        "ai_skipped": int(ai_skipped),
        "inference_avoidance_percent": (100.0 * ai_skipped / total_windows) if total_windows else 0.0,
        "retained_ddp_rows": int(len(retained)),
        "retention_percentage": (100.0 * len(retained) / len(canonical)) if len(canonical) else 0.0,
    }
    return window_frame, retained, summary

