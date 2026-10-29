import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from batteryiq.baseline import construct_baseline, parse_battery_identity, normalise_input_columns
from batteryiq.screening import AnomalyScreeningConfig, evaluate_window, apply_event_policy
from batteryiq.ai.ollama_qwen import run_ollama_diagnosis
from ddp_downsampling.config import PipelineConfig
from ddp_downsampling.downsampling import downsample_dataframe

def select_windows(windows: List[Dict[str, Any]], max_windows: str, selection_mode: str) -> List[Dict[str, Any]]:
    suspicious = [w for w in windows if w["suspicious"]]
    
    if str(max_windows).lower() == "all":
        limit = len(suspicious)
    else:
        try:
            limit = int(max_windows)
        except ValueError:
            limit = len(suspicious)
    
    if limit >= len(suspicious):
        return suspicious
        
    if selection_mode == "highest_score":
        sorted_suspicious = sorted(suspicious, key=lambda x: x["anomaly_score"], reverse=True)
        return sorted_suspicious[:limit]
    elif selection_mode == "spread":
        indices = np.linspace(0, len(suspicious) - 1, limit, dtype=int)
        return [suspicious[i] for i in indices]
    else:
        # default: chronological
        return suspicious[:limit]


def run_batch_experiment(
    df: pd.DataFrame,
    filename: str,
    max_windows: str = "10",
    selection_mode: str = "chronological",
    output_dir: str = "data/processed/batteryiq_results/qwen7b_batch"
) -> Dict[str, Any]:
    
    # 1. Prepare df and identity
    df = normalise_input_columns(df)
    try:
        identity = parse_battery_identity(filename)
        battery_id = identity.battery_id
        directory = identity.directory
    except Exception:
        battery_id = "uploaded"
        directory = "frontend_upload"
        
    baseline = construct_baseline(df, directory=directory, battery_id=battery_id, baseline_samples=min(1000, len(df)))
    screening_config = AnomalyScreeningConfig()
    
    window_size = 50
    total_windows_count = len(df) // window_size
    
    # 2. Level-1 Screening all windows
    screening_results = []
    window_info = []
    for i in range(total_windows_count):
        start = i * window_size
        end = start + window_size
        window_df = df.iloc[start:end].copy()
        
        result = evaluate_window(window_df, baseline, screening_config)
        screening_results.append(result)
        
        window_info.append({
            "window": i,
            "start_row": start,
            "end_row": end - 1,
            "result_obj": result,
            "anomaly_score": float(result.anomaly_score),
            "df": window_df
        })
        
    # Apply policy
    triggers = apply_event_policy(screening_results, min_trigger_windows=1, cooldown_windows=0)
    for i, w in enumerate(window_info):
        w["suspicious"] = bool(triggers[i])
        
    suspicious_count = sum(1 for w in window_info if w["suspicious"])
    
    # 3. Select windows
    selected = select_windows(window_info, max_windows, selection_mode)
    
    # 4. Run DDP and Ollama Qwen
    results = []
    ddp_config = PipelineConfig()
    
    for w in selected:
        print(f"[Batch] Processing window {w['window']}...")
        ddp_res = downsample_dataframe(w["df"], ddp_config)
        downsampled_df = ddp_res.downsampled_df
        
        original_rows = len(w["df"])
        retained_rows = len(downsampled_df)
        retention_percent = (retained_rows / original_rows * 100) if original_rows > 0 else 0.0
        
        vdd_mean = float(ddp_res.vdd.mean()) if len(ddp_res.vdd) > 0 else 0.0
        cdd_mean = float(ddp_res.cdd.mean()) if len(ddp_res.cdd) > 0 else 0.0
        high_count = len(ddp_res.index_sets["high"])
        mid_count = len(ddp_res.index_sets["mid"])
        low_count = len(ddp_res.index_sets["low"])
        
        context = {
            "baseline": baseline,
            "battery_id": battery_id,
            "filename": filename,
            "window_start": w["start_row"],
            "window_end": w["end_row"],
            "anomaly_score": w["anomaly_score"],
            "suspicious": True,
            "triggered_features": list(w["result_obj"].triggered_features),
            "feature_values": dict(w["result_obj"].feature_values),
            "deviations": dict(w["result_obj"].deviations),
            "ddp_original_rows": original_rows,
            "ddp_retained_rows": retained_rows,
            "ddp_retention_percent": round(retention_percent, 2),
            "ddp_vdd_mean": round(vdd_mean, 6),
            "ddp_cdd_mean": round(cdd_mean, 6),
            "ddp_high_count": high_count,
            "ddp_mid_count": mid_count,
            "ddp_low_count": low_count,
        }
        
        ai_res = run_ollama_diagnosis(context)
        
        results.append({
            "window": w["window"],
            "start_row": w["start_row"],
            "end_row": w["end_row"],
            "level1": {
                "anomaly_score": w["anomaly_score"],
                "suspicious": True,
                "triggered_features": list(w["result_obj"].triggered_features),
                "deviations": dict(w["result_obj"].deviations)
            },
            "ddp": {
                "original_rows": original_rows,
                "retained_rows": retained_rows,
                "retention_percent": round(retention_percent, 2),
                "vdd_mean": round(vdd_mean, 6),
                "cdd_mean": round(cdd_mean, 6)
            },
            "ai_result": ai_res,
            "model": {
                "name": "Qwen2.5 7B",
                "runtime": "Ollama",
                "local": True
            },
            "inference_seconds": ai_res.get("inference_seconds", 0)
        })
        
    # 5. Calculate Metrics
    ai_calls = len(results)
    ai_calls_avoided = total_windows_count - suspicious_count
    overall_avoidance = (ai_calls_avoided / total_windows_count * 100) if total_windows_count > 0 else 0.0
    
    retentions = [r["ddp"]["retention_percent"] for r in results]
    inf_times = [r["inference_seconds"] for r in results]
    
    experiment_metrics = {
        "filename": filename,
        "total_rows": len(df),
        "total_windows": total_windows_count,
        "suspicious_windows": suspicious_count,
        "selected_windows": ai_calls,
        "ai_calls": ai_calls,
        "ai_calls_avoided": ai_calls_avoided,
        "ai_avoidance_percent": round(overall_avoidance, 2),
        "average_ddp_retention": round(float(np.mean(retentions)), 2) if retentions else 0.0,
        "median_ddp_retention": round(float(np.median(retentions)), 2) if retentions else 0.0,
        "min_ddp_retention": round(float(np.min(retentions)), 2) if retentions else 0.0,
        "max_ddp_retention": round(float(np.max(retentions)), 2) if retentions else 0.0,
        "average_inference_time": round(float(np.mean(inf_times)), 2) if inf_times else 0.0,
        "median_inference_time": round(float(np.median(inf_times)), 2) if inf_times else 0.0,
        "total_inference_time": round(float(np.sum(inf_times)), 2) if inf_times else 0.0,
        "json_success_rate": round(sum(1 for r in results if r["ai_result"].get("json_parsed")) / ai_calls * 100, 2) if ai_calls > 0 else 0.0
    }
    
    # 6. Save results
    out_p = Path(output_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    
    # Save JSON
    with open(out_p / "batch_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "experiment": experiment_metrics,
            "results": results
        }, f, indent=2)
        
    # Save CSV
    csv_rows = []
    for r in results:
        csv_rows.append({
            "window": r["window"],
            "start_row": r["start_row"],
            "end_row": r["end_row"],
            "level1_anomaly_score": r["level1"]["anomaly_score"],
            "level1_suspicious": r["level1"]["suspicious"],
            "triggered_features": ",".join(r["level1"]["triggered_features"]),
            "ddp_original_rows": r["ddp"]["original_rows"],
            "ddp_retained_rows": r["ddp"]["retained_rows"],
            "ddp_retention_percent": r["ddp"]["retention_percent"],
            "vdd_mean": r["ddp"]["vdd_mean"],
            "cdd_mean": r["ddp"]["cdd_mean"],
            "qwen_anomaly_level": r["ai_result"].get("anomaly_level", "UNKNOWN"),
            "qwen_fault_type": r["ai_result"].get("fault_type", ""),
            "qwen_diagnosis": r["ai_result"].get("diagnosis", ""),
            "qwen_reason": r["ai_result"].get("reason", ""),
            "qwen_consistency": r["ai_result"].get("level1_consistency", ""),
            "qwen_recommended_action": r["ai_result"].get("recommendation", ""),
            "qwen_confidence": r["ai_result"].get("confidence", 0.0),
            "qwen_json_parsed": r["ai_result"].get("json_parsed", False),
            "qwen_parse_error": r["ai_result"].get("json_parse_error", ""),
            "qwen_inference_seconds": r["inference_seconds"]
        })
    pd.DataFrame(csv_rows).to_csv(out_p / "batch_results.csv", index=False)
    
    # Save Summary MD
    with open(out_p / "batch_summary.md", "w", encoding="utf-8") as f:
        f.write("# BatteryIQ Qwen 7B Batch Experiment\n\n")
        f.write("## Metrics\n")
        f.write("| Metric | Result |\n")
        f.write("|---|---:|\n")
        f.write(f"| Total windows | {experiment_metrics['total_windows']} |\n")
        f.write(f"| Suspicious windows | {experiment_metrics['suspicious_windows']} |\n")
        f.write(f"| Normal windows | {experiment_metrics['ai_calls_avoided']} |\n")
        f.write(f"| Screening AI avoidance | {experiment_metrics['ai_avoidance_percent']}% |\n")
        f.write(f"| Qwen windows evaluated | {experiment_metrics['selected_windows']} |\n")
        f.write(f"| Average DDP retention | {experiment_metrics['average_ddp_retention']}% |\n")
        f.write(f"| Average Qwen inference | {experiment_metrics['average_inference_time']} s |\n")
        f.write(f"| JSON success rate | {experiment_metrics['json_success_rate']}% |\n")

    return {
        "success": True,
        "experiment": experiment_metrics,
        "results": results
    }
