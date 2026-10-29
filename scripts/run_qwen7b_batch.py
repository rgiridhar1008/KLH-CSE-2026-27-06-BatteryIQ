import argparse
import sys
import pandas as pd
from pathlib import Path

# Ensure src is in pythonpath
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from batteryiq.batch_experiment import run_batch_experiment

def main():
    parser = argparse.ArgumentParser(description="BatteryIQ Qwen 7B Batch Experiment")
    parser.add_argument("--input", required=True, help="Path to input CSV file")
    parser.add_argument("--max-windows", default="10", help="Max windows to evaluate (int or 'all')")
    parser.add_argument("--selection", default="chronological", choices=["chronological", "highest_score", "spread"], help="Window selection mode")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)

    print("========================================")
    print("BatteryIQ Qwen 7B Batch Experiment")
    print("========================================")
    print(f"Dataset:\n{input_path.name}\n")

    df = pd.read_csv(input_path)

    print("Evaluating windows and running Ollama... this may take a while.\n")
    
    result = run_batch_experiment(
        df=df,
        filename=input_path.name,
        max_windows=args.max_windows,
        selection_mode=args.selection,
        output_dir=str(ROOT / "data" / "processed" / "batteryiq_results" / "qwen7b_batch")
    )
    
    if not result.get("success"):
        print("Experiment failed!")
        sys.exit(1)
        
    exp = result["experiment"]
    
    print("\nTotal rows:")
    print(exp["total_rows"])
    print("\nTotal windows:")
    print(exp["total_windows"])
    print("\nSuspicious windows:")
    print(exp["suspicious_windows"])
    print("\nSelected Qwen windows:")
    print(exp["selected_windows"])
    print("\nScreening AI avoidance:")
    print(f"{exp['ai_avoidance_percent']}%")
    print("\nExperiment complete.")
    print(f"\nAverage Qwen inference:\n{exp['average_inference_time']} s")
    print(f"\nAverage DDP retention:\n{exp['average_ddp_retention']}%")
    print("\nResults saved to:")
    print(str(ROOT / "data" / "processed" / "batteryiq_results" / "qwen7b_batch"))

if __name__ == "__main__":
    main()
