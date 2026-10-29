"""
BatteryIQ Level-2 AI Diagnosis

Real local Qwen2.5-1.5B GGUF diagnostic interface.

Pipeline:

Level-1 Screening
        ↓
Suspicious Window
        ↓
DDP Adaptive Downsampling
        ↓
Qwen2.5-1.5B
        ↓
Level-2 AI Verification

The model receives both:
1. DDP-selected battery measurements
2. Level-1 screening evidence

This allows Qwen to verify/explain the event detected by Level-1
instead of independently evaluating the window without context.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

import pandas as pd

try:
    from .baseline import BatteryBaseline
except ImportError:
    from batteryiq.baseline import BatteryBaseline


# ============================================================
# LEVEL-2 FEATURE DEFINITIONS
# ============================================================

LEVEL2_FEATURE_NAMES = (
    "V_mean",
    "V_std",
    "V_spread",
    "V_rate",
    "I_mean",
    "I_std",
    "I_rate",
    "T_mean",
    "T_std",
    "T_spread",
    "T_rate",
)


WINDOW_TO_BASELINE = {
    "V_mean": "voltage_mean",
    "V_std": "voltage_std",
    "V_spread": "voltage_spread",
    "V_rate": "voltage_rate",
    "I_mean": "current_mean",
    "I_std": "current_std",
    "I_rate": "current_rate",
    "T_mean": "temperature_mean",
    "T_std": "temperature_std",
    "T_spread": "temperature_spread",
    "T_rate": "temperature_rate",
}


# ============================================================
# JSON HELPERS
# ============================================================

def _json_value(value: Optional[float]) -> Optional[float]:
    """
    Convert NumPy/Pandas numeric values into JSON-safe values.
    """
    if value is None:
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    return value


# ============================================================
# WINDOW FEATURE EXTRACTION
# ============================================================

def _voltage_columns(df: pd.DataFrame) -> list[str]:
    """
    Return voltage columns sorted by numeric suffix.
    """

    columns = [
        c for c in df.columns
        if str(c).lower().startswith("vol_")
    ]

    def sort_key(column: str):
        try:
            return int(str(column).split("_")[-1])
        except ValueError:
            return 9999

    return sorted(columns, key=sort_key)


def _temperature_columns(df: pd.DataFrame) -> list[str]:
    """
    Return temperature columns sorted by numeric suffix.
    """

    columns = [
        c for c in df.columns
        if str(c).lower().startswith("temp_")
    ]

    def sort_key(column: str):
        try:
            return int(str(column).split("_")[-1])
        except ValueError:
            return 9999

    return sorted(columns, key=sort_key)


def _safe_mean(series: pd.Series) -> Optional[float]:
    values = pd.to_numeric(series, errors="coerce").dropna()

    if len(values) == 0:
        return None

    return _json_value(values.mean())


def _safe_std(series: pd.Series) -> Optional[float]:
    values = pd.to_numeric(series, errors="coerce").dropna()

    if len(values) < 2:
        return 0.0 if len(values) == 1 else None

    return _json_value(values.std(ddof=0))


def _safe_spread(series: pd.Series) -> Optional[float]:
    values = pd.to_numeric(series, errors="coerce").dropna()

    if len(values) == 0:
        return None

    return _json_value(values.max() - values.min())


def _safe_rate(series: pd.Series) -> Optional[float]:
    """
    Mean absolute first difference.

    This provides a simple temporal-change descriptor without
    assuming a timestamp column exists in the uploaded dataset.
    """

    values = pd.to_numeric(series, errors="coerce").dropna()

    if len(values) < 2:
        return 0.0 if len(values) == 1 else None

    diff = values.diff().dropna().abs()

    if len(diff) == 0:
        return 0.0

    return _json_value(diff.mean())


def extract_window_features(
    window: pd.DataFrame,
) -> Dict[str, Optional[float]]:
    """
    Extract the established BatteryIQ Level-2 feature set.

    Features are calculated across all voltage and temperature
    channels and the current channel.
    """

    voltage_cols = _voltage_columns(window)
    temperature_cols = _temperature_columns(window)

    if not voltage_cols:
        raise ValueError(
            "No voltage columns found. Expected vol_1, vol_2, ..."
        )

    if not temperature_cols:
        raise ValueError(
            "No temperature columns found. Expected temp_1, temp_2, ..."
        )

    if "cur" not in window.columns:
        raise ValueError(
            "Current column 'cur' is missing."
        )

    voltage_values = window[voltage_cols].apply(
        pd.to_numeric,
        errors="coerce",
    )

    temperature_values = window[temperature_cols].apply(
        pd.to_numeric,
        errors="coerce",
    )

    current_values = pd.to_numeric(
        window["cur"],
        errors="coerce",
    )

    # Flatten sensor values for distribution statistics.
    voltage_flat = voltage_values.stack().dropna()
    temperature_flat = temperature_values.stack().dropna()

    features: Dict[str, Optional[float]] = {}

    # --------------------------------------------------------
    # Voltage
    # --------------------------------------------------------

    features["V_mean"] = (
        _json_value(voltage_flat.mean())
        if len(voltage_flat) else None
    )

    features["V_std"] = (
        _json_value(voltage_flat.std(ddof=0))
        if len(voltage_flat) else None
    )

    if len(voltage_flat):
        features["V_spread"] = _json_value(
            voltage_flat.max() - voltage_flat.min()
        )
    else:
        features["V_spread"] = None

    # Mean voltage across cells at each row.
    voltage_row_mean = voltage_values.mean(axis=1)

    features["V_rate"] = _safe_rate(
        voltage_row_mean
    )

    # --------------------------------------------------------
    # Current
    # --------------------------------------------------------

    features["I_mean"] = _safe_mean(current_values)
    features["I_std"] = _safe_std(current_values)
    features["I_rate"] = _safe_rate(current_values)

    # --------------------------------------------------------
    # Temperature
    # --------------------------------------------------------

    features["T_mean"] = (
        _json_value(temperature_flat.mean())
        if len(temperature_flat) else None
    )

    features["T_std"] = (
        _json_value(temperature_flat.std(ddof=0))
        if len(temperature_flat) else None
    )

    if len(temperature_flat):
        features["T_spread"] = _json_value(
            temperature_flat.max() - temperature_flat.min()
        )
    else:
        features["T_spread"] = None

    temperature_row_mean = temperature_values.mean(axis=1)

    features["T_rate"] = _safe_rate(
        temperature_row_mean
    )

    return features


# ============================================================
# BASELINE STATISTICS
# ============================================================

def baseline_reference_statistics(
    baseline: BatteryBaseline,
) -> Dict[str, Optional[float]]:
    """
    Convert BatteryBaseline into the reference-statistics format
    used by the Level-2 Qwen prompt.
    """

    result: Dict[str, Optional[float]] = {}

    # BatteryBaseline implementations may expose different
    # attributes depending on the current project version.
    # We therefore read the known feature mapping safely.

    for feature_name, baseline_name in WINDOW_TO_BASELINE.items():

        value = getattr(
            baseline,
            baseline_name,
            None,
        )

        if value is None:
            # Some implementations store feature statistics
            # inside a mapping.
            statistics = getattr(
                baseline,
                "feature_statistics",
                None,
            )

            if isinstance(statistics, Mapping):
                value = statistics.get(
                    baseline_name
                )

        result[feature_name] = _json_value(value)

    return result


# ============================================================
# FEATURE VALIDATION
# ============================================================

def validate_level2_features(
    features: Mapping[str, Any],
) -> Dict[str, Optional[float]]:
    """
    Ensure the Level-2 feature set is complete and JSON safe.
    """

    validated: Dict[str, Optional[float]] = {}

    for name in LEVEL2_FEATURE_NAMES:
        value = features.get(name)

        validated[name] = _json_value(value)

    return validated


# ============================================================
# QWEN PROMPT
# ============================================================

def build_diagnostic_prompt(
    features: Mapping[str, Any],
    reference_statistics: Mapping[str, Any],
    level1_context: Optional[Mapping[str, Any]] = None,
) -> str:
    """
    Build a constrained diagnostic prompt.

    Level-1 evidence is explicitly included so Qwen acts as a
    second-level verifier rather than ignoring the event trigger.
    """

    validated_features = validate_level2_features(
        features
    )

    level1_context = level1_context or {}

    anomaly_score = level1_context.get(
        "anomaly_score"
    )

    suspicious = level1_context.get(
        "suspicious"
    )

    triggered_features = level1_context.get(
        "triggered_features",
        [],
    )

    feature_values = level1_context.get(
        "feature_values",
        {},
    )

    deviations = level1_context.get(
        "deviations",
        {},
    )

    # --------------------------------------------------------
    # Format Level-1 evidence
    # --------------------------------------------------------

    triggered_text = ", ".join(
        str(x)
        for x in triggered_features
    ) if triggered_features else "None reported"

    feature_value_lines = []

    if isinstance(feature_values, Mapping):
        for key, value in feature_values.items():
            feature_value_lines.append(
                f"{key}: {value}"
            )

    feature_value_text = (
        "\n".join(feature_value_lines)
        if feature_value_lines
        else "None available"
    )

    deviation_lines = []

    if isinstance(deviations, Mapping):
        for key, value in deviations.items():
            deviation_lines.append(
                f"{key}: {value}"
            )

    deviation_text = (
        "\n".join(deviation_lines)
        if deviation_lines
        else "None available"
    )

    # --------------------------------------------------------
    # Format Level-2 features
    # --------------------------------------------------------

    feature_lines = []

    for name in LEVEL2_FEATURE_NAMES:
        feature_lines.append(
            f"{name}: {validated_features.get(name)}"
        )

    feature_text = "\n".join(
        feature_lines
    )

    # --------------------------------------------------------
    # Format baseline
    # --------------------------------------------------------

    reference_lines = []

    for name in LEVEL2_FEATURE_NAMES:
        reference_lines.append(
            f"{name}: {reference_statistics.get(name)}"
        )

    reference_text = "\n".join(
        reference_lines
    )

    # --------------------------------------------------------
    # Final prompt
    # --------------------------------------------------------

    return f"""
