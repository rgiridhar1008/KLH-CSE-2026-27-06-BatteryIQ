"""Local GGUF Level-2 diagnostic support for BatteryIQ experiments.

This module deliberately performs descriptive, baseline-relative anomaly
interpretation only.  It does not assign physical fault types or severity.
"""

from __future__ import annotations

import json
import time
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from .baseline import BatteryBaseline
from .screening import extract_window_features


LEVEL2_FEATURE_NAMES: Sequence[str] = (
    "V_mean", "V_std", "V_spread", "V_rate", "I_mean", "I_std", "I_rate",
    "T_mean", "T_std", "T_spread", "T_rate",
)

WINDOW_TO_BASELINE = {
    "V_mean": "voltage_mean", "V_std": "voltage_std", "V_spread": "voltage_spread",
    "V_rate": "voltage_rate", "I_mean": "current_mean", "I_std": "current_std",
    "I_rate": "current_rate", "T_mean": "temperature_mean", "T_std": "temperature_std",
    "T_spread": "temperature_spread", "T_rate": "temperature_rate",
}


def _json_value(value: Optional[float]) -> Optional[float]:
    """Convert NumPy scalars and non-finite values to JSON-safe values."""
    if value is None or not np.isfinite(value):
        return None
    return float(value)


def validate_level2_features(features: Mapping[str, Optional[float]]) -> Dict[str, Optional[float]]:
    """Return exactly the established eleven Level-2 features, in fixed order."""
    if set(features) != set(LEVEL2_FEATURE_NAMES):
        raise ValueError("Qwen diagnostic input must contain exactly the eleven established Level-2 features.")
    return {name: _json_value(features[name]) for name in LEVEL2_FEATURE_NAMES}


def baseline_reference_statistics(baseline: BatteryBaseline) -> Dict[str, Dict[str, Optional[float]]]:
    """Expose supplied per-feature baseline means and scales without physical ranges."""
    return {
        name: {
            "reference": _json_value(baseline.features.get(baseline_name)),
            "scale": _json_value(baseline.scales.get(baseline_name)),
        }
        for name, baseline_name in WINDOW_TO_BASELINE.items()
    }


def build_diagnostic_prompt(
    features: Mapping[str, Optional[float]],
    reference_statistics: Mapping[str, Mapping[str, Optional[float]]],
    context: Mapping[str, Any] = None,
) -> str:
    """Build the constrained, baseline-relative Qwen prompt."""
    values = validate_level2_features(features)
    references = {name: dict(reference_statistics.get(name, {})) for name in LEVEL2_FEATURE_NAMES}
    
    ctx_str = ""
    if context:
        ctx_subset = {
            "anomaly_score": context.get("anomaly_score"),
            "suspicious": context.get("suspicious"),
            "triggered_features": context.get("triggered_features"),
            "deviations": context.get("deviations"),
            "ddp_retained_rows": context.get("ddp_retained_rows"),
            "ddp_retention_percent": context.get("ddp_retention_percent"),
            "ddp_vdd_mean": context.get("ddp_vdd_mean"),
            "ddp_cdd_mean": context.get("ddp_cdd_mean"),
            "ddp_high_count": context.get("ddp_high_count"),
            "ddp_mid_count": context.get("ddp_mid_count"),
            "ddp_low_count": context.get("ddp_low_count"),
        }
        ctx_str = f"Level-1 and DDP Context:\n{json.dumps(ctx_subset, allow_nan=False, indent=2)}\n"

    return f"""You are the Level-2 diagnostic model in a battery monitoring system.

Important evaluation boundaries:
- BatteryData has no explicit fault labels.
- Do not invent fault classes.
- Do not claim physical fault severity; evaluated anomaly level is relative to the supplied baseline/reference statistics (NOT physical-fault severity).
- Distinguish between:
  - evidence supporting an anomaly
  - evidence against an anomaly
  - insufficient evidence

Level-1 has already screened this battery window and marked it suspicious.
Do NOT ignore the Level-1 result.
Use the Level-1 anomaly score, triggered features, deviations, DDP features and baseline together.
Your job is to verify and explain the suspicious event.

Do not simply say that an individual feature is within a normal reference range if the overall Level-1 event indicates abnormal behavior.
Do not invent battery faults that are not supported by the supplied data.

Return only one valid JSON object with exactly this schema:
{{
  "anomaly_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "diagnosis": "SHORT DIAGNOSIS",
  "reason": "Clear explanation of why the window is or is not concerning.",
  "evidence": [
    "Evidence from Level-1",
    "Evidence from DDP",
    "Evidence from battery measurements"
  ],
  "level1_consistency": "CONSISTENT|PARTIALLY_CONSISTENT|INCONSISTENT",
  "recommended_action": "MONITOR|WARNING|FURTHER_ANALYSIS|PROTECTION",
  "confidence": 0.0
}}

Level-2 feature values:
{json.dumps(values, allow_nan=False, indent=2)}

Supplied baseline/reference statistics (reference and observed-variation scale):
{json.dumps(references, allow_nan=False, indent=2)}

{ctx_str}"""


