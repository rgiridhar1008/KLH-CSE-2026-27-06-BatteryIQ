"""One-window local-Qwen smoke helper using the shared diagnostic model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from batteryiq.baseline import construct_baseline  # noqa: E402
from batteryiq.diagnosis import (  # noqa: E402
    LEVEL2_FEATURE_NAMES as FEATURE_NAMES,
    LocalGGUFDiagnosticModel,
    build_diagnostic_prompt,
    load_llama,
    parse_diagnostic_json,
    request_qwen,
)
from batteryiq.screening import extract_window_features  # noqa: E402


DEFAULT_MODEL_PATH = REPO_ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
DEFAULT_INPUT_DIR = REPO_ROOT / "data" / "raw"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local Qwen on one BatteryData feature window.")
    parser.add_argument("--input-file", type=Path, default=None)
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--window-start", type=int, default=1000)
    parser.add_argument("--window-size", type=int, default=50)
    parser.add_argument("--max-tokens", type=int, default=256)
    return parser


def select_input_file(input_file: Optional[Path]) -> Path:
    if input_file is not None:
        path = Path(input_file)
        if path.suffix.lower() != ".csv" or not path.is_file():
            raise FileNotFoundError(f"CSV input file not found: {path}")
        return path
    files = sorted(DEFAULT_INPUT_DIR.rglob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found under {DEFAULT_INPUT_DIR}")
    return files[0]


def load_one_window(path: Path, start: int, size: int) -> Tuple[pd.DataFrame, Dict[str, Optional[float]]]:
    if start < 0 or size <= 0:
        raise ValueError("window-start must be non-negative and window-size must be positive.")
    frame = pd.read_csv(path)
    window = frame.iloc[start:start + size].copy()
    if len(window) != size:
        raise ValueError(f"Requested rows {start}:{start + size - 1}, but {path.name} has {len(frame)} rows.")
    features = extract_window_features(window)
    return window, {name: features[name] for name in FEATURE_NAMES}


def run_smoke_test(
    input_file: Path,
    model_path: Path,
    window_start: int,
    window_size: int,
    max_tokens: int,
    llm_loader: Callable[[Path], Any] = load_llama,
) -> Dict[str, Any]:
    """Execute one shared-model request; retained for focused unit testing."""
    window, features = load_one_window(input_file, window_start, window_size)
    baseline = construct_baseline(window, ".", "smoke", window_size)
    model = LocalGGUFDiagnosticModel(model_path, max_tokens=max_tokens, llm_loader=llm_loader)
    result = model.diagnose(window, {"baseline": baseline})
    return {
        "csv_filename": input_file.name,
        "csv_path": str(input_file),
        "window_start_row": window_start,
        "window_end_row": window_start + len(window) - 1,
        "features": features,
        "raw_response": result.raw_response,
        "parsed_response": ({"anomaly_level": result.severity, "reason": result.reason, "evidence": list(result.evidence)} if result.json_parsed else None),
        "parse_error": result.json_parse_error,
        "inference_seconds": result.inference_seconds,
        "model_load_seconds": model.model_load_seconds,
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        result = run_smoke_test(select_input_file(args.input_file), args.model_path, args.window_start, args.window_size, args.max_tokens)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Smoke test could not run: {error}")
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
