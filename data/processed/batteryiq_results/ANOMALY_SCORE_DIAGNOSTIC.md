# Anomaly-score diagnostic

## Scope and method

This report first records the original (legacy) 760-window diagnostic that
identified the normalization problem, then records the approved corrected
rerun on the same ten raw files. Sections 1–5 describe the original behavior;
the corrected implementation and before/after comparison are in section 6.
No raw data or DDP logic was changed.

The ten files contain battery 01 (31,960 rows across eight files) and battery
02 (8,000 rows across two files). Each battery baseline uses its first 1,000
concatenated rows; those rows are excluded from scoring.

## 1. Score distribution

| Statistic | Anomaly score |
| --- | ---: |
| Windows | 760 |
| Minimum | 0.369721 |
| Maximum | 4,959.013111 |
| Mean | 68.311707 |
| Median / 50th percentile | 9.563321 |
| Sample standard deviation | 267.711675 |
| 75th percentile | 14.070068 |
| 90th percentile | 204.490138 |
| 95th percentile | 351.912001 |
| 97.5th percentile | 482.804861 |
| 99th percentile | 832.044157 |
| 99.5th percentile | 1,532.556284 |
| 99.9th percentile | 3,636.415480 |

| Condition | Windows |
| --- | ---: |
| Score > 1 | 697 |
| Score > 2 | 504 |
| Score > 3 | 489 |
| Score > 5 | 483 |
| Score > 10 | 377 |
| Score > 50 | 126 |
| Score > 100 | 104 |
| Score > 1,000 | 7 |

The mean is about 7.1 times the median and the maximum is about 519 times the
median. This is a strongly right-skewed distribution; it is not suitable for
using the mean as a typical score summary.

## 2. Feature contributions

The CSV contains four actual scoring components. `deviation_voltage` averages
the normalized `V_mean` and `V_std` deviations; `deviation_voltage_spread` is
the normalized `V_spread` deviation; `deviation_current` averages `I_mean`,
`I_std`, and `I_rate`; and `deviation_temperature` averages `T_mean`, `T_std`,
`T_spread`, and `T_rate`. The final score is the equally weighted mean of these
four components.

| Scoring component | Min | Median | Mean | 95th | 99th | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `deviation_voltage` | 0.383433 | 3.511217 | 4.330758 | 9.051993 | 37.801546 | 48.072654 |
| `deviation_voltage_spread` | 0.008760 | 0.787515 | 246.207053 | 1,347.066800 | 3,302.440040 | 19,805.982700 |
| `deviation_current` | 0.330878 | 20.238071 | 20.192295 | 46.223558 | 49.165888 | 57.235596 |
| `deviation_temperature` | 0.279345 | 1.855240 | 2.516722 | 6.166736 | 6.903241 | 7.304698 |

`deviation_voltage_spread` is the only component with a very large right
tail. It provides 61.551763 score points on average (246.207053 / 4), or about
90.1% of the overall mean score. The concentration is battery-specific:

| Battery | Mean score | Mean voltage-spread deviation | Score contribution from voltage spread | Share of mean score |
| --- | ---: | ---: | ---: | ---: |
| 01 | 7.211629 | 1.678452 | 0.419613 | 5.8% |
| 02 | 338.897766 | 1,329.119430 | 332.279857 | 98.0% |

The window feature distributions below provide the corresponding CSV columns.
They describe the 50-row window summaries, not individual raw samples.

| Feature | Mean | Median | 95th | 99th | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| `V_mean` | 3.315294 | 3.333071 | 3.394010 | 3.407233 | 3.427475 |
| `V_std` | 0.001310 | 0.000947 | 0.002008 | 0.017993 | 0.022700 |
| `V_spread` | 0.003946 | 0.002870 | 0.006123 | 0.055863 | 0.071560 |
| `V_rate` | 0.001057 | 0.000477 | 0.004557 | 0.005233 | 0.006870 |
| `I_mean` | 1.714960 | -42.160945 | 130.475153 | 133.608396 | 136.214044 |
| `I_std` | 8.471010 | 3.223308 | 27.968117 | 77.107352 | 105.248160 |
| `I_rate` | 6.606754 | 3.102026 | 29.120896 | 32.856546 | 34.346960 |
| `T_mean` | 33.299836 | 32.000000 | 40.229125 | 41.412500 | 42.175000 |
| `T_std` | 0.473444 | 0.353765 | 1.363791 | 1.590125 | 1.674452 |
| `T_spread` | 1.196316 | 1.000000 | 3.753000 | 4.208200 | 4.840000 |
| `T_rate` | 0.010865 | 0.007653 | 0.033163 | 0.095102 | 0.155612 |

`V_rate` is recorded but is not included in `deviation_voltage`; the voltage
component uses only `V_mean` and `V_std`.

## 3. Baseline normalization and numerical stability

