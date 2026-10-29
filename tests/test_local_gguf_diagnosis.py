from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from batteryiq.diagnosis import (  # noqa: E402
    LEVEL2_FEATURE_NAMES,
    LocalGGUFDiagnosticModel,
    build_diagnostic_prompt,
)


class MockLlama:
    def __init__(self) -> None:
        self.calls = []

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return {"choices": [{"message": {"content": '{"anomaly_level":"LOW","reason":"Reference comparison is limited.","evidence":["V_mean reference supplied","I_rate reference supplied"]}'}}]}


def _features():
    return {name: float(index) for index, name in enumerate(LEVEL2_FEATURE_NAMES)}


def _references():
    return {name: {"reference": 0.0, "scale": 1.0} for name in LEVEL2_FEATURE_NAMES}


def test_local_gguf_uses_exact_level2_features_and_records_timing(tmp_path):
    mock = MockLlama()
    model = LocalGGUFDiagnosticModel(tmp_path / "unused.gguf", llm_loader=lambda _: mock)
    response = model.diagnose_features(_features(), _references())
    assert response.anomaly_level == "LOW"
    assert response.parse_error is None
    assert model.model_calls == 1
    assert model.total_inference_seconds >= 0.0
    assert mock.calls[0]["response_format"] == {"type": "json_object"}


def test_prompt_has_required_data_limits_and_reference_only_language():
    prompt = build_diagnostic_prompt(_features(), _references())
    assert "BatteryData has no explicit fault labels" in prompt
    assert "Do not invent fault classes" in prompt
    assert "Do not claim physical fault severity" in prompt
    assert "NOT physical-fault severity" in prompt
    assert "relative to the supplied baseline/reference statistics" in prompt
    assert "insufficient evidence" in prompt


def test_local_gguf_rejects_feature_sets_other_than_established_level2_features(tmp_path):
    model = LocalGGUFDiagnosticModel(tmp_path / "unused.gguf", llm_loader=lambda _: MockLlama())
    with pytest.raises(ValueError, match="exactly the eleven"):
        model.diagnose_features({"V_mean": 1.0}, _references())
