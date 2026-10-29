"""Run the always-on versus event-triggered Level-2 diagnostic experiment."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from batteryiq.evaluation import collect_window_observations, load_battery_files, load_screening_config  # noqa: E402
from batteryiq.experiment import (  # noqa: E402
    ComputationalCostConfig,
    StatisticalBaselineDiagnosticModel,
    StatisticalDiagnosticConfig,
    run_ai_mode_comparison,
)
from batteryiq.diagnosis import LocalGGUFDiagnosticModel  # noqa: E402


DEFAULT_QWEN_MODEL_PATH = REPO_ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare always-on and event-triggered Level-2 invocations.")
    parser.add_argument("--input-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data" / "processed" / "batteryiq_results")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "batteryiq.yaml")
    parser.add_argument("--max-files", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=None, help="Level-1 trigger threshold for this comparison run.")
    parser.add_argument("--cost-per-ai-call", type=float, default=1.0)
    parser.add_argument("--cost-per-ddp-row", type=float, default=0.001)
    parser.add_argument("--diagnostic-anomaly-threshold", type=float, default=1.0)
    parser.add_argument("--diagnostic-medium-threshold", type=float, default=3.0)
    parser.add_argument("--diagnostic-high-threshold", type=float, default=6.0)
    parser.add_argument("--diagnostic-model", choices=("statistical", "qwen"), default="statistical")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_QWEN_MODEL_PATH, help="Local GGUF path; used only with --diagnostic-model qwen.")
    parser.add_argument("--qwen-max-tokens", type=int, default=256)
    parser.add_argument(
        "--max-qwen-windows",
        type=int,
        default=None,
        help="Deterministically limit Qwen to this many sorted evaluation windows; ignored for statistical mode.",
    )
    return parser


def _save_plot(path: Path, title: str) -> None:
    plt.title(title)
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()


def _plots(frame, summary: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    modes = ["Always-on", "Event-triggered"]

    plt.figure(figsize=(6, 4))
    plt.bar(modes, [summary["always_on_ai_calls"], summary["event_triggered_ai_calls"]], color=["#3973ac", "#4c956c"])
    plt.ylabel("Level-2 diagnostic calls")
    _save_plot(directory / "ai_mode_ai_calls.png", "Level-2 diagnostic invocations")

    plt.figure(figsize=(5, 4))
    plt.bar(["Event-triggered"], [summary["inference_avoidance_percent"]], color="#4c956c")
    plt.ylim(0, 100)
    plt.ylabel("Inference avoidance (%)")
    _save_plot(directory / "ai_mode_inference_avoidance.png", "Inference avoidance")

    plt.figure(figsize=(7, 4))
    always = frame[frame["mode"] == "always_on"]["level2_anomaly_score"].dropna()
    event = frame[frame["mode"] == "event_triggered"]["level2_anomaly_score"].dropna()
    if len(always):
        bins = np.linspace(float(always.min()), float(always.max()), 31) if float(always.min()) != float(always.max()) else 30
        plt.hist(always, bins=bins, alpha=0.55, label="Always-on", color="#3973ac")
        plt.hist(event, bins=bins, alpha=0.55, label="Event-triggered calls", color="#4c956c")
    else:
        plt.text(0.5, 0.5, "No numeric Level-2 score for selected model", ha="center", va="center")
    plt.xlabel("Level-2 statistical anomaly score (when available)")
    plt.ylabel("Windows")
    plt.legend()
    _save_plot(directory / "ai_mode_level2_score_distribution.png", "Level-2 score distribution")

    plt.figure(figsize=(6, 4))
    plt.bar(["Level-2 anomaly windows", "Reached by event trigger"], [summary["level2_anomaly_windows"], summary["level2_anomalies_reached_by_event_trigger"]], color=["#3973ac", "#4c956c"])
    plt.ylabel("Windows")
    _save_plot(directory / "ai_mode_level2_coverage.png", "Level-2 anomaly coverage (not fault recall)")

    plt.figure(figsize=(6, 4))
    plt.bar(modes, [summary["always_on_ddp_calls"], summary["event_triggered_ddp_calls"]], color=["#3973ac", "#4c956c"])
    plt.ylabel("DDP executions")
    _save_plot(directory / "ai_mode_ddp_calls.png", "DDP execution comparison")


def _window_identity(frame) -> list[dict[str, Any]]:
    """Return stable, serializable evaluation identities for subset auditability."""
    columns = ["source_file", "directory", "battery_id", "start_sample", "end_sample"]
    return frame[columns].drop_duplicates().sort_values(columns).to_dict(orient="records")


def _mode_metrics(frame) -> dict[str, dict[str, Any]]:
    """Summarize measured calls, DDP work, JSON status, and severity by mode."""
    result: dict[str, dict[str, Any]] = {}
    for mode, group in frame.groupby("mode", sort=True):
        called = group[group["ai_called"]].copy()
        durations = called["diagnostic_inference_seconds"].dropna()
        severity = called["diagnostic_anomaly_severity"].fillna("")
        parsed = called["diagnostic_json_parsed"].dropna()
        input_rows = int(group["ddp_input_rows"].sum())
        retained_rows = int(group["ddp_retained_rows"].sum())
        result[str(mode)] = {
            "total_evaluation_windows": int(len(group)),
            "level2_ai_calls": int(group["ai_called"].sum()),
            "ddp_calls": int(group["ddp_called"].sum()),
            "ddp_input_rows": input_rows,
            "ddp_retained_rows": retained_rows,
            "ddp_retention_percent": 100.0 * retained_rows / input_rows if input_rows else 0.0,
            "low_count": int((severity == "LOW").sum()),
            "medium_count": int((severity == "MEDIUM").sum()),
            "high_count": int((severity == "HIGH").sum()),
            "json_parsing_successes": int((parsed == True).sum()),  # noqa: E712
            "json_parsing_failures": int((parsed == False).sum()),  # noqa: E712
            "total_inference_seconds": float(durations.sum()) if not durations.empty else None,
            "average_inference_seconds": float(durations.mean()) if not durations.empty else None,
            "minimum_inference_seconds": float(durations.min()) if not durations.empty else None,
            "maximum_inference_seconds": float(durations.max()) if not durations.empty else None,
        }
    return result


def _write_qwen_subset_report(path: Path, summary: dict[str, Any]) -> None:
    """Write a scope-explicit report; it is not a full-dataset evaluation."""
    modes = summary["mode_metrics"]
    always = modes["always_on"]
    event = modes["event_triggered"]
    scope = summary["qwen_subset"]
    path.write_text(
        "# 100-window Qwen subset experiment\n\n"
        "This is a deterministic 100-window Qwen subset experiment, not a 760-window full-dataset evaluation. "
        "BatteryData has no explicit fault labels; LOW/MEDIUM/HIGH are diagnostic anomaly severity only.\n\n"
        "## Scope\n\n"
        f"- Available 10-file evaluation windows: {scope['available_evaluation_windows']}\n"
        f"- Qwen subset windows: {scope['selected_qwen_windows']}\n"
        f"- Unique selected identities: {scope['unique_selected_window_identities']}\n"
        f"- Same identities in both Qwen modes: {scope['same_window_identities_in_both_modes']}\n"
        f"- Model load time: {summary['diagnostic_timing']['model_load_seconds']:.3f} seconds\n\n"
        "## Measured mode results\n\n"
        "| Mode | AI calls | DDP calls | DDP retention | Total inference | Average inference | JSON success/failure | LOW/MEDIUM/HIGH |\n"
        "|---|---:|---:|---:|---:|---:|---:|---:|\n"
        f"| Qwen Always-On | {always['level2_ai_calls']} | {always['ddp_calls']} | {always['ddp_retention_percent']:.4f}% | {always['total_inference_seconds']:.3f} s | {always['average_inference_seconds']:.3f} s | {always['json_parsing_successes']}/{always['json_parsing_failures']} | {always['low_count']}/{always['medium_count']}/{always['high_count']} |\n"
        f"| Qwen Event-Triggered | {event['level2_ai_calls']} | {event['ddp_calls']} | {event['ddp_retention_percent']:.4f}% | {event['total_inference_seconds']:.3f} s | {event['average_inference_seconds']:.3f} s | {event['json_parsing_successes']}/{event['json_parsing_failures']} | {event['low_count']}/{event['medium_count']}/{event['high_count']} |\n\n"
        f"Calls avoided by event-triggered mode: {summary['ai_calls_avoided']} ({summary['inference_avoidance_percent']:.2f}%).\n",
        encoding="utf-8",
    )


def main() -> int:
    args = _parser().parse_args()
    config = load_screening_config(args.config)
    if args.threshold is not None:
        config = replace(config, trigger_threshold=float(args.threshold))
    records = load_battery_files(args.input_dir, args.max_files)
    observations, _ = collect_window_observations(records, config)
    available_windows = len(observations)
    subset_requested = args.max_qwen_windows
    if args.diagnostic_model == "qwen" and subset_requested is not None:
        if subset_requested <= 0:
            raise ValueError("--max-qwen-windows must be positive.")
        if subset_requested > available_windows:
            raise ValueError(f"Requested {subset_requested} Qwen windows, but only {available_windows} are available.")
        observations = observations[:subset_requested]
    if args.diagnostic_model == "statistical":
        diagnostic_config = StatisticalDiagnosticConfig(
            anomaly_threshold=args.diagnostic_anomaly_threshold,
            medium_threshold=args.diagnostic_medium_threshold,
            high_threshold=args.diagnostic_high_threshold,
        )
        diagnostic_model = StatisticalBaselineDiagnosticModel(diagnostic_config)
    else:
        diagnostic_config = None
        # The GGUF is loaded only in this explicit branch.
        diagnostic_model = LocalGGUFDiagnosticModel(args.model_path, max_tokens=args.qwen_max_tokens)
    frame, summary = run_ai_mode_comparison(
        observations,
        config,
        diagnostic_model=diagnostic_model,
        cost_config=ComputationalCostConfig(args.cost_per_ai_call, args.cost_per_ddp_row),
    )
    summary["level2_model"] = diagnostic_model.model_name
    if diagnostic_config is not None:
        summary["level2_score_bands"] = {
            "anomaly_threshold": diagnostic_config.anomaly_threshold,
            "medium_threshold": diagnostic_config.medium_threshold,
            "high_threshold": diagnostic_config.high_threshold,
            "severity_label": "diagnostic anomaly severity",
        }
    else:
        summary["level2_output_schema"] = {"anomaly_level": "LOW|MEDIUM|HIGH", "reason": "...", "evidence": ["..."]}
        summary["interpretation"] = "Qwen output is descriptive baseline-relative diagnostic anomaly interpretation, not fault recall or physical severity."
        identities = _window_identity(frame)
        always_identities = _window_identity(frame[frame["mode"] == "always_on"])
        event_identities = _window_identity(frame[frame["mode"] == "event_triggered"])
        summary["qwen_subset"] = {
            "label": f"{len(identities)}-window Qwen subset experiment" if subset_requested is not None else "Qwen full evaluation-window experiment",
            "available_evaluation_windows": available_windows,
            "selected_qwen_windows": len(identities),
            "unique_selected_window_identities": len(identities),
            "same_window_identities_in_both_modes": always_identities == event_identities,
            "selected_window_identities": identities,
        }
        summary["mode_metrics"] = _mode_metrics(frame)
        frame["experiment_scope"] = summary["qwen_subset"]["label"]
        frame["available_evaluation_windows"] = available_windows
        frame["selected_qwen_windows"] = len(identities)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.output_dir / "ai_mode_comparison.csv"
    json_path = args.output_dir / "ai_mode_comparison.json"
    frame.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _plots(frame, summary, args.output_dir / "plots")
    if args.diagnostic_model == "qwen" and subset_requested is not None:
        _write_qwen_subset_report(args.output_dir / "QWEN_SUBSET_EXPERIMENT_REPORT.md", summary)

    print(f"Total windows: {summary['total_windows']}")
    print(f"Always-on AI calls: {summary['always_on_ai_calls']}")
    print(f"Event-triggered AI calls: {summary['event_triggered_ai_calls']}")
    print(f"AI calls avoided: {summary['ai_calls_avoided']}")
    print(f"Inference avoidance: {summary['inference_avoidance_percent']:.2f}%")
    print(f"Level-2 anomaly coverage: {summary['level2_anomaly_coverage_percent']:.2f}%")
    print(f"DDP calls (always/event): {summary['always_on_ddp_calls']}/{summary['event_triggered_ddp_calls']}")
    print(f"Event-triggered DDP retention: {summary['event_triggered_ddp_retention_percent']:.4f}%")
    print(f"Estimated relative cost (always/event): {summary['always_on_estimated_cost']:.6f}/{summary['event_triggered_estimated_cost']:.6f}")
    timing = summary["diagnostic_timing"]
    print(f"Model load time: {timing['model_load_seconds']}")
    print(f"Model calls: {timing['number_of_model_calls']}")
    print(f"Total inference time: {timing['total_inference_seconds']:.3f} seconds")
    print(f"Results: {csv_path}")
    print(f"Summary: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