`construct_baseline` in `src/batteryiq/baseline.py` builds baseline feature
means from the first 1,000 rows. Most scales are `1.4826 * MAD` of the
per-row feature. If that value is at most `1e-12`, `_robust_scale` falls back
to the feature mean and applies a `1e-6` lower floor. `_normalised_deviation`
then calculates `abs(window_value - baseline_reference) / max(abs(scale),
1e-6)`.

The important scales are:

| Battery | `V_mean` scale | `V_std` scale | `V_spread` scale | Current scale | `T_mean` scale |
| --- | ---: | ---: | ---: | ---: | ---: |
| 01 | 0.009636826 | 0.000250902 | 0.001481859 | 1.334559425 | 0.370650 |
| 02 | 0.009358931 | 0.000164403 | **0.000001** | 1.334559425 | 0.370650 |

Battery 02's baseline `V_spread` has mean 0.002793995 and ordinary temporal
standard deviation 0.000547600, but its MAD-derived scale is only
0.00000014826. It is raised only to the `1e-6` floor. This happens because the
quantized per-row spread values cluster very tightly around the median, even
though less-common values enlarge the ordinary standard deviation. The scoring
denominator is therefore about 548 times smaller than the ordinary baseline
standard deviation and about 2,794 times smaller than the baseline mean.

This is not a zero-division failure: every component is finite for all 760
windows. It is a numerical-scale instability for a quantized feature. A real
increase in raw voltage spread is consequently amplified to a score component
whose magnitude is not comparable with the other three components.

There are also feature/reference mismatches in the present implementation:

- `V_rate` is extracted but not scored.
- `I_rate` is compared with the `current_std` reference and a current-amplitude
  scale; no baseline rate feature is constructed.
- `T_rate` is compared with the `temperature_spread` reference and scale; no
  baseline temperature-rate feature is constructed.

These issues do not create the 4,959 maximum, but mean that rate components
are not normalized against like-for-like baseline statistics.

## 4. Maximum-score trace

| Field | Value |
| --- | --- |
| Source file | `real_world_02-03/battery_02_cells_009-016_t_04000-07999.csv` |
| Battery ID | 02 |
| Start / end sample | 7250 / 7299 |
| Local raw-row indices in source file | 3250 / 3299 |
| Anomaly score | 4,959.013111 |
| Triggered features | `voltage`, `voltage_spread`, `current`, `temperature` |

The component calculation for this window is:

| Component | Value |
| --- | ---: |
| Voltage | 23.759688 |
| Voltage spread | **19,805.982700** |
| Current | 4.235196 |
| Temperature | 2.074862 |
| Equal-weight mean | **4,959.013111** |

Its `V_spread` window mean is 0.022599978, versus baseline reference
0.002793995. Dividing the 0.019805983 difference by the 0.000001 scale gives
19,805.982700. That single component contributes 4,951.495675 of the final
score; the other three together contribute 7.517436.

The inspected raw rows contain eight voltage columns, eight temperature
columns, and `cur`. Their observed ranges are:

| Signal | Maximum-score window (50 raw rows) | Battery-02 baseline (1,000 raw rows) |
| --- | --- | --- |
| All cell-voltage values | 3.345000–3.455000 | 3.207000–3.344000 |
| Row-mean voltage | 3.358125–3.438625 | 3.207625–3.342125 |
| Per-row voltage spread | 0.013000–0.035000 | 0.001000–0.004000 |
| Current | -43.199950–0.000000 | -46.099854–0.000000 |
| All temperature values | 26.000000–30.000000 | 28.000000–34.000000 |
| Row-mean temperature | 27.125000–29.000000 | 29.125000–34.000000 |
| Per-row temperature spread | 2.000000–3.000000 | 0.000000–4.000000 |

Thus the raw window has a materially higher voltage spread than the initial
baseline, so the underlying feature change is present in the data. The
extreme *score magnitude*, however, is primarily the tiny denominator, not a
raw signal change of a comparable 19,806-unit magnitude. This diagnostic makes
no safety or physical-fault claim.

## 5. Baseline quality

The table gives the baseline signal mean and temporal standard deviation of
the 1,000 row-level means. The parenthetical `V_std` and `T_std` values are
the implementation's different features: mean within-row cell/sensor standard
deviation, rather than temporal standard deviation of the mean.

| Battery | Baseline size | Voltage mean / temporal std (`V_std`) | Current mean / std | Temperature mean / temporal std (`T_std`) |
| --- | ---: | --- | --- | --- |
| 01 | 1,000 / 1,000 requested | 3.316057 / 0.028154 (0.000671) | -42.853252 / 1.743409 | 31.965250 / 1.104768 (0.270739) |
| 02 | 1,000 / 1,000 requested | 3.317326 / 0.027840 (0.000978) | -42.853252 / 1.743409 | 30.087250 / 1.253566 (1.167540) |

Both baselines have the configured number of samples, but their first 1,000
rows are not representative of the later data's operating range:

| Battery | Later current mean / std | Later temperature-mean mean / std | Later voltage-spread mean / std |
| --- | --- | --- | --- |
| 01 | 1.385824 / 90.717094 | 33.706189 / 3.682351 | 0.003922 / 0.010170 |
| 02 | 2.419964 / 76.083163 | 31.476518 / 3.669736 | 0.004057 / 0.002762 |

