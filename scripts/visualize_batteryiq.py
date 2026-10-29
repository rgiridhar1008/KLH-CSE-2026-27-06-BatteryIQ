"""Generate basic BatteryIQ screening/DDP/risk plots."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ddp_downsampling.downsampling import find_csv_files, normalise_input_columns  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Plot BatteryIQ pipeline results.")
    parser.add_argument("--input-file", type=Path, default=None)
    parser.add_argument("--results-dir", type=Path, default=REPO_ROOT / "data" / "processed" / "batteryiq_results")
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser


def _save_signal_plot(x: np.ndarray, columns: list[str], frame: pd.DataFrame, title: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12, 4))
    if columns:
        for column in columns:
            ax.plot(x, pd.to_numeric(frame[column], errors="coerce"), linewidth=0.8, label=column)
        ax.legend(loc="best", ncol=4, fontsize=8)
    else:
        ax.text(0.5, 0.5, "No signal columns available", ha="center", va="center", transform=ax.transAxes)
    ax.set(title=title, xlabel="Sequential sample index")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def main() -> int:
    args = _parser().parse_args()
    files = [args.input_file] if args.input_file else find_csv_files(REPO_ROOT / "data" / "raw")
    if not files:
        raise SystemExit("No input CSV found. Supply --input-file or place data under data/raw/.")
    input_file = Path(files[0])
    frame = normalise_input_columns(pd.read_csv(input_file))
    results_path = args.results_dir / "batteryiq_results.csv"
    retained_path = args.results_dir / "ddp_retained_samples.csv"
    results = pd.read_csv(results_path) if results_path.exists() else pd.DataFrame()
    retained = pd.read_csv(retained_path) if retained_path.exists() else pd.DataFrame()
    raw_root = (REPO_ROOT / "data" / "raw").resolve()
    try:
        source_key = input_file.resolve().relative_to(raw_root).as_posix()
    except ValueError:
        source_key = input_file.name
    if "source_file" in results.columns:
        results = results[results["source_file"].astype(str) == source_key]
    if "source_file" in retained.columns:
        retained = retained[retained["source_file"].astype(str) == source_key]

    output_dir = args.output_dir or (args.results_dir / "plots")
    output_dir.mkdir(parents=True, exist_ok=True)
    x = np.arange(len(frame), dtype=int)
    voltage_cols = [c for c in frame.columns if str(c).lower().startswith("vol_")]
    temperature_cols = [c for c in frame.columns if str(c).lower().startswith("temp")]
    _save_signal_plot(x, voltage_cols, frame, "Cell voltage vs sequential sample index", output_dir / "voltage_vs_sample.png")
    _save_signal_plot(x, ["cur"] if "cur" in frame.columns else [], frame, "Current vs sequential sample index", output_dir / "current_vs_sample.png")
    _save_signal_plot(x, temperature_cols, frame, "Temperature vs sequential sample index", output_dir / "temperature_vs_sample.png")

    centers = ((results["start_sample"] + results["end_sample"]) / 2.0).to_numpy() if not results.empty else np.array([])
    scores = results["screening_score"].to_numpy(dtype=float) if not results.empty else np.array([])
    suspicious = results["suspicious"].astype(bool).to_numpy() if not results.empty else np.array([], dtype=bool)
    fig, ax = plt.subplots(figsize=(12, 4))
    if centers.size:
        ax.plot(centers, scores, marker=".", linewidth=0.8, label="screening score")
        ax.scatter(centers[suspicious], scores[suspicious], color="red", label="suspicious")
    ax.set(title="Screening score and suspicious events", xlabel="Sample index", ylabel="Score")
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_dir / "screening_score_events.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 3))
    ax.plot(x, np.zeros_like(x), ".", markersize=2, label="original samples")
    if "orig_idx" in retained.columns and not retained.empty:
        ax.scatter(retained["orig_idx"], np.ones(len(retained)), s=8, label="retained DDP samples")
    ax.set(title="DDP retained samples vs original samples", xlabel="Sequential sample index", yticks=[0, 1], yticklabels=["original", "retained"])
    ax.grid(alpha=0.25)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(output_dir / "ddp_retained_vs_original.png", dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 3))
    if not results.empty:
        states = {"NORMAL": 0, "WARNING": 1, "CHARGING_RESTRICTION": 2, "POWER_LIMITATION": 3, "PROTECTION": 4}
        y = [states.get(str(value), -1) for value in results["risk_state"]]
        ax.step(centers, y, where="mid")
    ax.set(title="Risk state timeline (software-policy simulation)", xlabel="Sample index", yticks=list(range(5)), yticklabels=["NORMAL", "WARNING", "CHARGING_RESTRICTION", "POWER_LIMITATION", "PROTECTION"])
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_dir / "risk_state_timeline.png", dpi=140)
    plt.close(fig)

    print(f"Plots written to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
