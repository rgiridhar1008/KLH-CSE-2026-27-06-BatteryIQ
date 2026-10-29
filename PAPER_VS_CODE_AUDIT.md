# Paper vs. Code Audit: BatteryIQ / DDP Downsampling

**Audit scope.** This is an inspection-only audit of the repository as it existed on 2026-09-16. No source, configuration, dataset, or generated output was changed. The only file created by this audit is this report.

**Evidence boundary.** The primary article is Jinglun Li et al., *Large language model-based fault diagnosis for lithium-ion batteries in cloud-edge systems*, *Cell Reports Physical Science* 7(4), 103210 (2026), DOI [10.1016/j.xcrp.2026.103210](https://doi.org/10.1016/j.xcrp.2026.103210). Its public abstract confirms DDP-guided downsampling and reports compression below 5%. The accessible article page did not expose the full methods/supplement at audit time. Therefore, statements labelled **Paper brief** come only from the supplied project brief (VDD, CDD, approximately 0.43/0.007 thresholds, and 30 s/5 s/original sampling); the exact Supplemental Methods equations and rules remain **unverified**, not inferred from code comments.

## 1. Executive Summary

The repository contains a compact, importable downsampling package, not a verified paper reproduction. It implements a windowed, representative-cell voltage divergence calculation and a voltage-range/current-range quantity called CDD, then maps the two threshold comparisons to three grades and samples each grade at 1/5/30-second nominal intervals.

The known paper-brief values are only partially aligned: CDD (0.007) and 1/5/30-second defaults align; VDD is 0.415 rather than the paper brief's approximately 0.43. More importantly, there is no separately defined numeric `DDP` calculation, no supplied config/data/example, no tests, no experiments, and no accessible method text against which to prove that the metric equations, representative-cell rule, segment logic, and overlap policy reproduce the paper.

**Readiness conclusion: YES, WITH CONDITIONS.** The code is a useful auditable scaffold, but implementation/reproduction work must begin by obtaining and transcribing the paper's Supplemental Methods and creating characterization tests before altering equations or thresholds.

## 2. Repository Architecture

| Path | Role | Audit observation |
|---|---|---|
| `src/ddp_downsampling/config.py` | CSV key/value parser and `PipelineConfig` defaults | No actual configuration CSV is provided. Invalid numeric/boolean values silently fall back to defaults. |
| `src/ddp_downsampling/ddp_metrics.py` | representative cells, divergence, VDD, CDD | Contains the core equations; its “Supplemental Methods S5” docstring is not independently substantiated here. |
| `src/ddp_downsampling/segmentation.py` | run-length segmentation and minimum-length reassignment | Operates in row counts, not elapsed time. |
| `src/ddp_downsampling/downsampling.py` | windowing, grades, sampling indices, DataFrame/CSV operations | Central data-flow implementation. |
| `src/ddp_downsampling/cli_downsample.py` | command-line batch entry point and stats | Requires input directory, output directory, and external config CSV. |
| `src/ddp_downsampling/downsample_dataset.py` | direct-script wrapper | Its bootstrap path resolves to `src/src`, which is not the repository source root. |
| `src/ddp_downsampling/__init__.py` | package marker | No runtime logic. |
| `data/raw/.gitkeep`, `data/processed/.gitkeep` | intended input/output directories | No data or generated outputs to inspect. |
| `tests/.gitkeep` | reserved tests directory | No tests exist. |
| `requirements.txt`, `pyproject.toml` | dependencies/package metadata | `pytest` is declared only in `requirements.txt`; `pyproject.toml` points to a missing `README.md`. |
| `PROJECT_STRUCTURE.txt` | project note | States source files were copied unchanged, but cannot establish paper fidelity. |

There is no README, dataset loader beyond `pandas.read_csv`, example config, visualization, experiment/evaluation script, notebook, or repository Git metadata in the audited directory.

## 3. Current Data Flow

```text
CSV files under --input-dir (recursive; manifest.csv excluded)
  -> pandas.read_csv
  -> require `cur` + all columns whose name starts `vol_`
  -> sort voltage columns numerically where possible
  -> one VDD/CDD window per row (or every step, then forward-fill)
  -> base grades: HIGH=2 / MID=1 / LOW=0
  -> minimum-run grade reassignment
  -> build high/mid/low index sets; union them
  -> selected rows + orig_idx/orig_row/selection flags/VDD/CDD
  -> mirrored output CSV; optional per-file row-count statistics
```

The CLI parses a key/value CSV with `load_kv_csv`, processes every eligible CSV independently, and mirrors relative input paths under `--output-dir`. `--stats` writes `downsampling_stats.csv` only after the data files are produced.

## 4. Paper Methodology Summary

The auditable paper baseline is deliberately limited to evidence available for this audit:

- The publication introduces DDP-guided downsampling for lithium-ion battery fault diagnosis and its abstract claims less than 5% retained data while preserving faults.
- The supplied project brief identifies DDP inputs as Voltage Divergence Degree (VDD) and Current Deviation Degree (CDD).
- The supplied brief describes three frequency regions and example values of VDD about 0.43, CDD 0.007, low 30 s, middle 5 s, and original/high frequency.

The article/supplement must be obtained before asserting the exact VDD equation, CDD equation, DDP aggregation, threshold inclusivity, window/step, representative-cell algorithm, endpoint rule, short-segment policy, or any reported retention result. Those details are ambiguous in the accessible evidence.

## 5. Paper vs Current Implementation Comparison

| Component | Paper | Current Code | Status | Evidence/File | Required Action |
|---|---|---|---|---|---|
| DDP purpose | DDP-guided adaptive downsampling | Implements VDD/CDD-driven grades and sampling | Partial | `downsampling.py:57-111,139-183` | Verify that grades are the paper's DDP decision rule. |
| Numeric DDP | Brief calls methodology DDP; formula unavailable | No numeric `DDP` variable/function; only VDD, CDD, and grade | Missing/unverified | `ddp_metrics.py`, `downsampling.py:57-111` | Compare with paper equation before adding or renaming anything. |
| VDD threshold | About 0.43 (brief) | Default 0.415 | Difference | `config.py:80` | Do not change until the exact source value, units, and calibration dataset are confirmed. |
| CDD threshold | 0.007 (brief) | Default 0.007 | Aligned, unverified | `config.py:81` | Confirm equation and comparator convention. |
| Three rates | high/original, 5 s, 30 s (brief) | 1 s, 5 s, 30 s defaults | Partial/aligned | `config.py:88-90`; `downsampling.py:151-154` | Verify that input cadence is 1 s before treating 1 s as “original.” |
| Representative cells | Not accessible in paper methods | Up to five extrema/range/variance-selected cells, deduplicated | Unverified | `ddp_metrics.py:8-45` | Validate exact S5 selection criteria and tie/NaN handling. |
| VDD calculation | Exact equation unavailable | maximum custom pairwise divergence among representatives | Unverified | `ddp_metrics.py:55-99` | Equation-level verification required. |
| CDD calculation | Exact equation unavailable | all-cell voltage range divided by current range, floored by full-series current range | Unverified/risk | `ddp_metrics.py:102-125`; `downsampling.py:72-75` | Verify denominator domain and whether voltage range is all cells/window. |
| Grade rule | Three regions mentioned; rule unavailable | HIGH iff both `>`; LOW iff both `<`; otherwise MID | Unverified | `downsampling.py:91-96` | Verify mixed/equal threshold handling. |
| Minimum segment rule | Not available | 20/10/50 rows plus `extend`/`discard` policy | Project-specific/unverified | `config.py:92-97`; `segmentation.py:58-179` | Confirm whether paper has this post-processing. |
| Overlap policy | Not available | default `share` combines base and fixed masks; `exclusive` is optional | Project-specific/unverified | `config.py:97`; `downsampling.py:147-183` | Characterize/justify or replace only after reference confirmation. |
| Timestamp use | Sampling intervals are temporal | Uses configured `output_interval_s`, not observed timestamp differences | Incomplete/risk | `downsampling.py:28-32,151-154,215-224` | Validate cadence/monotonicity or define an explicit resampling contract. |
| Retention/compression | Abstract says <5% for paper evaluation | Optional row count and raw/down ratio only; no experiment | Incomplete | `cli_downsample.py:33-49,66-91` | Reproduce only with paper data/protocol and report separately. |

## 6. DDP Equation-by-Equation Comparison

The implementation is exactly representable as follows, but none of these equations can be marked paper-equivalent without the supplement.

1. For each selected voltage sequence, code centers it: `x' = x - mean(x)`.
2. It forms `p_t = x1'_t * x2'_t`; only negative products are replaced with `-alpha * abs(p_t)**beta`.
3. Its pair divergence is `1 - mean(p) / (std(x1') * std(x2'))`, returning zero if either standard deviation is below `1e-12`.
4. `VDD = max(0, maximum pair divergence)` over representative cells.
5. `CDD = (max(vol_window) - min(vol_window)) / max(range(square-wave-adjusted cur_window), full_series_current_range_floor)`.
6. Grades are HIGH if `VDD > vdd_thres and CDD > cdd_thres`; LOW if both strict inequalities are `<`; all other cases are MID.

There is no code formula that combines VDD and CDD into a scalar named DDP. The phrase “DDP calculation” in this repository refers operationally to the two metric calculations and threshold classification, not a documented `DDP = f(VDD, CDD)` value. This is a blocking ambiguity for exact reproduction.

## 7. VDD Implementation Audit

- `compute_vdd` selects representative voltage columns, optionally adds the same alternating square wave to each selected sequence, calculates all unordered pair divergences, and returns the largest non-negative result.
- It returns 0 for fewer than two selected cells or zero-variance pairs. This is a defensive software choice, but it may make a single-cell pack or a flat/noisy window appear low disorder.
- No finite-value validation is performed. `NaN` can propagate through `max`, `var`, and the divergence path; the resulting behavior is not documented or tested.
- Square-wave injection is enabled by default (`1e-4` V). The supplied brief does not establish this perturbation. Treat it as project-specific until S5 explicitly supports it.
- The use of `np.std`/`np.var` uses population normalization (`ddof=0`), a material choice for short windows that requires paper verification.

## 8. CDD Implementation Audit

- CDD is not based on a cell-specific current channel; it uses the total voltage span of all cells and all rows inside the window divided by current span.
- `current_range_floor` is calculated once from the **entire input series**, not the local window. This makes local CDD depend on distant portions of the file and prevents the local current range from fully determining the denominator (`downsampling.py:72-75,84-99`).
- With a near-constant current the code substitutes `max(abs(cur))`, then at least `1e-6`; default current square-wave injection may also force a nonzero local span. The numerical/physical rationale is undocumented.
- The `denom < eps` branch is normally unreachable because the supplied floor is at least `1e-6`. This is harmless but signals an untested edge-case contract.
- Units/normalization are undocumented. A raw voltage-range/current-range ratio is sensitive to units and current scaling, so the 0.007 threshold is not portable without an explicit data contract.

## 9. Representative Cell Selection Audit

Within each voltage window, the code picks the indices of: maximum per-cell maximum, minimum per-cell minimum, maximum per-cell range, maximum variance, and minimum variance. Duplicates are removed, then a second arbitrary column is appended if only one was selected in a multi-cell pack.

This is deterministic except for NumPy's first-index tie behavior. It uses extrema anywhere in the window, not a common instantaneous time point. Empty columns are handled, but no rows, NaNs, one-cell packs, ties, or all-constant arrays are tested. The code comment attributes this list to S5; that attribution must be checked against the paper rather than accepted as evidence.

## 10. DDP Classification/Grade Audit

Grades are integers rather than named labels: `2=HIGH`, `1=MID`, `0=LOW` (`segmentation.py:10-16`). A grade is assigned for every input row. Threshold equality and mixed high/low metric results are MID due to strict comparisons. The code has no grade confidence, DDP scalar, reason code, or persisted full grade series in its CSV output.

The grade logic is clear and reproducible internally, but its correspondence to the paper's low/middle/high regions is unproven. In particular, an OR-based condition, inclusive threshold, or DDP aggregate in the paper would change boundary behavior materially.

## 11. Sampling Frequency Audit

Nominal steps are `round(interval_seconds / output_interval_s)`, clamped to at least one row. Defaults produce 1/5/30 rows only when `output_interval_s=1` and the file is uniformly 1-second sampled. The algorithm does not determine input cadence from a timestamp column.

Sampling restarts at each contiguous mask segment. It includes the start, then every Nth row; it does **not** force inclusion of a segment's final row. HIGH means every row only when high interval rounds to one. “Original frequency” is therefore an assumption, not a verified preservation of the original acquisition cadence.

## 12. Threshold Audit

| Parameter | Code default | Paper-brief value | Finding |
|---|---:|---:|---|
| `vdd_thres` | 0.415 | approximately 0.43 | Difference; precision and dataset calibration are unknown. |
| `cdd_thres` | 0.007 | 0.007 | Numerically aligned, but the underlying CDD equation is unverified. |
| `ddp_alpha` | 0.3 | not supplied | Project-specific/unverified. |
| `ddp_beta` | 2.0 | not supplied | Project-specific/unverified. |
| voltage square-wave amplitude | `1e-4` | not supplied | Project-specific/unverified. |
| current square-wave amplitude | `1e-3` | not supplied | Project-specific/unverified. |

There is no checked-in `pipeline_params.csv`, so default values are the only executable baseline in the repository. `get_float`, `get_int`, and `get_bool` silently choose a default for malformed values, which can unintentionally change an experiment without failing fast.

## 13. Window Size and Step-Size Audit

Defaults are a 50-row window, step size 1, centered anchor. At both edges the window is shifted inward, so the first approximately half-window rows reuse the first full window and the final rows reuse the last full window. With a step greater than one, code evaluates only at indices `0, step, ...` then forward-fills VDD, CDD, and grade.

Both window length and step are in rows, not seconds, and no dataset-specific sampling-rate conversion occurs. The paper brief provides no window/step values; these are unverified and must not be relabelled paper defaults.

## 14. Segmentation Audit

`grades_to_segments` produces inclusive, contiguous run-length segments. `enforce_min_lengths` reassigns grade ownership; it never drops timestamps. The default minimums are HIGH 20, MID 10, LOW 50 rows. Under `extend`, a short segment borrows rows only from lower-grade neighboring segments, then can merge if still short. Under `discard`, it is merged into a selected neighbor, favoring higher grade and then the right neighbor on a tie.

These are substantial adaptive-policy decisions, not merely mechanical implementation. There is no evidence in the supplied paper brief that min-length enforcement, priority borrowing, its defaults, or the maximum of 10,000 passes belongs to the baseline.

## 15. Timestamp and Boundary Handling Audit

- Recognized time columns are only `time_s` and `orig_idx`; otherwise a synthetic time `row_number * output_interval_s` is created.
- A recognized column is converted directly to float. ISO datetimes, timezone-aware timestamps, duplicate timestamps, non-monotonic records, gaps, and missing values are unsupported/unchecked.
- The output field called `orig_idx` contains selected **time values**, rounded to six decimals; `orig_row` holds the source row index. This is semantically confusing when the source had an `orig_idx` rather than a time.
- The original `time_s`/`orig_idx` field is excluded from copied columns, so precision/type/column name are not faithfully preserved.
- Window boundaries are shifted to retain a complete 50-row window where possible; sampling segment ends are not guaranteed to be retained.

## 16. Downsampling Index Selection Audit

`exclusive` mode samples only the final minimum-length-adjusted grade masks. Default `share` mode samples HIGH from final grades, but samples MID and LOW from the union of their base and final masks. The output union is deduplicated, while `sel_high`, `sel_mid`, and `sel_low` retain multi-membership flags.

This means default output may represent two grade interpretations simultaneously. For example, a base-MID segment changed to LOW can still contribute 5-second MID indices and 30-second LOW indices. It may be intentional, but it is not a conventional exclusive adaptive-sampling partition and needs paper/evaluation evidence.

## 17. Data Retention / Compression Audit

The optional stats table records `raw_len`, `down_len`, `overlap_mode`, `short_segment_policy`, and `compression_ratio = raw_len/down_len`. The CLI prints aggregate retained-row rate and aggregate ratio.

This is a useful count summary but is not a complete reproduction evaluation: it has no per-grade retention, byte/file-size compression, time-weighted retention for irregular samples, fault-preservation metric, selected-index manifest, or comparison against uniform/random downsampling. No CSV, output, or reported experiment exists, so the paper's “<5%” result must not be claimed for this project.

## 18. Dataset Compatibility Audit

Required input schema:

| Requirement | Actual behavior |
|---|---|
| Current | exactly a numeric `cur` column. |
| Cell voltages | one or more numeric columns beginning `vol_`; numeric suffixes sort numerically (`vol_2` before `vol_10`), other suffixes follow afterward. |
| Time (optional) | numeric `time_s` preferred, otherwise numeric `orig_idx`, otherwise synthetic. |
| Other fields | copied through to output at selected rows, except recognized time fields. |
| Row consistency | not validated explicitly; inconsistent/invalid arrays fail indirectly or propagate NaNs. |

No alias mapping exists for common schemas such as `current`, `timestamp`, `cell_01_voltage`, long/tidy data, pack IDs, cycle IDs, or multi-pack files. There is no grouping: all rows in a CSV are treated as one continuous pack sequence. Dataset compatibility with the paper's five battery types cannot be evaluated because no data, loader specification, or schema is present.

## 19. Configuration Audit

`PipelineConfig` has reasonable centralized defaults, but there is no checked-in parameter file, schema, unit documentation, range validation, provenance/version identifier, or recording of effective configuration in output metadata. The CLI requires a config path but does not verify unrecognized keys; `load_kv_csv` ignores optional headers, blank/short rows, and columns beyond the second.

Unknown `ddp_window_anchor` behaves as centered; unknown short policy becomes `extend`; any overlap string other than `exclusive` behaves as `share`. These silent fallbacks are risky for a research reproduction, where incorrect settings should be observable rather than masked.

## 20. Existing Test Coverage

There are no test files—only `tests/.gitkeep`. A read-only smoke test imported the package and ran `downsample_dataframe` on a 60-row synthetic two-cell frame, producing 12 output rows with a single MID grade. This establishes only that this path executes; it is not methodological validation.

`pytest` is listed in `requirements.txt`, but it is not installed in the audit environment (`No module named pytest`), so `python -m pytest -p no:cacheprovider -q` could not collect tests. No dependencies were installed for this audit.

## 21. Missing Tests

Write characterization tests before any methodology change:

1. Exact VDD and CDD golden vectors from the paper supplement, including alpha/beta, zero variance, negative products, and square-wave policy.
2. Representative-cell fixtures covering unique winners, duplicate winners, ties, one-cell, NaN, and constant windows.
3. Grade-boundary tests for `<`, `=`, `>` and mixed VDD/CDD states.
4. Window-anchor/edge/step tests proving which rows share a window and forward-fill behavior.
5. Segment tests for every neighbor arrangement, short-run policy, min lengths, and no dropped/reordered rows.
6. Index tests for all intervals, every segment endpoint, non-1-second cadence, `share` versus `exclusive`, and selection flags.
7. Timestamp tests for numeric, irregular, duplicate, non-monotonic, missing, and unsupported datetime values.
8. CSV/CLI tests for schema errors, config parsing failures, recursively mirrored paths, empty input, stats, and output schema.
9. End-to-end regression tests on fixed paper-compatible data with expected retained index sets and retention figures.

## 22. Potential Bugs or Research-Reproducibility Risks

1. **Unverified scientific core:** code comments assert an S5 source, but no full supplemental evidence is available; a plausible implementation is not a reproduction.
2. **No scalar DDP:** papers/tests may expect a named DDP calculation that the code does not expose.
3. **Time/cadence mismatch:** configured output interval drives sampling steps even when provided timestamps indicate another cadence or gaps.
4. **CDD depends on the whole file:** local decisions change if unrelated distant current observations are appended.
5. **Default square-wave perturbations:** alter both metrics without paper-brief support and can dominate flat signals.
6. **Default shared masks:** base and adjusted classifications can both generate retained points, obscuring the intended frequency assignment.
7. **Endpoint loss:** low/mid segment final observations are not guaranteed, potentially losing event transitions.
8. **Row-count rather than duration policy:** minimum lengths and reported retention are invalid as temporal quantities for irregular data.
9. **No NaN/schema/group validation:** ordinary BMS data quality issues can silently produce invalid grades or cross pack/cycle boundaries.
10. **Packaging/direct-wrapper issues:** the missing `README.md` conflicts with `pyproject.toml`, and the direct wrapper computes `src/src`; neither has a test.
11. **Absent experiment provenance:** no config, data checksum, code version, retained index record, or expected output exists.

## 23. Parts That Are Already Correct

“Correct” here means internally coherent or aligned with the supplied brief—not verified paper fidelity.

- The package is modular: metrics, segmentation, sampling, configuration, and CLI are separated.
- Required core columns fail clearly when `cur` or `vol_` data are absent.
- Numeric cell-suffix sorting prevents the common `vol_10`/`vol_2` lexical ordering error.
- The code keeps source row identity (`orig_row`) and emits selected VDD/CDD values and selection-set flags.
- It preserves all non-time ancillary columns for selected rows and mirrors batch-directory structure.
- It offers explicit base and adjusted grades internally, plus an optional compression count report.
- Defaults numerically include the brief's 0.007 CDD and 1/5/30-second frequency pattern.

## 24. Parts That Are Incorrect or Incomplete

No item below is an instruction to change code now; it is an audit finding.

- Exact paper equivalence cannot be established; key formulas/rules are incomplete from available evidence.
- The VDD default differs from the brief's approximate value and lacks calibration provenance.
- There is no explicit DDP scalar/definition, data contract, sample config, README, data, output fixture, experiment, visualization, or test suite.
- Timestamp treatment does not verify actual cadence and replaces time-field naming/type.
- Default share semantics, min-length grade reassignment, and square waves are unsupported by the supplied baseline.
- The claimed project structure says tests are reserved, confirming the absence rather than providing coverage.
- Package metadata references a nonexistent README and the direct wrapper has an incorrect path calculation.

## 25. Parts That Must NOT Be Changed Without Verification

- The VDD divergence equation, centering, negative-product transform, alpha, beta, standard-deviation convention, and zero-variance result.
- The CDD numerator/denominator, current normalization/floor, units, and square-wave behavior.
- Representative-cell set, pair aggregation, VDD/CDD thresholds, comparator inclusivity, and grade decision table.
- Window size, anchor, step size, boundary reuse, and whether per-row or per-window grades are required.
- 1/5/30-second assignments, source cadence assumptions, and endpoint selection policy.
- Minimum-length values, `extend`/`discard` semantics, priority direction, and shared versus exclusive masks.
- Any target retention/compression figure, including the paper's abstract result.

## 26. Recommended Implementation Order

1. Obtain the paper PDF and Supplemental Methods/data protocol; archive the exact citation, equations, parameter table, and figure/table references in project documentation.
2. Make a paper-to-code specification table that resolves every “unverified” row in this report, explicitly retaining any intentional BatteryIQ deviations as novelties rather than baseline.
3. Create a minimal, versioned sample config and schema fixture only after verifying units/cadence/columns.
4. Add golden unit tests for equations, classification, boundaries, segments, and index sets before changing implementation.
5. Run the untouched baseline against a fixed, paper-compatible dataset and persist an index-level result manifest.
6. Compare retention, timing, and fault-relevant performance with the paper protocol; classify differences as data, implementation, or unresolvable paper ambiguity.
7. Only then make narrowly scoped baseline corrections, rerun the characterization suite, and keep future BatteryIQ novelties in separate modules/configurations.

## 27. Exact Files That Would Need Modification in the Next Phase

No changes are made by this audit. Subject to the verification order above, these are the concrete files implicated by each next-phase task:

| Next-phase purpose | Files |
|---|---|
| Baseline equation/representative-cell correction, if paper disproves current implementation | `src/ddp_downsampling/ddp_metrics.py` |
| Window, grade, timestamp, index, and output corrections | `src/ddp_downsampling/downsampling.py` |
| Verified segmentation/policy correction | `src/ddp_downsampling/segmentation.py` |
| Verified defaults, strict config validation, and parameter provenance | `src/ddp_downsampling/config.py` plus a new checked-in example config file |
| CLI validation/metadata/statistics correction | `src/ddp_downsampling/cli_downsample.py` |
| Direct script execution fix | `src/ddp_downsampling/downsample_dataset.py` |
| Packaging/documentation correction | `pyproject.toml`, `requirements.txt` if dependency policy changes, and a new `README.md` |
| Required verification suite | new files under `tests/` (metrics, segmentation, downsampling, CLI, and end-to-end fixtures) |
| Reproduction protocol and results | this audit's successor documentation and versioned fixture/experiment assets; do not overwrite this audit |

## 28. Final Readiness Assessment

### READY FOR IMPLEMENTATION?

**YES, WITH CONDITIONS**

The project is ready to begin a disciplined verification-and-test phase, not to claim a completed reproduction or to add downstream AI/risk/dashboard features.

- **Already correct:** the package is runnable on its narrow expected schema, structurally modular, and has the brief-aligned CDD/1/5/30 defaults described above.
- **Incorrect or incomplete:** full paper-method equivalence is unproved; a scalar DDP is absent; VDD default differs; timing, segmentation, overlap, and perturbation choices lack baseline evidence; tests/data/docs/config fixture are absent.
- **Missing:** paper supplemental equations/protocol, dataset contract, parameter provenance, golden examples, automated tests, evaluation scripts/plots, and reproducible outputs.
- **Needs clarification:** exact VDD/CDD/DDP equations; representative-cell selection; threshold semantics; window/step/boundaries; segment/overlap policy; input cadence and dataset schema; paper evaluation data and fault-preservation metric.
- **Fix first:** do not edit the scientific code first. First obtain and encode the authoritative Supplemental Methods into a testable specification; then correct only demonstrated discrepancies.
- **Write first:** equation golden tests, threshold-boundary tests, representative-cell tests, timestamp/index tests, and segment-policy tests.
- **Run first:** an untouched-baseline characterization on a fixed compatible fixture, then the paper-protocol comparison of retained indices, retention ratio, and fault-relevant outcome. Do not treat the paper's <5% abstract claim as a result for BatteryIQ until that experiment is actually run.
