"""Run exactly three local-Qwen Level-2 diagnostic windows, then stop."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from batteryiq.diagnosis import LocalGGUFDiagnosticModel  # noqa: E402
from batteryiq.evaluation import collect_window_observations, load_battery_files, load_screening_config  # noqa: E402


DEFAULT_MODEL_PATH = REPO_ROOT / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run exactly three local Qwen Level-2 windows.")
    parser.add_argument("--input-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    parser.add_argument("--config", type=Path, default=REPO_ROOT / "config" / "batteryiq.yaml")
    parser.add_argument("--model-path", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--max-files", type=int, default=1, help="Input discovery limit; only three windows are processed.")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "data" / "processed" / "batteryiq_results" / "qwen_smoke_3_windows.json")
    return parser


def run_three_window_smoke(
    input_dir: Path,
    config_path: Path,
    model_path: Path,
    max_files: int = 1,
    max_tokens: int = 256,
) -> Dict[str, Any]:
    """Load Qwen once and call it exactly once for each of three observations."""
    config = load_screening_config(config_path)
    observations, _ = collect_window_observations(load_battery_files(input_dir, max_files), config)
    selected = observations[:3]
    if len(selected) != 3:
        raise ValueError(f"Three post-baseline windows are required; found {len(selected)}.")
    model = LocalGGUFDiagnosticModel(model_path, max_tokens=max_tokens)
    results: List[Dict[str, Any]] = []
    for observation in selected:
        result = model.diagnose(observation.window, {"baseline": observation.baseline, "screening": observation.screening})
        results.append({
            "source_file": observation.source_file,
            "start_sample": observation.start_sample,
            "end_sample": observation.end_sample,
            "response": {"anomaly_level": result.severity, "reason": result.reason, "evidence": list(result.evidence)},
            "json_parsed": result.json_parsed,
            "json_parse_error": result.json_parse_error,
            "inference_seconds": result.inference_seconds,
        })
    parse_successes = sum(item["json_parsed"] is True for item in results)
    return {
        "model_name": model.model_name,
        "windows_processed": len(results),
        "qwen_calls": model.model_calls,
        "model_load_seconds": model.model_load_seconds,
        "average_inference_seconds": model.total_inference_seconds / model.model_calls if model.model_calls else None,
        "total_inference_seconds": model.total_inference_seconds,
        "json_parsing_successes": parse_successes,
        "json_parsing_failures": len(results) - parse_successes,
        "results": results,
        "interpretation": "This is a three-window local-Qwen smoke test. It makes no fault, accuracy, recall, or physical-severity claim.",
    }


def main() -> int:
    args = _parser().parse_args()
    try:
        summary = run_three_window_smoke(args.input_dir, args.config, args.model_path, args.max_files, args.max_tokens)
    except (FileNotFoundError, RuntimeError, ValueError) as error:
        print(f"Qwen smoke experiment could not run: {error}")
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, indent=2))
    print(f"Results: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