For example, both baseline current means are -42.853252, whereas subsequent
data spans charging/discharging values and has much larger temporal variation.
The baseline is adequate in count but state-limited: it represents the earliest
portion, not the full range seen later. This is an observation about
representativeness, not a conclusion that the earliest data are invalid.

## 6. Corrected normalization and rerun

The approved implementation changes only `src/batteryiq/` and its supporting
configuration, tests, documentation, and comparison script. DDP equations,
DDP defaults, window size/step, configured thresholds, event-policy semantics,
and raw data are unchanged.

### Exact scale formula

For every stored baseline feature, the corrected deterministic scale is:

```text
robust_scale       = 1.4826 * median(abs(feature_value - median(feature_value)))
conventional_scale = population_standard_deviation(feature_value)
observed_scale     = max(robust_scale, conventional_scale)
scale              = observed_scale if observed_scale is nonzero; otherwise 1e-6
```

The `1e-6` value is therefore reached only when both observed-variation
estimates are zero (or numerically zero), not merely because MAD is small. The
formula selects the larger observed variation so a quantized nonzero MAD cannot
collapse the denominator below the feature's conventional baseline variation.
It is a deterministic stability policy, not a tuning step for a target
inference-avoidance rate.

For the original battery-02 voltage-spread baseline, this changes the effective
scale from `0.000001` to its observed conventional variation (about
`0.000547`), preventing the former 19,805.98 normalized component.

### Matching rate baselines and components

Baseline construction now stores `voltage_rate`, `current_rate`, and
`temperature_rate`. Each is the mean/scaled distribution of absolute adjacent
changes in the same row-level signal that the window feature uses. Screening
now compares every scored value with the baseline feature of the same name:

- Voltage: `V_mean`, `V_std`, `V_spread`, and `V_rate`.
- Current: `I_mean`, `I_std`, and `I_rate`.
- Temperature: `T_mean`, `T_std`, `T_spread`, and `T_rate` when temperature is
  available.

`V_rate` is now included in the voltage component. There are three transparent
components—voltage, current, and temperature—and their configured positive
weights are normalized over the components available in a window. The default
baseline configuration is explicitly `strategy: initial`, using only the
earliest 1,000 rows; no adaptive or future-data baseline was introduced.

### Before/after score comparison

The comparison was regenerated by
`scripts/compare_anomaly_scores.py --max-files 10`, which reproduces the
legacy calculation and evaluates the corrected calculation on the identical
ten files and 760 windows.

| Statistic | Original / legacy | Corrected |
| --- | ---: | ---: |
| Maximum | 4,959.013111 | 19.154387 |
| Mean | 68.311707 | 6.217204 |
| Median | 9.563321 | 6.111324 |
| 95th percentile | 351.912001 | 13.526555 |
| 99th percentile | 832.044157 | 16.599766 |

| Component | Legacy mean / max | Corrected mean / max |
| --- | --- | --- |
| Voltage | 4.330758 / 48.072654 | 1.906475 / 28.519000 |
| Voltage spread (separate legacy component only) | 246.207053 / 19,805.982700 | Included within voltage |
| Current | 20.192295 / 57.235596 | 15.574546 / 44.071157 |
| Temperature | 2.516722 / 7.304698 | 1.170590 / 3.320896 |

Lower numerical scores do not, by themselves, establish better anomaly
detection. They demonstrate that the former quantized-voltage-spread
amplification no longer dominates the scale.

### Corrected trigger and threshold outputs

With the unchanged configured trigger threshold of 1.0, the corrected rerun
has 443 triggered windows, 317 skipped windows, and 41.710526% inference
avoidance. This records the result of the unchanged threshold under corrected
normalization; it is not a recommendation to retain, change, or select that
threshold.

| Exploratory threshold | Triggered | Skipped | Inference avoidance |
| ---: | ---: | ---: | ---: |
| 0.5 | 681 | 79 | 10.394737% |
| 1.0 | 443 | 317 | 41.710526% |
| 1.5 | 428 | 332 | 43.684211% |
| 2.0 | 420 | 340 | 44.736842% |
| 2.5 | 417 | 343 | 45.131579% |
| 3.0 | 415 | 345 | 45.394737% |

No final trigger threshold is selected or recommended.

### Remaining limitations

- The initial 1,000-row baseline remains state-limited and is not necessarily
  representative of later operating conditions; no future data are used to
  compensate for that limitation.
- Taking the larger of robust and conventional scale protects against
  quantization collapse, but the conventional standard deviation can itself be
  affected by unusual values within the baseline. Baseline-quality review is
  still required.
- A truly constant baseline feature still uses the numerical `1e-6` floor;
  later variation in such a feature should be interpreted with the baseline's
  measurement resolution in mind.
- The dataset has no fault labels. These scores do not validate fault
  detection, establish physical battery faults, or support a safety claim.