You are the Level-2 AI verification module of BatteryIQ,
an event-triggered lithium-ion battery monitoring system.

Your task is to analyze a suspicious battery window after
Level-1 lightweight screening and DDP adaptive downsampling.

IMPORTANT:
- Do not invent a physical fault that cannot be supported by the data.
- Do not treat an anomaly score alone as proof of a battery fault.
- Use the Level-1 evidence together with the DDP-selected features.
- Explain whether the Level-1 trigger is supported, contradicted,
  or inconclusive.
- If the measurements do not support a strong anomaly, return LOW.
- If there is meaningful abnormal evidence, return MEDIUM or HIGH
  according to the strength of the evidence.
- Use CRITICAL only when the supplied evidence clearly indicates
  an extreme condition.
- Return ONLY valid JSON.
- Do not use Markdown.
- Do not add text before or after the JSON.

============================================================
LEVEL-1 SCREENING RESULT
============================================================

Anomaly score:
{anomaly_score}

Suspicious:
{suspicious}

Triggered features:
{triggered_text}

Level-1 feature values:
{feature_value_text}

Level-1 deviations:
{deviation_text}

============================================================
DDP-DOWNSAMPLED LEVEL-2 FEATURES
============================================================

{feature_text}

============================================================
BATTERY BASELINE REFERENCE
============================================================

