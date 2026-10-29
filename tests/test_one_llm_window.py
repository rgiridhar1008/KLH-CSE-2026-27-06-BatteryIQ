from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "test_one_llm_window.py"
SPEC = importlib.util.spec_from_file_location("test_one_llm_window", SCRIPT_PATH)
assert SPEC and SPEC.loader
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


class MockLlama:
    def __init__(self) -> None:
        self.calls = []

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return {"choices": [{"message": {"content": '{"anomaly_level":"LOW","reason":"Descriptive feature variation only.","evidence":["V_mean supplied","I_rate supplied"]}'}}]}


def test_one_window_smoke_uses_all_level2_features_and_mocked_llm(tmp_path):
    frame = pd.DataFrame({
        **{f"vol_{number}": [3.30 + number * 0.001 + row * 0.0001 for row in range(50)] for number in range(1, 9)},
        **{f"temp_{number}": [30.0 + number * 0.1 for _ in range(50)] for number in range(1, 9)},
        "cur": [float(row) for row in range(50)],
    })
    csv_path = tmp_path / "one_window.csv"
    frame.to_csv(csv_path, index=False)
    mock = MockLlama()
    result = smoke.run_smoke_test(
        input_file=csv_path,
        model_path=tmp_path / "unused.gguf",
        window_start=0,
        window_size=50,
        max_tokens=128,
        llm_loader=lambda _: mock,
    )

    assert tuple(result["features"]) == smoke.FEATURE_NAMES
    assert result["window_start_row"] == 0
    assert result["window_end_row"] == 49
    assert result["parsed_response"]["anomaly_level"] == "LOW"
    assert result["parse_error"] is None
    assert mock.calls[0]["response_format"] == {"type": "json_object"}
    prompt = mock.calls[0]["messages"][0]["content"]
    assert "no explicit fault labels" in prompt
    assert "NOT physical-fault severity" in prompt


def test_invalid_model_json_is_reported_without_crashing():
    try:
        smoke.parse_diagnostic_json("not-json")
    except ValueError as error:
        assert "No JSON object" in str(error)
    else:
        raise AssertionError("Invalid model output must report a parsing failure.")
