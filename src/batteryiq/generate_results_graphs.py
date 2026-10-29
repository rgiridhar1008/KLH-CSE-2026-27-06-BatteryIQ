import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================
# BatteryIQ Results Graph Generator
# ============================================================

# Always save relative to D:\BatteryIQ
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "results_graphs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("Saving graphs to:")
print(OUTPUT_DIR)
print()


# ============================================================
# ACTUAL BATTERYIQ RESULTS
# ============================================================

windows = list(range(1, 81))

anomaly_scores = [
    0.6002, 0.5499, 0.5831, 0.5412, 0.4187,
    0.3098, 0.3599, 0.2811, 0.3413, 0.3545,
    0.2696, 0.2975, 0.4604, 0.3763, 0.3682,
    0.2826, 0.2645, 0.3255, 0.3947, 0.4400,
    0.5869, 0.6737, 0.7358, 0.8605, 0.9360,
    0.9416, 0.8626, 0.9464, 0.5954, 0.4101,
    0.4514, 0.3701, 0.4899, 0.5681, 0.5136,
    0.4780, 0.5034, 0.6055, 0.7838, 0.8694,
    1.2506, 1.1147, 1.0254, 1.1725, 6.2322,
    6.9974, 6.9391, 7.1147, 7.3415, 7.5615,
    7.7697, 7.8515, 7.8366, 8.1538, 8.3548,
    8.3220, 8.3384, 8.7362, 5.4012, 2.7770,
    2.4170, 2.8419, 3.9311, 3.7380, 3.7124,
    3.8104, 3.8417, 3.9879, 3.9131, 3.9128,
    3.9654, 3.9533, 3.9871, 4.3200, 3.7689,
    2.2635, 9.5157, 7.3426, 7.9259, 7.9365
]


# ============================================================
# 1. ANOMALY SCORE GRAPH
# ============================================================

plt.figure(figsize=(12, 6))

plt.plot(
    windows,
    anomaly_scores,
    marker="o",
    markersize=3,
    linewidth=2
)

plt.axvline(
    x=40.5,
    linestyle="--",
    linewidth=2,
    label="Suspicious windows begin"
)

plt.xlabel("Window Number")
plt.ylabel("Anomaly Score")

plt.title(
    "BatteryIQ - Level-1 Anomaly Score Across 80 Windows",
    fontweight="bold"
)

plt.grid(True, alpha=0.3)
plt.legend()

plt.tight_layout()

file1 = OUTPUT_DIR / "01_anomaly_score.png"

plt.savefig(
    file1,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print(f"Created: {file1}")


# ============================================================
# 2. AI CALLS VS AI AVOIDED
# ============================================================

categories = [
    "AI Calls",
    "AI Calls Avoided"
]

values = [
    40,
    40
]

plt.figure(figsize=(8, 6))

bars = plt.bar(
    categories,
    values,
    width=0.55
)

plt.ylabel("Number of Windows")

plt.title(
    "BatteryIQ - Event-Triggered AI Usage",
    fontweight="bold"
)

plt.ylim(0, 50)

plt.grid(
    axis="y",
    alpha=0.3
)

for bar, value in zip(bars, values):
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        value + 1,
        str(value),
        ha="center",
        fontweight="bold"
    )

plt.text(
    0.5,
    44,
    "AI Avoidance = 50%",
    ha="center",
    fontweight="bold"
)

plt.tight_layout()

file2 = OUTPUT_DIR / "02_ai_calls_vs_avoided.png"

plt.savefig(
    file2,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print(f"Created: {file2}")


# ============================================================
# 3. FEATURE DEVIATIONS - WINDOW 41
# ============================================================

features = [
    "Voltage",
    "Current",
    "Temperature"
]

deviations = [
    1.7533,
    1.3927,
    0.6058
]

plt.figure(figsize=(8, 6))

bars = plt.bar(
    features,
    deviations,
    width=0.55
)

plt.ylabel("Deviation")

plt.title(
    "BatteryIQ - Level-1 Feature Deviations\nWindow 41 (Rows 2000-2049)",
    fontweight="bold"
)

plt.grid(
    axis="y",
    alpha=0.3
)

for bar, value in zip(bars, deviations):
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        value + 0.05,
        f"{value:.4f}",
        ha="center",
        fontweight="bold"
    )

plt.tight_layout()

file3 = OUTPUT_DIR / "03_feature_deviations.png"

plt.savefig(
    file3,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print(f"Created: {file3}")


# ============================================================
# 4. DDP DATA REDUCTION
# ============================================================

categories = [
    "Original Rows",
    "Retained Rows"
]

values = [
    50,
    2
]

plt.figure(figsize=(8, 6))

bars = plt.bar(
    categories,
    values,
    width=0.55
)

plt.ylabel("Number of Rows")

plt.title(
    "BatteryIQ - DDP Adaptive Downsampling\nWindow 41",
    fontweight="bold"
)

plt.ylim(0, 60)

plt.grid(
    axis="y",
    alpha=0.3
)

for bar, value in zip(bars, values):
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        value + 1.5,
        str(value),
        ha="center",
        fontweight="bold"
    )

plt.text(
    0.5,
    55,
    "Retention = 4%  |  Data Reduction = 96%",
    ha="center",
    fontsize=10.5
)

plt.tight_layout()

file4 = OUTPUT_DIR / "04_ddp_data_reduction.png"

plt.savefig(
    file4,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print(f"Created: {file4}")


# ============================================================
# 5. DDP CLASSIFICATION
# ============================================================

categories = [
    "HIGH",
    "MID",
    "LOW"
]

values = [
    0,
    0,
    2
]

plt.figure(figsize=(8, 6))

bars = plt.bar(
    categories,
    values,
    width=0.55
)

plt.ylabel("Retained Rows")

plt.title(
    "BatteryIQ - DDP Classification\nWindow 41",
    fontweight="bold"
)

plt.ylim(0, 3)

plt.grid(
    axis="y",
    alpha=0.3
)

for bar, value in zip(bars, values):
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        value + 0.05,
        str(value),
        ha="center",
        fontweight="bold"
    )

plt.tight_layout()

file5 = OUTPUT_DIR / "05_ddp_classification.png"

plt.savefig(
    file5,
    dpi=300,
    bbox_inches="tight"
)

plt.close()

print(f"Created: {file5}")


# ============================================================
# DONE
# ============================================================

print()
print("=" * 60)
print("BATTERYIQ GRAPHS GENERATED SUCCESSFULLY")
print("=" * 60)
print()
print(f"Folder: {OUTPUT_DIR}")
print()
print("Files:")
print("  1. 01_anomaly_score.png")
print("  2. 02_ai_calls_vs_avoided.png")
print("  3. 03_feature_deviations.png")
print("  4. 04_ddp_data_reduction.png")
print("  5. 05_ddp_classification.png")
print()