from pathlib import Path
import sys
import io

import pandas as pd

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware


# =========================================================
# PROJECT PATH
# =========================================================

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# =========================================================
# BATTERYIQ IMPORTS
# =========================================================

from batteryiq.baseline import (
    construct_baseline,
    parse_battery_identity,
    normalise_input_columns,
)

from batteryiq.screening import (
    AnomalyScreeningConfig,
    evaluate_window,
    apply_event_policy,
)

from batteryiq.ai.ollama_qwen import (
    check_ollama_status,
    run_ollama_diagnosis,
)

from batteryiq.batch_experiment import run_batch_experiment


# =========================================================
# DDP IMPORTS
# =========================================================

from ddp_downsampling.config import PipelineConfig
from ddp_downsampling.downsampling import downsample_dataframe


# =========================================================
# OLLAMA CONFIG
# =========================================================

import os

# =========================================================
# FASTAPI
# =========================================================

app = FastAPI(
    title="BatteryIQ API",
    description="BatteryIQ intelligent battery monitoring backend",
    version="1.0",
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "system": "BatteryIQ",
        "status": "running",
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy",
    }


# =========================================================
# AI STATUS
# =========================================================

@app.get("/ai/status")
def ai_status():
    return check_ollama_status()

# =========================================================
# LEVEL-1 ANALYSIS
# =========================================================

@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...)
):

    # -----------------------------------------------------
    # Read CSV
    # -----------------------------------------------------

    contents = await file.read()

    df = pd.read_csv(
        io.BytesIO(contents)
    )

    df = normalise_input_columns(df)


    # -----------------------------------------------------
    # Identify battery
    # -----------------------------------------------------

    try:

        identity = parse_battery_identity(
            file.filename
        )

        battery_id = identity.battery_id
        directory = identity.directory

    except Exception:

        battery_id = "uploaded"
        directory = "frontend_upload"


    # -----------------------------------------------------
    # Create baseline
    # -----------------------------------------------------

    baseline = construct_baseline(
        df,
        directory=directory,
        battery_id=battery_id,
        baseline_samples=min(
            1000,
            len(df)
        ),
    )


    # -----------------------------------------------------
    # Screening configuration
    # -----------------------------------------------------

    screening_config = (
        AnomalyScreeningConfig()
    )


    # -----------------------------------------------------
    # 50-row windows
    # -----------------------------------------------------

    window_size = 50

    total_windows = (
        len(df) // window_size
    )

    screening_results = []


    for i in range(total_windows):

        start = (
            i * window_size
        )

        end = (
            start + window_size
        )

        window = df.iloc[
            start:end
        ].copy()


        result = evaluate_window(
            window,
            baseline,
            screening_config,
        )


        screening_results.append(
            result
        )


    # -----------------------------------------------------
    # Event policy
    # -----------------------------------------------------

    triggers = apply_event_policy(
        screening_results,
        min_trigger_windows=1,
        cooldown_windows=0,
    )


    # -----------------------------------------------------
    # Counts
    # -----------------------------------------------------

    suspicious_windows = sum(
        bool(x)
        for x in triggers
    )

    ai_calls_avoided = (
        total_windows
        - suspicious_windows
    )


    # -----------------------------------------------------
    # Avoidance percentage
    # -----------------------------------------------------

    if total_windows > 0:

        inference_avoidance_percent = round(
            (
                ai_calls_avoided
                / total_windows
            )
            * 100,
            2,
        )

    else:

        inference_avoidance_percent = 0


    # -----------------------------------------------------
    # Window results
    # -----------------------------------------------------

    windows = []


    for index, (
        result,
        trigger
    ) in enumerate(
        zip(
            screening_results,
            triggers
        )
    ):

        start = (
            index
            * window_size
        )

        end = (
            start
            + window_size
            - 1
        )


        windows.append(
            {
                "window": index + 1,

                "start_row": start,

                "end_row": end,

                "suspicious": bool(
                    trigger
                ),

                "score": float(
                    result.anomaly_score
                ),
            }
        )


    # -----------------------------------------------------
    # Return Level-1 result
    # -----------------------------------------------------

    return {

        "filename": file.filename,

        "battery_id": battery_id,

        "total_rows": len(df),

        "total_windows": total_windows,

        "suspicious_windows": (
            suspicious_windows
        ),

        "ai_calls": suspicious_windows,

        "ai_calls_avoided": (
            ai_calls_avoided
        ),

        "inference_avoidance_percent": (
            inference_avoidance_percent
        ),

        "windows": windows,
    }


# =========================================================
# LEVEL-2 DIAGNOSIS
#
# Level-1
#     ↓
# Suspicious Window
#     ↓
# Real DDP
#     ↓
# Real Qwen2.5-1.5B
# =========================================================

