"""Exploratory event-trigger threshold sensitivity analysis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from batteryiq.evaluation import (  # noqa: E402
    collect_window_observations,
    load_battery_files,
    load_screening_config,
    threshold_sensitivity,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze exploratory event-trigger thresholds.")
    parser.add_argument("--input-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data" / "processed" / "batteryiq_results")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "batteryiq.yaml")
    parser.add_argument("--max-files", type=int, default=10)
    parser.add_argument("--thresholds", nargs="+", type=float, default=[0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    return parser


def main() -> int:
    args = _parser().parse_args()
    config = load_screening_config(args.config)
    records = load_battery_files(args.input_dir, args.max_files)
    observations, _ = collect_window_observations(records, config)
    table = threshold_sensitivity(observations, config, args.thresholds)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "trigger_threshold_sensitivity.csv"
    table.to_csv(output, index=False)
    print(f"Files processed: {len(records)}")
    print(f"Windows evaluated: {len(observations)}")
    print("Threshold sensitivity (exploratory; no best threshold selected):")
    print(table.to_string(index=False))
    print(f"Results: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
