import json
import urllib.request
import urllib.error
import time
import re
from typing import Dict, Any

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
OLLAMA_MODEL = "qwen2.5:7b"

SYSTEM_PROMPT = """You are the Level-2 diagnostic model of BatteryIQ.

The Level-1 screening layer has already identified this battery window as suspicious.

You must analyze the supplied Level-1 evidence, DDP-reduced data, and baseline/reference information.

Your task is to provide a second-level interpretation.

Do not ignore the Level-1 trigger.

Do not automatically classify the event as HIGH merely because the Level-1 anomaly score is high.

Do not automatically classify it as LOW merely because one individual feature is within its reference range.

Consider all supplied evidence.

Distinguish:
1. evidence supporting the suspicious event
2. evidence contradicting the event
3. insufficient evidence

Do not invent a physical battery fault.

If a specific fault cannot be established from the supplied evidence, explicitly say so.

Return only valid JSON."""

JSON_FORMAT = """
{
  "anomaly_level": "LOW|MEDIUM|HIGH|CRITICAL|UNKNOWN",
  "fault_type": "string",
  "diagnosis": "string",
  "reason": "string",
  "evidence": [
    "string"
  ],
  "level1_consistency": "CONSISTENT|PARTIALLY_CONSISTENT|INCONSISTENT",
  "recommended_action": "MONITOR|WARNING|FURTHER_ANALYSIS|PROTECTION",
  "confidence": 0.0
}
"""

def check_ollama_status() -> Dict[str, Any]:
    """Check if Ollama and the required model are available."""
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                models = [m.get("name") for m in data.get("models", [])]
                if OLLAMA_MODEL in models:
                    return {
                        "available": True,
                        "runtime": "Ollama",
                        "model": OLLAMA_MODEL
                    }
                else:
                    return {
                        "available": False,
                        "runtime": "Ollama",
                        "model": OLLAMA_MODEL,
                        "error": f"Model {OLLAMA_MODEL} is not installed in Ollama."
                    }
            else:
                return {
                    "available": False,
                    "runtime": "Ollama",
                    "model": OLLAMA_MODEL,
                    "error": f"Ollama returned status {response.status}"
                }
    except Exception as e:
        return {
            "available": False,
            "runtime": "Ollama",
            "model": OLLAMA_MODEL,
            "error": f"Ollama is not running or connection failed: {e}"
        }

def parse_llm_json(raw_text: str) -> Dict[str, Any]:
    """Extract and parse JSON from the LLM response."""
    # Attempt to extract JSON from markdown code blocks
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if match:
        json_str = match.group(1)
    else:
        # Fallback to finding the first { and last }
        start = raw_text.find("{")
        end = raw_text.rfind("}")
        if start != -1 and end != -1 and end > start:
            json_str = raw_text[start:end + 1]
        else:
            json_str = raw_text
    
    try:
        parsed = json.loads(json_str)
        return parsed
    except json.JSONDecodeError:
        raise ValueError(f"Could not parse JSON from model response. Raw output: {raw_text}")

def run_ollama_diagnosis(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs the prompt, calls Ollama, and parses the response.
    """
    
    # 1. Format the input prompt
    user_prompt = f"""
LEVEL-1 SCREENING RESULT

Window:
Rows {context.get("window_start")}–{context.get("window_end")}

Anomaly score:
{context.get("anomaly_score")}

Suspicious:
{str(context.get("suspicious")).lower()}

Triggered features:
{json.dumps(context.get("triggered_features"), indent=2)}

Level-1 deviations:
{json.dumps(context.get("deviations"), indent=2)}

DDP-DOWNSAMPLED FEATURES:
Original Rows: {context.get("ddp_original_rows")}
Retained Rows: {context.get("ddp_retained_rows")} (Retention: {context.get("ddp_retention_percent")}%)
VDD Mean: {context.get("ddp_vdd_mean")}
CDD Mean: {context.get("ddp_cdd_mean")}
HIGH Priority Count: {context.get("ddp_high_count")}
MID Priority Count: {context.get("ddp_mid_count")}
LOW Priority Count: {context.get("ddp_low_count")}

BASELINE:
Baseline calculations exist and were used for these derivations.

Provide your diagnosis in exactly this JSON format:
{JSON_FORMAT}
"""

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "stream": False,
        "options": {
            "temperature": 0.0  # Keep it deterministic
        }
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=data, headers={"Content-Type": "application/json"})
    
    start_time = time.time()
    
    try:
        with urllib.request.urlopen(req, timeout=120.0) as response:
            result = json.loads(response.read().decode("utf-8"))
            
            inference_seconds = time.time() - start_time
            raw_content = result.get("message", {}).get("content", "")
            
            try:
                parsed_json = parse_llm_json(raw_content)
                
                # Fill in missing fields with null/defaults if needed, to adhere to contract
                return {
                    "anomaly_level": parsed_json.get("anomaly_level", "UNKNOWN"),
                    "fault_type": parsed_json.get("fault_type", "Unknown"),
                    "diagnosis": parsed_json.get("diagnosis", "No diagnosis provided"),
                    "reason": parsed_json.get("reason", "No reason provided"),
                    "evidence": parsed_json.get("evidence", []),
                    "level1_consistency": parsed_json.get("level1_consistency", "UNKNOWN"),
                    "confidence": parsed_json.get("confidence", 0.0),
                    "recommendation": parsed_json.get("recommended_action", parsed_json.get("recommendation", "No recommendation provided")),
                    "json_parsed": True,
                    "json_parse_error": None,
                    "inference_seconds": inference_seconds,
                    "raw_response": raw_content
                }
            except Exception as e:
                return {
                    "anomaly_level": "UNKNOWN",
                    "fault_type": None,
                    "diagnosis": None,
                    "reason": None,
                    "evidence": [],
                    "level1_consistency": None,
                    "confidence": 0.0,
                    "recommendation": None,
                    "json_parsed": False,
                    "json_parse_error": str(e),
                    "inference_seconds": inference_seconds,
                    "raw_response": raw_content
                }

    except urllib.error.URLError as e:
        # Connection error, timeout, etc.
        return {
            "anomaly_level": "UNKNOWN",
            "fault_type": None,
            "diagnosis": None,
            "reason": None,
            "evidence": [],
            "level1_consistency": None,
            "confidence": 0.0,
            "recommendation": None,
            "json_parsed": False,
            "json_parse_error": f"Ollama connection error: {e}",
            "inference_seconds": time.time() - start_time,
            "raw_response": ""
        }
    except Exception as e:
        return {
            "anomaly_level": "UNKNOWN",
            "fault_type": None,
            "diagnosis": None,
            "reason": None,
            "evidence": [],
            "level1_consistency": None,
            "confidence": 0.0,
            "recommendation": None,
            "json_parsed": False,
            "json_parse_error": f"Unexpected error: {e}",
            "inference_seconds": time.time() - start_time,
            "raw_response": ""
        }
