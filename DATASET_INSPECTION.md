# BatteryData Dataset Label and Semantic Inspection

## Scope and method

This is an inspection-only report of the CSV files currently under `data/raw/`. All 600 CSV files were read. No raw file, pipeline module, DDP calculation, screening rule, risk policy, or model was modified. The optional machine-readable summary is [data/processed/dataset_summary.json](data/processed/dataset_summary.json).

Important: this report describes only information present in the files and their names. It does not infer ISC, ESC, PCF, SDF, ICF, fault severity, health state, or any other label from signal behavior.

## 1. Dataset structure

The current `data/raw/` tree contains three directories and 600 CSV files:

| Directory | CSV files | Rows | Files per battery | Filename sample range |
|---|---:|---:|---:|---|
| `real_world_02-03` | 240 | 958,800 | 8 | `00000-31959` |
| `real_world_03_04` | 270 | 976,830 | 9 | `00000-32560` |
| `real_world_05_06` | 90 | 293,400 | 3 | `00000-09779` |
| **Total** | **600** | **2,229,030** | — | — |

All files match the same pattern:

```text
battery_<battery_id>_cells_<first_cell>-<last_cell>_t_<first_sample>-<last_sample>.csv
```

Every filename range predicts the actual row count exactly (`end - start + 1`). Row counts are 4,000 for 510 files, 3,960 for 30 files, 561 for 30 files, and 1,780 for 30 files.

The dataset contains battery identifiers `01` through `30`. Each identifier is associated with one eight-cell range: `001-008`, `009-016`, ..., `233-240`. Thus the files appear to represent 30 battery groups with eight voltage and eight temperature channels per group. The CSVs do not contain a separate battery metadata table confirming the physical interpretation.

The directory names may be collection-period or session names, but their exact meaning is not documented in the files. They must not be treated as fault, severity, or operating-condition labels.

## 2. File naming convention and semantics

For an example filename:

```text
battery_01_cells_001-008_t_00000-03999.csv
```

| Component | Observed value | Supported interpretation |
|---|---|---|
| `battery_01` | `01` | Battery/group identifier encoded in the filename. |
| `cells_001-008` | `001-008` | Range of eight cell channels associated with that file; separate physical-cell metadata is unavailable. |
| `t_00000-03999` | `00000-03999` | Sequential sample-index range; it is not independently proven to be a timestamp or seconds. |
| `.csv` | CSV | Tabular signal data. |

The filenames contain no explicit fault type, fault severity, class, label, condition, event, healthy/normal, or anomaly token. The three directory names also contain none of those tokens. The names alone cannot identify a fault experiment or operating condition.

## 3. Signal schema and column analysis

All 600 files have the same 17 columns, in the same order, and all parsed as `float64`:

```text
vol_1, vol_2, vol_3, vol_4, vol_5, vol_6, vol_7, vol_8,
temp_1, temp_2, temp_3, temp_4, temp_5, temp_6, temp_7, temp_8,
cur
```

There is no `time`, `time_s`, `timestamp`, `orig_idx`, row-index, SOC, fault, class, severity, condition, or other metadata column. Sample order is available only from row order and filename ranges.

The following statistics are pooled across all 2,229,030 rows. `unique_values` is the exact number of distinct non-missing numeric values observed for that column. `large_step_count` is a descriptive discontinuity count using thresholds of `>0.1 V` for voltage, `>5 °C` for temperature, and `>100` current units; these are screening thresholds, not scientific fault criteria.

