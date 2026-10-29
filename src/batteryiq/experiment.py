"""Always-on versus event-triggered statistical-diagnostic experiment.

This module compares invocation and processing behavior on identical Level-1
windows.  Its Level-2 output is a deterministic statistical baseline measure,
not a fault classifier or a physical battery-fault assessment.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, Optional, Protocol, Sequence, Tuple

import numpy as np
import pandas as pd

from ddp_downsampling.config import PipelineConfig
from ddp_downsampling.downsampling import downsample_dataframe

from .baseline import BatteryBaseline
from .evaluation import WindowObservation
from .screening import AnomalyScreeningConfig, apply_event_policy, extract_window_features


WINDOW_TO_BASELINE = {
    "V_mean": "voltage_mean", "V_std": "voltage_std", "V_spread": "voltage_spread",
    "V_rate": "voltage_rate", "I_mean": "current_mean", "I_std": "current_std",
    "I_rate": "current_rate", "T_mean": "temperature_mean", "T_std": "temperature_std",
    "T_spread": "temperature_spread", "T_rate": "temperature_rate",
}


@dataclass(frozen=True)
class DiagnosticResult:
    """A Level-2 result; severity is diagnostic, not physical."""

    anomaly_detected: bool
    anomaly_score: Optional[float]
    severity: str
    confidence: Optional[float]
    model_name: str = "STATISTICAL BASELINE DIAGNOSTIC MODEL"
    reason: Optional[str] = None
    evidence: Tuple[str, ...] = ()
    raw_response: Optional[str] = None
    json_parsed: Optional[bool] = None
    json_parse_error: Optional[str] = None
    inference_seconds: Optional[float] = None


class DiagnosticModel(Protocol):
    """Replaceable Level-2 diagnostic interface for research experiments."""

    def diagnose(self, window_data: pd.DataFrame, context: Mapping[str, Any]) -> DiagnosticResult:
        """Return a deterministic diagnostic result for one analysis window."""


@dataclass(frozen=True)
class StatisticalDiagnosticConfig:
    anomaly_threshold: float = 1.0
    medium_threshold: float = 3.0
    high_threshold: float = 6.0


class StatisticalBaselineDiagnosticModel:
    """Transparent Level-2 score using matching battery-baseline features.

    The score is the unweighted mean of available absolute normalized
    deviations across the eleven window features. It is intentionally separate
    from the configurable, component-weighted Level-1 trigger score.
    """

    model_name = "STATISTICAL BASELINE DIAGNOSTIC MODEL"

    def __init__(self, config: Optional[StatisticalDiagnosticConfig] = None) -> None:
        self.config = config or StatisticalDiagnosticConfig()
        if not (0.0 <= self.config.anomaly_threshold <= self.config.medium_threshold <= self.config.high_threshold):
            raise ValueError("Diagnostic score bands must satisfy 0 <= anomaly <= medium <= high.")

    @staticmethod
    def _deviation(value: Optional[float], reference: Optional[float], scale: Optional[float]) -> Optional[float]:
        if value is None or reference is None or scale is None:
            return None
        if not (np.isfinite(value) and np.isfinite(reference) and np.isfinite(scale)) or scale <= 0.0:
            return None
        difference = abs(float(value) - float(reference))
        roundoff = 4.0 * np.finfo(float).eps * max(1.0, abs(float(value)), abs(float(reference)))
        return 0.0 if difference <= roundoff else float(difference / abs(float(scale)))

    def diagnose(self, window_data: pd.DataFrame, context: Mapping[str, Any]) -> DiagnosticResult:
        baseline = context.get("baseline")
        if not isinstance(baseline, BatteryBaseline):
            raise ValueError("StatisticalBaselineDiagnosticModel requires context['baseline'].")
        values = extract_window_features(window_data)
        deviations = [
            self._deviation(values[window_name], baseline.features.get(baseline_name), baseline.scales.get(baseline_name))
            for window_name, baseline_name in WINDOW_TO_BASELINE.items()
        ]
        available = [value for value in deviations if value is not None and np.isfinite(value)]
        score = float(np.mean(available)) if available else 0.0
        if score >= self.config.high_threshold:
            severity = "HIGH"
        elif score >= self.config.medium_threshold:
            severity = "MEDIUM"
        elif score >= self.config.anomaly_threshold:
            severity = "LOW"
        else:
            severity = "NONE"
        confidence = min(1.0, score / self.config.high_threshold) if self.config.high_threshold else 1.0
        return DiagnosticResult(
            anomaly_detected=bool(score >= self.config.anomaly_threshold),
            anomaly_score=score,
            severity=severity,
            confidence=float(confidence),
            model_name=self.model_name,
        )


@dataclass(frozen=True)
class ComputationalCostConfig:
    """Estimated relative computation costs, not hardware-energy measurements."""

    cost_per_ai_call: float = 1.0
    cost_per_ddp_row: float = 0.001


def _ddp_metrics(observation: WindowObservation, config: PipelineConfig) -> Dict[str, Any]:
    frame = observation.window.copy()
    frame["orig_idx"] = np.arange(observation.start_sample, observation.start_sample + len(frame), dtype=float)
    retained = downsample_dataframe(frame, config).downsampled_df
    input_rows = int(len(frame))
    retained_rows = int(len(retained))
    return {
        "ddp_called": True,
        "ddp_input_rows": input_rows,
        "ddp_retained_rows": retained_rows,
        "ddp_retention_percent": 100.0 * retained_rows / input_rows if input_rows else 0.0,
    }


def _skipped_ddp_metrics() -> Dict[str, Any]:
    return {"ddp_called": False, "ddp_input_rows": 0, "ddp_retained_rows": 0, "ddp_retention_percent": 0.0}


def _trigger_decisions(observations: Sequence[WindowObservation], config: AnomalyScreeningConfig) -> Dict[Tuple[str, str, int], bool]:
    grouped: Dict[Tuple[str, str], list[WindowObservation]] = {}
    for observation in observations:
        grouped.setdefault((observation.directory, observation.battery_id), []).append(observation)
    decisions: Dict[Tuple[str, str, int], bool] = {}
    for group in grouped.values():
        group.sort(key=lambda item: item.global_start)
        allowed = apply_event_policy(
            [item.screening for item in group], config.min_trigger_windows, config.cooldown_windows
        )
        for observation, decision in zip(group, allowed):
            decisions[(observation.source_file, observation.battery_id, observation.start_sample)] = decision
    return decisions


def _row_base(observation: WindowObservation, mode: str, trigger_allowed: bool) -> Dict[str, Any]:
    return {
        "mode": mode,
        "source_file": observation.source_file,
        "directory": observation.directory,
        "battery_id": observation.battery_id,
        "start_sample": observation.start_sample,
        "end_sample": observation.end_sample,
        "level1_anomaly_score": observation.screening.anomaly_score,
        "level1_suspicious": observation.screening.suspicious,
        "event_trigger_allowed": trigger_allowed,
        "ai_called": False,
        "level2_anomaly_detected": None,
        "level2_anomaly_score": None,
        "diagnostic_anomaly_severity": None,
        "diagnostic_confidence": None,
        "diagnostic_model_name": None,
        "diagnostic_reason": None,
        "diagnostic_evidence": None,
        "diagnostic_json_parsed": None,
        "diagnostic_json_parse_error": None,
        "diagnostic_inference_seconds": None,
        **_skipped_ddp_metrics(),
    }


def _add_diagnostic(row: Dict[str, Any], result: DiagnosticResult) -> None:
    row.update({"ai_called": True, "level2_anomaly_detected": result.anomaly_detected,
                "level2_anomaly_score": result.anomaly_score,
                "diagnostic_anomaly_severity": result.severity,
                "diagnostic_confidence": result.confidence,
                "diagnostic_model_name": result.model_name,
                "diagnostic_reason": result.reason,
                "diagnostic_evidence": "|".join(result.evidence) if result.evidence else None,
                "diagnostic_json_parsed": result.json_parsed,
                "diagnostic_json_parse_error": result.json_parse_error,
                "diagnostic_inference_seconds": result.inference_seconds})


def _score_summary(values: pd.Series) -> Dict[str, Optional[float]]:
    finite = pd.to_numeric(values, errors="coerce").dropna()
    if finite.empty:
        return {"mean": None, "median": None, "p95": None}
    return {"mean": float(finite.mean()), "median": float(finite.median()), "p95": float(np.percentile(finite, 95))}


def _estimated_cost(frame: pd.DataFrame, costs: ComputationalCostConfig) -> float:
    return float(costs.cost_per_ai_call * int(frame["ai_called"].sum()) + costs.cost_per_ddp_row * int(frame["ddp_input_rows"].sum()))


def _timing_summary(frame: pd.DataFrame, model: DiagnosticModel) -> Dict[str, Any]:
    """Collect model timing without imposing timing behavior on the baseline."""
    durations = pd.to_numeric(frame.get("diagnostic_inference_seconds"), errors="coerce").dropna()
    parsed = frame.get("diagnostic_json_parsed", pd.Series(dtype=object)).dropna()
    return {
        "model_load_seconds": getattr(model, "model_load_seconds", None),
        "number_of_model_calls": int(getattr(model, "model_calls", int(frame["ai_called"].sum()))),
        "total_inference_seconds": float(getattr(model, "total_inference_seconds", durations.sum())),
        "average_inference_seconds": float(durations.mean()) if not durations.empty else None,
        "json_parsing_successes": int((parsed == True).sum()),  # noqa: E712
        "json_parsing_failures": int((parsed == False).sum()),  # noqa: E712
    }


def run_ai_mode_comparison(
    observations: Sequence[WindowObservation],
    screening_config: AnomalyScreeningConfig,
    diagnostic_model: Optional[DiagnosticModel] = None,
    ddp_config: Optional[PipelineConfig] = None,
    cost_config: Optional[ComputationalCostConfig] = None,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Run both architectures on precisely the same ordered observations."""
    model = diagnostic_model or StatisticalBaselineDiagnosticModel()
    ddp = ddp_config or PipelineConfig()
    costs = cost_config or ComputationalCostConfig()
    ordered = sorted(observations, key=lambda item: (item.directory, item.battery_id, item.global_start))
    decisions = _trigger_decisions(ordered, screening_config)
    rows = []
    for observation in ordered:
        key = (observation.source_file, observation.battery_id, observation.start_sample)
        allowed = decisions[key]
        context = {"baseline": observation.baseline, "screening": observation.screening}

        always = _row_base(observation, "always_on", allowed)
        _add_diagnostic(always, model.diagnose(observation.window, context))
        always.update(_ddp_metrics(observation, ddp))
        rows.append(always)

        event = _row_base(observation, "event_triggered", allowed)
        if allowed:
            _add_diagnostic(event, model.diagnose(observation.window, context))
            event.update(_ddp_metrics(observation, ddp))
        rows.append(event)

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame, {"total_windows": 0}
    always_frame = frame[frame["mode"] == "always_on"].copy()
    event_frame = frame[frame["mode"] == "event_triggered"].copy()
    level2_anomalies = int(always_frame["level2_anomaly_detected"].fillna(False).sum())
    reached = int((event_frame["ai_called"] & event_frame["level2_anomaly_detected"].fillna(False)).sum())
    always_cost = _estimated_cost(always_frame, costs)
    event_cost = _estimated_cost(event_frame, costs)
    total = int(len(always_frame))
    event_calls = int(event_frame["ai_called"].sum())
    summary: Dict[str, Any] = {
        "total_windows": total,
        "always_on_ai_calls": int(always_frame["ai_called"].sum()),
        "event_triggered_ai_calls": event_calls,
        "ai_calls_avoided": total - event_calls,
        "inference_avoidance_percent": 100.0 * (total - event_calls) / total if total else 0.0,
        "always_on_ddp_calls": int(always_frame["ddp_called"].sum()),
        "event_triggered_ddp_calls": int(event_frame["ddp_called"].sum()),
        "ddp_calls_avoided": int(always_frame["ddp_called"].sum() - event_frame["ddp_called"].sum()),
        "total_input_rows": int(always_frame["ddp_input_rows"].sum()),
        "event_triggered_ddp_input_rows": int(event_frame["ddp_input_rows"].sum()),
        "event_triggered_ddp_retained_rows": int(event_frame["ddp_retained_rows"].sum()),
        "event_triggered_ddp_retention_percent": 100.0 * int(event_frame["ddp_retained_rows"].sum()) / int(event_frame["ddp_input_rows"].sum()) if int(event_frame["ddp_input_rows"].sum()) else 0.0,
        "always_on_level2_score": _score_summary(always_frame["level2_anomaly_score"]),
        "event_triggered_level2_score": _score_summary(event_frame["level2_anomaly_score"]),
        "level2_anomaly_windows": level2_anomalies,
        "level2_anomalies_reached_by_event_trigger": reached,
        "level2_anomaly_coverage_percent": 100.0 * reached / level2_anomalies if level2_anomalies else 0.0,
        "cost_model": {**asdict(costs), "label": "ESTIMATED RELATIVE COMPUTATIONAL COST"},
        "always_on_estimated_cost": always_cost,
        "event_triggered_estimated_cost": event_cost,
        "estimated_cost_reduction_percent": 100.0 * (always_cost - event_cost) / always_cost if always_cost else 0.0,
        "interpretation": "Level-2 anomaly coverage is statistical-detector coverage, not ground-truth fault recall.",
        "diagnostic_timing": _timing_summary(frame, model),
    }
    return frame, summary