{reference_text}

============================================================
DECISION TASK
============================================================

Determine the Level-2 assessment.

Consider:

1. Does the DDP-selected data support the Level-1 trigger?
2. Which measurements provide evidence?
3. Which measurements contradict or weaken the trigger?
4. Is the available evidence sufficient for a higher severity?
5. Avoid claiming a specific physical fault unless supported.

Return exactly this JSON structure:

{{
  "anomaly_level": "LOW",
  "reason": "Short explanation based on the supplied evidence.",
  "evidence": [
    "Evidence item 1",
    "Evidence item 2"
  ]
}}

Allowed anomaly_level values:

LOW
MEDIUM
HIGH
CRITICAL
""".strip()


# ============================================================
# QWEN LOADER
# ============================================================

def load_llama(model_path: Path) -> Any:
    """
    Load the local GGUF using llama-cpp-python.
    """

    from llama_cpp import Llama

    return Llama(
        model_path=str(model_path),
        n_ctx=4096,
        n_threads=8,
        verbose=False,
    )


# ============================================================
# QWEN REQUEST
# ============================================================

def request_qwen(
    llm: Any,
    prompt: str,
    max_tokens: int,
) -> str:
    """
    Request a JSON response from Qwen.
    """

    response = llm.create_chat_completion(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        temperature=0.0,
        max_tokens=max_tokens,
        response_format={
            "type": "json_object"
        },
    )

    try:
        content = (
            response[
                "choices"
            ][0][
                "message"
            ][
                "content"
            ]
        )

    except (
        KeyError,
        IndexError,
        TypeError,
    ) as error:

        raise RuntimeError(
            "Unexpected llama.cpp response structure."
        ) from error

    if not isinstance(content, str):
        raise RuntimeError(
            "Qwen returned a non-string response."
        )

    return content.strip()


# ============================================================
# JSON PARSER
# ============================================================

def parse_diagnostic_json(
    raw_response: str,
) -> Dict[str, Any]:
    """
    Parse and validate the constrained Qwen JSON response.
    """

    if not raw_response:
        raise ValueError(
            "Qwen returned an empty response."
        )

    text = raw_response.strip()

    # First attempt: direct JSON.
    try:
        parsed = json.loads(text)

    except json.JSONDecodeError:

        # Fallback: extract the first JSON object.
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end <= start:
            raise ValueError(
                "No JSON object found in Qwen response."
            )

        candidate = text[
            start:end + 1
        ]

        try:
            parsed = json.loads(
                candidate
            )

        except json.JSONDecodeError as error:
            raise ValueError(
                f"Invalid diagnostic JSON: {error}"
            ) from error

    if not isinstance(parsed, dict):
        raise ValueError(
            "Diagnostic response must be a JSON object."
        )

    anomaly_level = str(
        parsed.get(
            "anomaly_level",
            "LOW",
        )
    ).upper().strip()

    allowed_levels = {
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
    }

    if anomaly_level not in allowed_levels:
        anomaly_level = "LOW"

    reason = parsed.get(
        "reason",
        "",
    )

    if not isinstance(reason, str):
        reason = str(reason)

    evidence = parsed.get(
        "evidence",
        [],
    )

    if isinstance(evidence, str):
        evidence = [evidence]

    if not isinstance(evidence, list):
        evidence = [str(evidence)]

    evidence = [
        str(item)
        for item in evidence
    ]

    return {
        "anomaly_level": anomaly_level,
        "reason": reason,
        "evidence": evidence,
    }


# ============================================================
# DIAGNOSTIC RESPONSE
# ============================================================

@dataclass
class LocalDiagnosticResponse:
    anomaly_level: Optional[str]
    reason: str
    evidence: Sequence[str]
    raw_response: str
    parse_error: Optional[str]
    inference_seconds: float


# ============================================================
# LOCAL QWEN MODEL
# ============================================================

class LocalGGUFDiagnosticModel:
    """
    Real local Qwen2.5-1.5B GGUF implementation for Level-2 diagnosis.

    The GGUF model is loaded once and reused for subsequent requests.
    """

    def __init__(
        self,
        model_path: Path,
        max_tokens: int = 256,
        llm_loader: Callable[
            [Path],
            Any
        ] = load_llama,
    ) -> None:

        self.model_path = Path(
            model_path
        )

        self.max_tokens = int(
            max_tokens
        )

        started = time.perf_counter()

        self._llm = llm_loader(
            self.model_path
        )

        self.model_load_seconds = (
            time.perf_counter()
            - started
        )

        self.model_calls = 0
        self.total_inference_seconds = 0.0

        self.model_name = (
            "LOCAL QWEN2.5-1.5B-INSTRUCT "
            "GGUF DIAGNOSTIC MODEL"
        )

    # --------------------------------------------------------
    # Feature diagnosis
    # --------------------------------------------------------

    def diagnose_features(
        self,
        features: Mapping[str, Any],
        reference_statistics: Mapping[str, Any],
        level1_context: Optional[
            Mapping[str, Any]
        ] = None,
    ) -> LocalDiagnosticResponse:

        prompt = build_diagnostic_prompt(
            features,
            reference_statistics,
            level1_context,
        )

        started = time.perf_counter()

        raw_response = request_qwen(
            self._llm,
            prompt,
            self.max_tokens,
        )

        elapsed = (
            time.perf_counter()
            - started
        )

        self.model_calls += 1

        self.total_inference_seconds += elapsed

        try:

            parsed = parse_diagnostic_json(
                raw_response
            )

            return LocalDiagnosticResponse(
                anomaly_level=parsed[
                    "anomaly_level"
                ],
                reason=parsed[
                    "reason"
                ],
                evidence=parsed[
                    "evidence"
                ],
                raw_response=raw_response,
                parse_error=None,
                inference_seconds=elapsed,
            )

        except Exception as error:

            return LocalDiagnosticResponse(
                anomaly_level=None,
                reason=(
                    "Qwen response could not be "
                    "parsed as valid diagnostic JSON."
                ),
                evidence=[],
                raw_response=raw_response,
                parse_error=str(error),
                inference_seconds=elapsed,
            )

    # --------------------------------------------------------
    # Experiment / pipeline adapter
    # --------------------------------------------------------

    def diagnose(
        self,
        window_data: pd.DataFrame,
        context: Mapping[str, Any],
    ):
        """
        Adapt the BatteryIQ experiment window to Level-2.

        Required:
            context["baseline"]

        Optional Level-1 evidence:
            anomaly_score
            suspicious
            triggered_features
            feature_values
            deviations
        """

        baseline = context.get(
            "baseline"
        )

        if not isinstance(
            baseline,
            BatteryBaseline,
        ):
            raise ValueError(
                "LocalGGUFDiagnosticModel requires "
                "context['baseline']."
            )

        features = extract_window_features(
            window_data
        )

        reference_statistics = (
            baseline_reference_statistics(
                baseline
            )
        )

        level1_context = {
            "anomaly_score": context.get(
                "anomaly_score"
            ),

            "suspicious": context.get(
                "suspicious"
            ),

            "triggered_features": context.get(
                "triggered_features",
                [],
            ),

            "feature_values": context.get(
                "feature_values",
                {},
            ),

            "deviations": context.get(
                "deviations",
                {},
            ),
        }

        response = self.diagnose_features(
            features,
            reference_statistics,
            level1_context,
        )

        # Import lazily to avoid module-level
        # circular dependency.
        from .experiment import DiagnosticResult

        return DiagnosticResult(
            anomaly_detected=(
                response.anomaly_level
                is not None
            ),

            anomaly_score=None,

            severity=(
                response.anomaly_level
                or "UNPARSEABLE"
            ),

            confidence=None,

            model_name=self.model_name,

            reason=response.reason,

            evidence=response.evidence,

            raw_response=response.raw_response,

            json_parsed=(
                response.parse_error
                is None
            ),

            json_parse_error=(
                response.parse_error
            ),

            inference_seconds=(
                response.inference_seconds
            ),
        )


def diagnose(window: pd.DataFrame) -> Dict[str, Any]:
    """Deterministic placeholder diagnosis for a triggered window."""
    return {
        "fault_type": "PLACEHOLDER_ANOMALY",
        "severity": "MEDIUM",
        "confidence": 0.5,
    }


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "diagnose",
    "BatteryBaseline",
    "Callable",
    "Dict",
    "LEVEL2_FEATURE_NAMES",
    "LocalDiagnosticResponse",
    "LocalGGUFDiagnosticModel",
    "Mapping",
    "Optional",
    "Path",
    "Sequence",
    "annotations",
    "baseline_reference_statistics",
    "build_diagnostic_prompt",
    "dataclass",
    "extract_window_features",
    "json",
    "load_llama",
    "parse_diagnostic_json",
    "pd",
    "request_qwen",
    "time",
    "validate_level2_features",
]