| Column | Type | Minimum | Maximum | Mean | Missing | Unique | Constant files | Max within-file step | Large steps |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `vol_1` | float64 | 3.1220002 | 3.551 | 3.313598 | 0 | 404 | 0 | 0.202000 | 111 |
| `vol_2` | float64 | 3.1210000 | 3.5290003 | 3.313950 | 0 | 397 | 0 | 0.178000 | 97 |
| `vol_3` | float64 | 3.1180000 | 3.5370002 | 3.313881 | 0 | 407 | 0 | 0.193000 | 110 |
| `vol_4` | float64 | 3.1170000 | 3.5660002 | 3.313838 | 0 | 414 | 0 | 0.212000 | 118 |
| `vol_5` | float64 | 3.1180000 | 3.5380000 | 3.313423 | 0 | 410 | 0 | 0.185000 | 117 |
| `vol_6` | float64 | 3.0730002 | 3.5490003 | 3.313982 | 0 | 463 | 0 | 0.176000 | 117 |
| `vol_7` | float64 | 3.1220002 | 3.5240002 | 3.313973 | 0 | 397 | 0 | 0.177000 | 107 |
| `vol_8` | float64 | 3.1240000 | 3.6040000 | 3.314405 | 0 | 464 | 0 | 0.171000 | 115 |
| `temp_1` | float64 | 23 | 44 | 31.991892 | 0 | 22 | 0 | 8 | 103 |
| `temp_2` | float64 | 23 | 44 | 32.123880 | 0 | 22 | 0 | 8 | 112 |
| `temp_3` | float64 | 22 | 44 | 32.028579 | 0 | 23 | 0 | 8 | 102 |
| `temp_4` | float64 | 21 | 44 | 31.920377 | 0 | 24 | 0 | 7 | 99 |
| `temp_5` | float64 | 22 | 44 | 31.938326 | 0 | 23 | 0 | 7 | 107 |
| `temp_6` | float64 | 23 | 44 | 31.991424 | 0 | 22 | 0 | 8 | 89 |
| `temp_7` | float64 | 24 | 44 | 32.140984 | 0 | 21 | 0 | 8 | 103 |
| `temp_8` | float64 | 23 | 45 | 32.013837 | 0 | 23 | 0 | 8 | 98 |
| `cur` | float64 | -133.19995 | 141.40015 | -0.119940 | 0 | 2,357 | 0 | 153.000001 | 1,950 |

## 4. Label and metadata search

The following were searched without finding an explicit label:

- all directory names;
- all 600 filenames;
- all CSV headers;
- the values in initial rows of every CSV;
- all non-CSV files under `data/raw/`.

Search concepts included `fault`, `failure`, `anomaly`, `normal`, `healthy`, `damaged`, `severity`, `class`, `label`, `type`, `event`, `condition`, `ISC`, `ESC`, `PCF`, `SDF`, `ICF`, `short`, `circuit`, and `degradation`.

The only non-CSV file is `.gitkeep`. There is no README, manifest, label table, experiment configuration, or metadata file under `data/raw/`. Signal excursions and screening-triggered windows are observations, not ground-truth labels.

## 5. Supervised-training determination

**C. NO EXPLICIT FAULT LABELS AVAILABLE**

Evidence:

- zero label/class/fault/severity/condition columns;
- no label-like tokens in filenames or directory names;
- no metadata or README under `data/raw/`;
- only voltage, temperature, and current measurements are present.

Supervised fault classification cannot be justified from this dataset alone. In particular, no ISC/ESC/PCF/SDF/ICF labels may be created from signal thresholds or inferred from the three directory names without an external documented protocol.

## 6. Battery grouping

The strongest available grouping key is `(directory, battery_id)` parsed from the filename. Each directory contains all 30 battery IDs, and each battery ID has a fixed eight-cell range. The same battery identifier reappears in each directory, but the files do not establish that those are one continuous experiment across directories. Treat the directory/session as part of the identity until external metadata says otherwise.

Recommended grouping key for any later analysis:

```text
collection_directory + battery_id + filename_sample_range
```

Do not pool rows from different batteries or different directories into one sequence without an explicit protocol.

## 7. Temporal structure and continuity

There is no timestamp column, so the actual sampling period cannot be proven from CSV contents. The `t_...` filename component is an ordered sample index. If the project’s external data documentation confirms one-second sampling, it may be used as a documented assumption; it is not independently encoded in these files.

