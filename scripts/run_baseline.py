"""Run the BatteryIQ DDP downsampling baseline over data/raw/*.csv."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ddp_downsampling.config import PipelineConfig, load_kv_csv  # noqa: E402
from ddp_downsampling.downsampling import (  # noqa: E402
    downsample_csv_file,
    find_csv_files,
    mirror_output_path,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the BatteryIQ DDP baseline.")
    parser.add_argument("--input-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data" / "processed")
    parser.add_argument("--config", type=Path, default=None, help="Optional key/value CSV config.")
    return parser


def main() -> int:
    args = _parser().parse_args()
    cfg = PipelineConfig()
    if args.config is not None:
        cfg = PipelineConfig.from_dict(load_kv_csv(args.config))

    files = find_csv_files(args.input_dir)
    if not files:
        print(f"No CSV files found under {args.input_dir}")
        return 0

    stats: List[Dict[str, object]] = []
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for number, source in enumerate(files, start=1):
        destination = mirror_output_path(source, args.input_dir, args.output_dir)
        print(f"[{number}/{len(files)}] {source.relative_to(args.input_dir)}")
        result = downsample_csv_file(source, destination, cfg)
        original_rows = int(result.vdd.size)
        retained_rows = int(len(result.downsampled_df))
        retention = (100.0 * retained_rows / original_rows) if original_rows else 0.0
        compression = (original_rows / retained_rows) if retained_rows else float("inf")
        print(
            f"  original rows: {original_rows}; retained rows: {retained_rows}; "
            f"retention: {retention:.2f}%; compression ratio: {compression:.4f}"
        )
        stats.append(
            {
                "file": str(source.relative_to(args.input_dir)),
                "raw_len": original_rows,
                "down_len": retained_rows,
                "retention_percentage": retention,
                "compression_ratio": compression,
            }
        )

    stats_path = args.output_dir / "downsampling_stats.csv"
    pd.DataFrame(stats).to_csv(stats_path, index=False)
    print(f"Statistics: {stats_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