@app.post("/diagnose")
async def diagnose(
    file: UploadFile = File(...),
    start_row: int = 0,
):

    global qwen_model


    # =====================================================
    # READ CSV
    # =====================================================

    contents = await file.read()

    df = pd.read_csv(
        io.BytesIO(contents)
    )

    df = normalise_input_columns(
        df
    )


    # =====================================================
    # VALIDATE WINDOW
    # =====================================================

    window_size = 50

    end_row = (
        start_row
        + window_size
    )


    if start_row < 0:

        return {

            "success": False,

            "error": (
                "start_row cannot be negative."
            ),
        }


    if end_row > len(df):

        return {

            "success": False,

            "error": (
                f"Invalid window range. "
                f"Requested rows {start_row} "
                f"to {end_row - 1}, "
                f"but CSV contains only "
                f"{len(df)} rows."
            ),
        }


    # -----------------------------------------------------
    # Extract window
    # -----------------------------------------------------

    window = df.iloc[
        start_row:end_row
    ].copy()


    # =====================================================
    # IDENTIFY BATTERY
    # =====================================================

    try:

        identity = parse_battery_identity(
            file.filename
        )

        battery_id = (
            identity.battery_id
        )

        directory = (
            identity.directory
        )

    except Exception:

        battery_id = "uploaded"

        directory = "frontend_upload"


    # =====================================================
    # CREATE BASELINE
    # =====================================================

    baseline = construct_baseline(
        df,
        directory=directory,
        battery_id=battery_id,
        baseline_samples=min(
            1000,
            len(df)
        ),
    )


    # =====================================================
    # LEVEL-1 SCREENING
    # =====================================================

    screening_config = (
        AnomalyScreeningConfig()
    )


    screening_result = (
        evaluate_window(
            window,
            baseline,
            screening_config,
        )
    )


    # =====================================================
    # REAL DDP
    # =====================================================

    ddp_config = PipelineConfig()


    ddp_result = (
        downsample_dataframe(
            window,
            ddp_config,
        )
    )


    # Actual DDP output
    downsampled_window = (
        ddp_result.downsampled_df
    )


    # =====================================================
    # DDP STATISTICS
    # =====================================================

    original_rows = len(
        window
    )

    retained_rows = len(
        downsampled_window
    )


    if original_rows > 0:

        retention_percent = (
            retained_rows
            / original_rows
        ) * 100

    else:

        retention_percent = 0.0


    # -----------------------------------------------------
    # VDD
    # -----------------------------------------------------

    if len(ddp_result.vdd) > 0:

        vdd_mean = float(
            ddp_result.vdd.mean()
        )

    else:

        vdd_mean = 0.0


    # -----------------------------------------------------
    # CDD
    # -----------------------------------------------------

    if len(ddp_result.cdd) > 0:

        cdd_mean = float(
            ddp_result.cdd.mean()
        )

    else:

        cdd_mean = 0.0


    # =====================================================
    # DDP COUNTS
    # =====================================================

    high_count = len(
        ddp_result.index_sets[
            "high"
        ]
    )

    mid_count = len(
        ddp_result.index_sets[
            "mid"
        ]
    )

    low_count = len(
        ddp_result.index_sets[
            "low"
        ]
    )


    # =====================================================
    # QWEN CONTEXT
    # =====================================================

    context = {
        "baseline": baseline,
        "battery_id": battery_id,
        "filename": file.filename,
        "window_start": start_row,
        "window_end": end_row - 1,

        # -------------------------------------------------
        # LEVEL-1 SCREENING EVIDENCE
        # -------------------------------------------------
        "anomaly_score": float(screening_result.anomaly_score),
        "suspicious": bool(screening_result.suspicious),
        "triggered_features": list(screening_result.triggered_features),
        "feature_values": dict(screening_result.feature_values),
        "deviations": dict(screening_result.deviations),

        # -------------------------------------------------
        # DDP
        # -------------------------------------------------
        "ddp_original_rows": original_rows,
        "ddp_retained_rows": retained_rows,
        "ddp_retention_percent": round(retention_percent, 2),
        "ddp_vdd_mean": round(vdd_mean, 6),
        "ddp_cdd_mean": round(cdd_mean, 6),
        "ddp_high_count": high_count,
        "ddp_mid_count": mid_count,
        "ddp_low_count": low_count,
    }

    # =====================================================
    # LOGGING
    # =====================================================

    if screening_result.suspicious:
        print(f"[BatteryIQ] Level-1 triggered window: {start_row}–{end_row - 1}")
    
    print("[BatteryIQ] DDP completed")
    print("[BatteryIQ] Sending diagnosis to Ollama")
    print("[BatteryIQ] Model: qwen2.5:7b")

    # =====================================================
    # REAL QWEN INFERENCE VIA OLLAMA
    # =====================================================

    ai_result = run_ollama_diagnosis(context)
    
    print("[BatteryIQ] Qwen response received")
    if ai_result.get("json_parsed"):
        print("[BatteryIQ] JSON diagnosis parsed successfully")

    # =====================================================
    # COMPLETE RESPONSE
    # =====================================================

    return {
        "success": True,
        "filename": file.filename,
        "battery_id": battery_id,

        "window_start": start_row,
        "window_end": end_row - 1,

        "screening": {
            "anomaly_score": float(screening_result.anomaly_score),
            "suspicious": bool(screening_result.suspicious),
            "triggered_features": list(screening_result.triggered_features),
            "feature_values": dict(screening_result.feature_values),
            "deviations": dict(screening_result.deviations),
            "available_components": list(screening_result.available_components),
        },

        "ddp": {
            "original_rows": original_rows,
            "retained_rows": retained_rows,
            "retention_percent": round(retention_percent, 2),
            "vdd_mean": round(vdd_mean, 6),
            "cdd_mean": round(cdd_mean, 6),
            "high_count": high_count,
            "mid_count": mid_count,
            "low_count": low_count,
        },

        "ai_result": ai_result,
        
        "model": {
            "name": "Qwen2.5 7B",
            "runtime": "Ollama",
            "local": True
        }
    }


# =========================================================
# BATCH EXPERIMENT
# =========================================================

from fastapi import Form

@app.post("/batch-diagnose")
async def batch_diagnose(
    file: UploadFile = File(...),
    max_windows: str = Form("10"),
    selection_mode: str = Form("chronological")
):
    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        
        result = run_batch_experiment(
            df=df,
            filename=file.filename,
            max_windows=max_windows,
            selection_mode=selection_mode,
            output_dir="data/processed/batteryiq_results/qwen7b_batch"
        )
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }
