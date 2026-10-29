"""Evaluate baseline-relative event triggering on a limited BatteryData subset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from batteryiq.evaluation import (  # noqa: E402
    collect_window_observations,
    evaluate_observations,
    load_battery_files,
    load_screening_config,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate BatteryIQ baseline-relative event triggering.")
    parser.add_argument("--input-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data" / "processed" / "batteryiq_results")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "batteryiq.yaml")
    parser.add_argument("--max-files", type=int, default=10, help="Development limit; defaults to 10 files.")
    return parser


def _save_plot(path: Path, title: str) -> None:
    plt.title(title)
    plt.tight_layout()
    plt.savefig(path, dpi=140)
    plt.close()


def generate_plots(event_frame: pd.DataFrame, retained_frame: pd.DataFrame, plot_dir: Path) -> None:
    plot_dir.mkdir(parents=True, exist_ok=True)
    if event_frame.empty:
        return

    plt.figure(figsize=(8, 5))
    plt.hist(event_frame["anomaly_score"], bins=30, color="#3973ac", alpha=0.85)
    plt.xlabel("Anomaly score")
    plt.ylabel("Windows")
    _save_plot(plot_dir / "anomaly_score_distribution.png", "Anomaly score distribution")

    plt.figure(figsize=(10, 5))
    plt.scatter(event_frame["start_sample"], event_frame["anomaly_score"], c=event_frame["suspicious"].astype(int), cmap="coolwarm", s=14)
    plt.xlabel("Sample index")
    plt.ylabel("Anomaly score")
    _save_plot(plot_dir / "anomaly_score_vs_sample_index.png", "Anomaly score vs sample index")

    for column, filename, title in [
        ("V_spread", "voltage_spread_vs_sample_index.png", "Voltage spread vs sample index"),
        ("T_spread", "temperature_spread_vs_sample_index.png", "Temperature spread vs sample index"),
        ("I_mean", "current_vs_sample_index.png", "Current mean vs sample index"),
    ]:
        plt.figure(figsize=(10, 5))
        if column in event_frame:
            plt.scatter(event_frame["start_sample"], event_frame[column], s=12, color="#4c956c")
        plt.xlabel("Sample index")
        plt.ylabel(column)
        _save_plot(plot_dir / filename, title)

    plt.figure(figsize=(10, 5))
    plt.plot(event_frame["start_sample"], event_frame["anomaly_score"], color="#555555", linewidth=0.8)
    triggered = event_frame[event_frame["ai_status"] == "AI_REQUIRED"]
    if not triggered.empty:
        plt.scatter(triggered["start_sample"], triggered["anomaly_score"], color="#d1495b", label="AI_REQUIRED", zorder=3)
        plt.legend()
    plt.xlabel("Sample index")
    plt.ylabel("Anomaly score")
    _save_plot(plot_dir / "event_trigger_markers.png", "Event-trigger markers")

    plt.figure(figsize=(10, 5))
    if not retained_frame.empty and "orig_idx" in retained_frame:
        plt.scatter(retained_frame["orig_idx"], [1] * len(retained_frame), s=10, color="#d1495b")
    plt.xlabel("Retained original sample index")
    plt.ylabel("DDP retained marker")
    _save_plot(plot_dir / "ddp_retained_samples.png", "DDP retained samples around triggered events")


def main() -> int:
    args = _parser().parse_args()
    config = load_screening_config(args.config)
    records = load_battery_files(args.input_dir, args.max_files)
    print(f"Loading {len(records)} files (max-files={args.max_files})")
    observations, baselines = collect_window_observations(records, config)
    events, retained, summary, per_battery = evaluate_observations(observations, config)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    events_path = args.output_dir / "event_trigger_evaluation.csv"
    retained_path = args.output_dir / "event_trigger_ddp_retained.csv"
    per_battery_path = args.output_dir / "event_trigger_per_battery.csv"
    summary_path = args.output_dir / "event_trigger_summary.json"
    events.to_csv(events_path, index=False)
    retained.to_csv(retained_path, index=False)
    per_battery.to_csv(per_battery_path, index=False)
    summary_payload = {
        "files_processed": len(records),
        "batteries": len(baselines),
        "baseline_strategy": config.baseline_strategy,
        "baseline_samples_requested": config.baseline_samples,
        "window_size": config.window_size,
        "window_step": config.window_step,
        "trigger_threshold": config.trigger_threshold,
        "min_trigger_windows": config.min_trigger_windows,
        "cooldown_windows": config.cooldown_windows,
        "weights": dict(config.weights),
        "baselines": [baseline.as_dict() for baseline in baselines.values()],
        "summary": summary,
    }
    summary_path.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
    generate_plots(events, retained, args.output_dir / "plots")

    print(f"Files processed: {len(records)}")
    print(f"Batteries: {len(baselines)}")
    print(f"Total windows: {summary['total_windows']}")
    print(f"Triggered windows: {summary['triggered_windows']}")
    print(f"Skipped windows: {summary['skipped_windows']}")
    print(f"Inference avoidance: {summary['inference_avoidance_percent']:.2f}%")
    print(f"Mean anomaly score: {summary['mean_anomaly_score']:.6f}")
    print(f"Median anomaly score: {summary['median_anomaly_score']:.6f}")
    print(f"Maximum anomaly score: {summary['maximum_anomaly_score']:.6f}")
    print(f"DDP input rows: {summary['ddp_input_rows']}")
    print(f"DDP retained rows: {summary['ddp_retained_rows']}")
    print(f"DDP retention: {summary['ddp_retention_percent']:.4f}%")
    print(f"Results: {events_path}")
    print(f"Summary: {summary_path}")
    print(f"Plots: {args.output_dir / 'plots'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
