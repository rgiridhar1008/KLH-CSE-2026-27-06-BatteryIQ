"""Run the BatteryIQ per-file screening and triggered-DDP pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ddp_downsampling.battery_pipeline import RESULT_COLUMNS, process_battery_dataframe  # noqa: E402
from ddp_downsampling.config import PipelineConfig  # noqa: E402
from ddp_downsampling.downsampling import find_csv_files  # noqa: E402
from ddp_downsampling.event_trigger import ScreeningConfig  # noqa: E402
from ddp_downsampling.risk_policy import load_risk_policy  # noqa: E402


def load_pipeline_config(path: Path) -> ScreeningConfig:
    with Path(path).open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    screening = raw.get("screening", {}) or {}
    thresholds = screening.get("thresholds", {}) or {}
    return ScreeningConfig(
        window_size=max(1, int(raw.get("window_size", 50))),
        window_step=max(1, int(raw.get("window_step", 50))),
        thresholds={str(k): float(v) for k, v in thresholds.items()},
        min_triggered_features=max(1, int(screening.get("min_triggered_features", 1))),
        score_threshold=float(screening.get("score_threshold", 1.0)),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run BatteryIQ level-1 screening and triggered DDP.")
    parser.add_argument("--input-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data" / "processed" / "batteryiq_results")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "batteryiq.yaml")
    parser.add_argument("--risk-policy", type=Path, default=REPO_ROOT / "config" / "risk_policy.yaml")
    parser.add_argument("--max-files", type=int, default=None, help="Optional development limit; never required for normal runs.")
    return parser


def main() -> int:
    args = _parser().parse_args()
    screening_config = load_pipeline_config(args.config)
    risk_policy = load_risk_policy(args.risk_policy)
    ddp_config = PipelineConfig()

    files = find_csv_files(args.input_dir)
    if args.max_files is not None:
        files = files[: max(0, int(args.max_files))]
    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_windows: List[pd.DataFrame] = []
    all_retained: List[pd.DataFrame] = []
    file_summaries: List[Dict[str, Any]] = []
    total_input_rows = 0
    for number, source in enumerate(files, start=1):
        relative = source.relative_to(args.input_dir).as_posix()
        print(f"[{number}/{len(files)}] processing {relative}")
        frame = pd.read_csv(source)
        window_rows, retained, file_summary = process_battery_dataframe(
            frame,
            relative,
            ddp_config,
            screening_config,
            risk_policy,
        )
        all_windows.append(window_rows)
        if not retained.empty:
            all_retained.append(retained)
        file_summaries.append(file_summary)
        total_input_rows += int(len(frame))

    if all_windows:
        results = pd.concat(all_windows, ignore_index=True)
    else:
        results = pd.DataFrame(columns=RESULT_COLUMNS)
    if all_retained:
        retained_rows = pd.concat(all_retained, ignore_index=True)
    else:
        retained_rows = pd.DataFrame(columns=["source_file", "orig_idx"])

    results_path = args.output_dir / "batteryiq_results.csv"
    summary_path = args.output_dir / "batteryiq_summary.json"
    retained_path = args.output_dir / "ddp_retained_samples.csv"
    results.to_csv(results_path, index=False)
    retained_rows.to_csv(retained_path, index=False)

    risk_counts = {
        str(key): int(value)
        for key, value in results["risk_state"].value_counts(dropna=False).items()
    } if "risk_state" in results.columns else {}
    total_windows = int(len(results))
    suspicious_windows = int(results["suspicious"].sum()) if "suspicious" in results.columns else 0
    ai_invocations = int((results["ai_status"] == "AI_REQUIRED").sum()) if "ai_status" in results.columns else 0
    ai_skipped = int((results["ai_status"] == "AI_SKIPPED").sum()) if "ai_status" in results.columns else 0
    summary: Dict[str, Any] = {
        "csv_files": len(files),
        "total_input_rows": total_input_rows,
        "total_windows": total_windows,
        "suspicious_windows": suspicious_windows,
        "ai_invocations": ai_invocations,
        "ai_skipped": ai_skipped,
        "inference_avoidance_percent": (100.0 * ai_skipped / total_windows) if total_windows else 0.0,
        "risk_state_counts": risk_counts,
        "total_retained_ddp_rows": int(len(retained_rows)),
        "overall_retention_percentage": (100.0 * len(retained_rows) / total_input_rows) if total_input_rows else 0.0,
        "files": file_summaries,
        "placeholder_diagnosis": True,
        "research_policy_simulation_only": True,
    }
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    with (args.output_dir / "per_file_summaries.json").open("w", encoding="utf-8") as handle:
        json.dump(file_summaries, handle, indent=2)

    print(f"CSV files: {len(files)}")
    print(f"Total input rows: {total_input_rows}")
    print(f"Total windows: {total_windows}")
    print(f"Suspicious windows: {suspicious_windows}")
    print(f"AI invocations: {ai_invocations}")
    print(f"AI skipped: {ai_skipped}")
    print(f"Inference avoidance: {summary['inference_avoidance_percent']:.2f}%")
    print(f"Risk state counts: {risk_counts}")
    print(f"Total retained DDP rows: {len(retained_rows)}")
    print(f"Overall retention: {summary['overall_retention_percentage']:.2f}%")
    print(f"Results: {results_path}")
    print(f"Summary: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