def parse_diagnostic_json(raw_response: str) -> Dict[str, Any]:
    """Safely parse the required constrained JSON response."""
    candidate = raw_response.strip()
    if candidate.startswith("```"):
        candidate = candidate.split("\n", 1)[1] if "\n" in candidate else ""
        if candidate.rstrip().endswith("```"):
            candidate = candidate.rstrip()[:-3].rstrip()
            
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("No JSON object found in model response.")
        
    try:
        parsed = json.loads(candidate[start:end+1])
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON response: {error.msg}") from error
        
    if not isinstance(parsed, dict):
        raise ValueError("Model JSON must be an object.")
        
    # Ensure all required fields exist with defaults if missing
    required = {"anomaly_level", "diagnosis", "reason", "evidence", "level1_consistency", "recommended_action", "confidence"}
    
    for r in required:
        if r not in parsed:
             parsed[r] = None
             
    if not isinstance(parsed.get("evidence"), list):
        parsed["evidence"] = []
        
    if parsed.get("confidence") is not None:
        try:
            parsed["confidence"] = float(parsed["confidence"])
        except (ValueError, TypeError):
             parsed["confidence"] = 0.0
             
    return parsed


def request_qwen(llm: Any, prompt: str, max_tokens: int) -> str:
    """Request JSON mode from a llama-cpp-compatible chat-completion client."""
    temperature = float(os.environ.get("QWEN_TEMPERATURE", "0.1"))
    response = llm.create_chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("llama-cpp returned no chat-completion message content.") from error
    if not isinstance(content, str):
        raise ValueError("llama-cpp returned non-text chat-completion content.")
    return content


def load_llama(model_path: Path) -> Any:
    """Load a local GGUF; this function never downloads a model."""
    if not Path(model_path).is_file():
        raise FileNotFoundError(f"GGUF model not found: {model_path}")
    try:
        from llama_cpp import Llama
    except ModuleNotFoundError as error:
        raise RuntimeError("llama_cpp is not installed in this Python interpreter.") from error
    
    n_ctx = int(os.environ.get("QWEN_CONTEXT_LENGTH", "4096"))
    n_threads = os.environ.get("QWEN_CPU_THREADS")
    n_threads = int(n_threads) if n_threads else None
    n_gpu_layers = int(os.environ.get("QWEN_GPU_LAYERS", "0"))
    
    return Llama(
        model_path=str(model_path), 
        n_ctx=n_ctx,
        n_threads=n_threads,
        n_gpu_layers=n_gpu_layers,
        verbose=False
    )


@dataclass(frozen=True)
class LocalDiagnosticResponse:
    anomaly_level: Optional[str]
    diagnosis: Optional[str]
    reason: Optional[str]
    evidence: tuple[str, ...]
    level1_consistency: Optional[str]
    recommended_action: Optional[str]
    confidence: Optional[float]
    raw_response: str
    parse_error: Optional[str]
    inference_seconds: float

    @property
    def json_parsed(self) -> bool:
        return self.parse_error is None

    @property
    def json_parse_error(self) -> Optional[str]:
        return self.parse_error

    @property
    def severity(self) -> Optional[str]:
        return self.anomaly_level


class LocalGGUFDiagnosticModel:
    """One reusable local-Qwen implementation for Level-2 diagnostics.

    The GGUF is loaded once during construction, only when this class is
    explicitly selected. ``diagnose_features`` accepts exactly the established
    Level-2 feature set; window extraction is an adapter for the experiment.
    """

    model_name = "LOCAL QWEN 7B DIAGNOSTIC MODEL"

    def __init__(
        self,
        model_path: Path,
        max_tokens: int = 1024,
        llm_loader: Callable[[Path], Any] = load_llama,
    ) -> None:
        self.model_path = Path(model_path)
        self.max_tokens = int(os.environ.get("QWEN_MAX_TOKENS", max_tokens))
        started = time.perf_counter()
        self._llm = llm_loader(self.model_path)
        self.model_load_seconds = time.perf_counter() - started
        self.model_calls = 0
        self.total_inference_seconds = 0.0

    def diagnose_features(
        self,
        features: Mapping[str, Optional[float]],
        reference_statistics: Mapping[str, Mapping[str, Optional[float]]],
        context: Mapping[str, Any] = None,
    ) -> LocalDiagnosticResponse:
        """Run one constrained Qwen request for exactly the Level-2 features."""
        prompt = build_diagnostic_prompt(features, reference_statistics, context)
        started = time.perf_counter()
        raw_response = request_qwen(self._llm, prompt, self.max_tokens)
        elapsed = time.perf_counter() - started
        self.model_calls += 1
        self.total_inference_seconds += elapsed
        try:
            parsed = parse_diagnostic_json(raw_response)
            return LocalDiagnosticResponse(
                anomaly_level=parsed["anomaly_level"],
                diagnosis=parsed["diagnosis"],
                reason=parsed["reason"],
                evidence=tuple(parsed["evidence"]),
                level1_consistency=parsed["level1_consistency"],
                recommended_action=parsed["recommended_action"],
                confidence=parsed["confidence"],
                raw_response=raw_response,
                parse_error=None, 
                inference_seconds=elapsed,
            )
        except ValueError as error:
            return LocalDiagnosticResponse(
                anomaly_level=None, diagnosis=None, reason=None, evidence=(),
                level1_consistency=None, recommended_action=None, confidence=None,
                raw_response=raw_response,
                parse_error=str(error), inference_seconds=elapsed,
            )

    def diagnose(self, window_data: pd.DataFrame, context: Mapping[str, Any]) -> LocalDiagnosticResponse:
        """Adapt an experiment window to the shared Level-2 feature interface."""
        baseline = context.get("baseline")
        if not isinstance(baseline, BatteryBaseline):
            raise ValueError("LocalGGUFDiagnosticModel requires context['baseline'].")
        return self.diagnose_features(extract_window_features(window_data), baseline_reference_statistics(baseline), context)