Within each `(directory, battery_id)` group:

- every adjacent filename range starts exactly one sample after the previous range ends;
- all 510 expected adjacent file pairs have no gaps or overlaps;
- filename row counts match `end - start + 1` for all 600 files;
- the final per-file fragments are exactly the shorter ranges shown in the structure table;
- across-file boundary checks found no voltage jump above 0.1 V, temperature jump above 5 °C, or current jump above 100 current units.

Therefore, files within the same directory and battery group are consistent with consecutive sample segments and can be concatenated by filename range for exploratory analysis, subject to the absence of timestamps. The three directories restart their ranges at zero and may represent separate collection periods; they must not be concatenated across directories solely because the battery identifier matches.

## 8. Data quality

### Missing values and types

No missing or non-finite values were found in any of the 2,229,030 rows or 17 columns. Every file has the same schema and numeric `float64` parsing.

### Duplicate rows

Exact duplicate full rows occur within files:

- 117,538 rows belong to duplicate groups (`duplicated(keep=False)`);
- 66,983 rows are excess copies if the first occurrence of each duplicate group is retained.

This is consistent with quantized measurements and repeated operating states, but it is not evidence of a fault. Duplicate handling should be decided by the modeling protocol, not silently applied during inspection.

### Constant columns

No column is constant within any of the 600 files. Temperature values are quantized to a small set of integer-like values, but they do vary.

### Signal ranges and broad plausibility checks

- Voltages are between 3.0730002 and 3.604 V across all cell channels.
- Temperatures are between 21 and 45 in the recorded temperature units, apparently °C by naming/context but not explicitly documented in the CSV.
- Current is between -133.19995 and 141.40015 in the recorded current units; the unit and sign convention are not stored.

No obviously empty or nonsensical all-zero signal column was found. Some within-file step changes exceed the descriptive thresholds listed above; these are candidates for transient inspection, not fault labels. Boundary transitions between sequential files were smaller than those thresholds.

## 9. Recommended next modeling strategy

Because there are no explicit fault labels, the next defensible modeling phase is unsupervised or self-supervised:

1. preserve `(directory, battery_id)` grouping and filename sample ranges;
2. use DDP and Level-1 screening as signal-selection/event-proposal mechanisms, not as ground truth;
3. build unsupervised anomaly detection, clustering, representation learning, or forecasting baselines;
4. validate repeatability across batteries and collection directories;
5. acquire or construct a separately documented label protocol before supervised fault training;
6. if labels become available, split by battery and collection session to prevent leakage across adjacent segments.

The placeholder diagnosis and risk policy must remain explicitly non-ground-truth software components. No model should be trained against their outputs as if they were labels.

## 10. Unknown or uncertain information

The following cannot be determined from these files alone:

- whether `real_world_02-03`, `real_world_03_04`, and `real_world_05_06` are dates, experiment IDs, operating conditions, or collection sessions;
- the physical meaning and units of `cur` and `temp_*`;
- whether the filename `t` values are seconds, sample numbers, or another index;
- whether repeated battery IDs across directories refer to the same physical batteries;
- whether any signal pattern corresponds to a fault, degradation, load transition, or normal operation;
- the ground-truth health state, fault type, severity, event boundaries, or operating condition;
- whether rows were pre-cleaned, resampled, clipped, or otherwise transformed before export;
- whether a missing metadata package exists outside the repository.

## Conclusion

The extracted dataset is a clean, uniform multivariate time-series collection with 30 filename-defined battery groups, eight voltage channels, eight temperature channels, and current. It has reliable within-directory sample-range structure but no explicit fault labels or timestamp column. The correct supervised-learning status is **C. NO EXPLICIT FAULT LABELS AVAILABLE**. Any fault taxonomy, severity, event label, or “normal” label must come from an external documented source and must not be invented from these measurements.
