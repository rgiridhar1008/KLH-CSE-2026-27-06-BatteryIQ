# Paper-to-Code Scientific Verification Report

## 1. Paper citation

Jinglun Li, Yunlong Shang, Xin Gu, Hao Geng, Kailong Liu, Xiangjun Li, Fangyuan Bi, and Chenghui Zhang, “Large language model-based fault diagnosis for lithium-ion batteries in cloud-edge systems,” *Cell Reports Physical Science* 7, 103210 (2026), DOI: [10.1016/j.xcrp.2026.103210](https://doi.org/10.1016/j.xcrp.2026.103210).

The local paper examined was `C:\Users\91949\Downloads\PIIS2666386426001165.pdf` (13 pages). The PDF is the main article. It refers to Methods S5 and S6, but those supplemental methods are not included in this file. No source code was changed and no experiment was run.

## 2. Exact paper sections used

The verification uses the following locations in the supplied PDF:

- **Results — Data acquisition and experimental platform**, printed pages 3–4 (PDF pages 4–5): dataset composition, fault classes, cleaning/labelling, trajectory slicing/data augmentation, and real-world data.
- **Results — DDP-guided adaptive down-sampling**, printed pages 4–5 (PDF pages 5–6): VDD/CDD purpose, threshold values, qualitative sampling behavior, and compression results.
- **Methods — Down-sampling method based on DDP**, printed page 9 (PDF page 10): Equation 1 and the short-segment/fixed-fragment description.
- **Methods continuation**, printed page 10 (PDF page 11): qualitative interpretation of VDD, CDD, and high/low DDP.
- **Resource availability**, printed page 10 (PDF page 11): Zenodo dataset and original-code links.
- **Referenced but unavailable:** Methods S5 (VDD/CDD equations and threshold determination) and Methods S6 (detailed segmentation pseudocode). The article explicitly says those details are in S5/S6; they cannot be reconstructed from the main PDF without guessing.

## 3. DDP methodology

The paper defines data disorder degree (DDP) as a method-level construct made from two complementary indicators: voltage divergence degree (VDD) and current deviation degree (CDD). VDD captures dispersion among cell-voltage trajectories within a module. CDD characterizes whether voltage fluctuations are driven by external current variation or by internal fault-induced dynamics.

The paper does **not** present a separate scalar arithmetic expression named `DDP` in the supplied main article. DDP is operationalized through the joint VDD/CDD decision in Equation 1. The exact formulas for VDD and CDD are stated to be in Methods S5, which is not included in the supplied PDF.

## 4. VDD equation

**Status: CANNOT DETERMINE.** The main article provides no VDD equation. It states that the calculation methodology is in Methods S5. The supplied PDF contains no S5 pages, and no equation can be reproduced accurately without that supplement.

Current code instead implements a centered pairwise custom divergence, optional square-wave perturbation, and the maximum divergence over selected representative cells (`src/ddp_downsampling/ddp_metrics.py`). That is a code description, not evidence of paper equivalence.

## 5. CDD equation

**Status: CANNOT DETERMINE.** The main article provides no CDD equation. It states that the calculation methodology is in Methods S5. The supplied PDF contains no S5 pages, and no equation can be reproduced accurately without that supplement.

Current code computes a window-wide voltage range divided by a current-range denominator with a full-series floor (`src/ddp_downsampling/ddp_metrics.py` and `downsampling.py`). The paper does not authorize that exact implementation in the supplied material.

## 6. DDP decision rule

The paper’s Methods Equation 1 (printed page 9) gives the sampling-frequency rule:

```text
F = F0/30  if VDD < φVDD and CDD < φCDD
F = F0     if VDD > φVDD and CDD > φCDD
F = F0/5   otherwise
```

Here `F0` is the original sampling frequency. The PDF text layer renders the fraction bars poorly (`F0=30` and `F0=5`), but the surrounding text and figures describe the corresponding 30-second, original/high-frequency, and 5-second sampling intervals. The rule is strict on both inequalities; equality is therefore in the “otherwise” middle case.

The current base-grade logic is equivalent: both strict lower comparisons produce LOW, both strict higher comparisons produce HIGH, and every other case produces MID. This match applies only to the uncorrected `base_grades`; subsequent code-specific segment reassignment can change final regions.

## 7. Threshold values

The paper reports VDD threshold **0.43** and CDD threshold **0.007** in the Results discussion of Figures 3 and 4 (printed page 4, PDF page 5). It calls them `φVDD` and `φCDD` in Equation 1. The exact threshold-determination procedure is delegated to unavailable Methods S5.

The current defaults are VDD **0.415** and CDD **0.007**. Thus CDD matches numerically; VDD differs.

## 8. Sampling-frequency rules

The paper’s three regions are:

- **Low:** 30-second interval (`F0/30` in Equation 1).
- **High/original:** original sampling frequency (`F0`).
- **Middle:** 5-second interval (`F0/5`).

The current defaults are high interval 1 s, middle 5 s, and low 30 s. The middle and low intervals match the paper’s stated intervals. The high setting is only equivalent if the source data’s original cadence is exactly 1 s; the paper defines it relationally as `F0`, not as a universal one-second interval.

## 9. Representative-cell procedure

**Status: CANNOT DETERMINE.** The main article describes VDD at the module/cell-trajectory level but gives no representative-cell selection procedure. The paper directs calculation details to Methods S5, unavailable in the supplied PDF.

The current code selects up to five columns using per-window maximum, minimum, range, maximum variance, and minimum variance, then deduplicates them. This must not be labelled paper behavior until S5 is obtained.

## 10. Window/segment procedure

The paper says VDD/CDD are evaluated “within each time window,” but the supplied main PDF does not specify window length, step, anchor, boundary padding, or timestamp-to-row conversion. Those metric details are delegated to S5.

The paper’s main Methods section does specify a later segmentation concept: a refined adaptive segment-partitioning algorithm merges short segments with the **subsequent higher-priority segment**, then divides merged data into fixed-length fragments optimized to fit the LLM’s maximum input size. Detailed pseudocode is delegated to Methods S6, unavailable here.

The current code performs run-length grade segmentation and minimum-length reassignment, but does not implement the paper-described fixed-length LLM fragments.

## 11. Data-retention/compression methodology

The paper defines compression ratio as the amount of data retained after downsampling relative to the original data, expressed as a percentage. Smaller is stronger compression. It reports median retained proportions of 3.35% (CC), 3.54% (real world), 3.71% (DST), 3.70% (HWFET), 3.71% (UDDS), and 4.09% (US06); the most demanding case remains below 4.75%. These statistics are computed on windows containing battery faults. Fault-free conditions approach approximately 3.3% retained data.

The current CLI records `raw_len/down_len` as `compression_ratio` and separately prints retained rate `down_len/raw_len`. That named ratio is the inverse orientation of the paper’s retained-percentage definition, and the current code does not restrict or report fault-containing windows.

## 12. Dataset/protocol information

The paper’s data comprise:

- laboratory fault-injection data from four lithium-ion cell types: prismatic ternary, cylindrical 18650 LFP, blade ternary, and blade LFP;
- operating profiles including CC, UDDS, US06, DST, and HWFET;
- five fault classes: ISC, ESC, PCF, SDF, and ICF;
- cleaned and labelled raw measurements, trajectory slicing, and data augmentation;
- 3,000 laboratory samples, 500 per class;
- real-world energy-storage data from another LFP battery type: 200 continuously operating cells monitored for 1,203 hours;
- Zenodo data availability at DOI [10.5281/zenodo.18471156](https://doi.org/10.5281/zenodo.18471156), and original code at [Cuadger/DDP-based-dowm-sampling](https://github.com/Cuadger/DDP-based-dowm-sampling).

The current package expects flat CSVs containing `cur` and `vol_1 ... vol_N`, with optional numeric `time_s`/`orig_idx`. It has no implementation of the paper’s cleaning, labelling, trajectory slicing, augmentation, fault-window selection, or battery-type protocol. This is a dataset/protocol difference, not a source-code fix to make during this phase.

## 13. Complete Paper vs Code verification table

Statuses are exactly one of the requested categories: `PAPER MATCH`, `CODE DIFFERS`, `PAPER DOES NOT SPECIFY`, `CODE ADDS EXTRA BEHAVIOR`, or `CANNOT DETERMINE`.

| Item | Paper | Current Code | Status | Paper Evidence | Action |
|---|---|---|---|---|---|
| 1. Exact VDD definition/equation | VDD measures dispersion among cell-voltage trajectories; equation is in unavailable S5 | Custom centered pairwise divergence, max over selected cells | CANNOT DETERMINE | Methods, printed p. 9, says VDD/CDD calculations are in S5 | Obtain S5; do not alter equation yet. |
| 2. Exact CDD definition/equation | CDD describes voltage dynamics decoupled from current variation; equation is in unavailable S5 | Voltage range/current-range quantity with full-series floor | CANNOT DETERMINE | Methods, printed p. 9, delegates calculation to S5 | Obtain S5; verify denominator and units. |
| 3. Exact DDP definition | DDP is constructed from VDD and CDD and controls sampling | Uses VDD/CDD jointly; no separate scalar DDP | PAPER MATCH | Results, printed p. 4; Methods Equation 1 | Preserve the two-indicator decision abstraction unless S5 says otherwise. |
| 4. Representative-cell selection | Not present in supplied main PDF; delegated to S5 | Five extrema/range/variance criteria | CANNOT DETERMINE | S5 reference in Methods, printed p. 9 | Verify from S5. |
| 5. Divergence calculation | Not present in supplied main PDF; delegated to S5 | Centering, negative-product transform, normalized pair divergence | CANNOT DETERMINE | S5 reference in Methods, printed p. 9 | Verify equation and normalization from S5. |
| 6. Alpha and beta | Not present in supplied main PDF | Defaults α=0.3, β=2.0 | CANNOT DETERMINE | No α/β in main PDF; S5 unavailable | Treat values as unverified project parameters. |
| 7. Square-wave/perturbation procedure | Not present in supplied main PDF | Enabled by default for VDD and CDD with configurable amplitudes | CODE ADDS EXTRA BEHAVIOR | No square-wave description in supplied paper | Do not call this paper baseline without S5 evidence. |
| 8. VDD threshold | 0.43 | 0.415 default | CODE DIFFERS | Results, printed p. 4, Figure 3 discussion | Baseline threshold must be verified/changed later; no change now. |
| 9. CDD threshold | 0.007 | 0.007 default | PAPER MATCH | Results, printed p. 4, Figure 3 discussion | Preserve pending S5 unit/equation verification. |
| 10. Threshold operators | VDD/CDD both `<` for low, both `>` for high, otherwise middle | Same strict comparisons | PAPER MATCH | Methods Equation 1 | Preserve strict operators in base grading. |
| 11. HIGH/MID/LOW decision table | High/original only when both exceed; low only when both are below; otherwise middle | Same base decision table | PAPER MATCH | Methods Equation 1 | Preserve base decision rule. |
| 12. Original/high-frequency definition | `F0`, the original sampling frequency | Configured high interval defaults to 1 s | CODE DIFFERS | Methods Equation 1 | Use measured/original cadence when baseline is implemented. |
| 13. Middle-frequency interval | 5 s | 5 s default | PAPER MATCH | Methods Equation 1 and Results, printed p. 4 | Preserve 5 s after cadence contract is defined. |
| 14. Low-frequency interval | 30 s | 30 s default | PAPER MATCH | Methods Equation 1 and Results, printed p. 4 | Preserve 30 s. |
| 15. Window size | Not stated in supplied main PDF; S5 referenced | 50 rows | CANNOT DETERMINE | S5 reference in Methods, printed p. 9 | Do not label 50 as paper value. |
| 16. Window movement/step | Not stated in supplied main PDF; S5 referenced | 1 row default, optional forward-filled larger step | CANNOT DETERMINE | S5 reference in Methods, printed p. 9 | Verify from S5. |
| 17. Window boundary handling | Not stated in supplied main PDF | Centered window shifted inward at boundaries | CANNOT DETERMINE | No boundary rule in supplied PDF | Verify from S5/S6. |
| 18. Segment formation | Merge short segments into subsequent higher-priority segment; then fixed-length fragments | Run-length segments plus neighbor borrowing/merging; no fixed LLM fragments | CODE DIFFERS | Methods, printed p. 9 | Reconcile with S6 before baseline correction. |
| 19. Minimum segment lengths | Short segments exist, numeric lengths not stated in supplied PDF | HIGH 20, MID 10, LOW 50 rows | CANNOT DETERMINE | Methods says “short segments”; S6 pseudocode unavailable | Verify exact thresholds from S6. |
| 20. Segment-length correction exists | Yes, short segments are merged | Yes, minimum lengths enforced | PAPER MATCH | Methods, printed p. 9 | Preserve concept; verify exact policy. |
| 21. Overlapping/shared sampling regions | Not stated | Default `overlap_mode="share"` can place a timestamp in multiple sets | CODE ADDS EXTRA BEHAVIOR | No overlap rule in supplied PDF | Do not present shared masks as paper behavior. |
| 22. Sampling includes segment endpoints | Not stated | Start included; final point is not forced for stepped segments | CANNOT DETERMINE | No endpoint rule in supplied PDF | Verify from S6/pseudocode. |
| 23. Timestamp/cadence assumptions | Uses original frequency `F0`; exact cadence contract not stated | Assumes configured `output_interval_s`; synthesizes times if absent | CODE DIFFERS | Methods Equation 1 defines relative to `F0` | Preserve timestamps and establish cadence explicitly. |
| 24. Data-retention calculation | Retained/original × 100%, especially fault-containing windows | Row counts; prints retained rate and inverse raw/down ratio | CODE DIFFERS | Results, printed pp. 4–5 | Report paper-style retained percentage separately. |
| 25. Compression calculation | Smaller retained percentage means stronger compression; medians by operating condition | Per-file and aggregate row-count ratios, no fault-window stratification | CODE DIFFERS | Results, printed p. 5 | Reproduce paper stratification and statistic definition. |
| 26. Dataset preprocessing | Cleaning, labelling, trajectory slicing, augmentation; specific lab/field protocols | Generic CSV read; no cleaning, slicing, augmentation, or fault labels | CODE DIFFERS | Results, printed p. 3 | Add a verified preprocessing protocol later, outside this phase. |
| 27. Fault-region preservation/evaluation | Fault-containing windows used for compression; downstream CA/SA evaluate diagnosis; high-frequency data preserve transient signatures | No fault-region metric or preservation test; no diagnosis evaluation | CODE DIFFERS | Results pp. 4–6; Methods p. 10 | Define a separate reproduction evaluation before claiming preservation. |

## 14. Exact discrepancies that must be fixed

These are verification findings only; no fixes are applied in this phase.

1. `vdd_thres=0.415` differs from the paper’s reported `φVDD=0.43`; `cdd_thres=0.007` matches the reported `φCDD=0.007`.
2. The code’s high interval is a fixed one-second default, while the paper’s high region is the original frequency `F0`.
3. The paper’s segment procedure explicitly merges short segments with the subsequent higher-priority segment and then creates fixed-length LLM-sized fragments. The current code uses a different bidirectional minimum-length reassignment and does not create those fixed-length fragments.
4. The current `share` overlap mode is not described in the supplied paper and must not be treated as baseline.
5. The current compression ratio field (`raw_len/down_len`) is oriented differently from the paper’s retained/original percentage and is not stratified to fault-containing windows.
6. The current generic CSV pipeline does not implement the paper’s data cleaning, labels, trajectory slicing, augmentation, or fault-window evaluation.
7. Exact VDD/CDD equations, representative-cell procedure, α/β, window details, exact segment thresholds, and endpoint rules remain unresolved because S5/S6 were not supplied.

## 15. Code behavior that should be preserved

Pending S5/S6 verification, the following behavior agrees with the main paper and should be preserved:

- the conceptual DDP decomposition into VDD and CDD;
- the strict two-threshold decision table for base grades;
- the reported 5-second middle and 30-second low intervals;
- explicit preservation of source row identity and selected signal columns;
- separation of metric calculation, segmentation, index selection, configuration, and CLI orchestration;
- retaining high-frequency data around high-DDP/fault-relevant transitions as the intended design objective.

These are preservation recommendations, not permission to refactor or alter source in this phase.

## 16. Code behavior that is NOT part of the paper

Based on the supplied main PDF, the following are code-specific or unsupported:

- default VDD threshold 0.415;
- α=0.3 and β=2.0;
- default voltage/current square-wave injection and their amplitudes;
- the exact five representative-cell heuristics;
- 50-row centered windows and one-row steps;
- the full-series current-range floor in CDD;
- minimum lengths 20/10/50 and the exact `extend`/`discard` implementation;
- shared/overlapping sampling masks;
- failure to force stepped-segment endpoints;
- one-second high interval as a universal original cadence;
- inverse row-count compression ratio as the primary field;
- generic `cur`/`vol_*` schema handling without paper preprocessing.

Some of these may appear in unavailable S5/S6; until verified, they must remain classified as unsupported rather than definitively contradicted.

## 17. Ambiguities that remain

1. The provided PDF omits Methods S5, so exact VDD and CDD equations, representative-cell selection, α/β, threshold derivation, and window details cannot be determined.
2. The provided PDF omits Methods S6, so exact short-segment minimums, priority ordering details, fragment length, overlap, and endpoint inclusion cannot be determined.
3. The PDF text layer renders Equation 1’s division bars ambiguously; its surrounding narrative clearly identifies 30-second and 5-second intervals, but the original typeset equation should be checked against S5/S6.
4. The paper does not state a universal raw timestamp cadence in the supplied main article; only the relative original frequency `F0` is defined.
5. “Compression ratio” is defined as retained percentage in the paper, while code uses a field named compression ratio for the inverse row-count ratio. Both quantities can coexist, but they must not be conflated.
6. The paper reports compression on fault-containing windows, but the exact window-selection implementation and aggregation details are not in the supplied main PDF.

## 18. Recommended baseline configuration

This is a verification target, not a request to edit `config.py` now.

| Parameter | Recommended verified baseline | Confidence |
|---|---|---|
| VDD threshold | `0.43` | Main paper explicitly reports it; S5 threshold derivation unavailable. |
| CDD threshold | `0.007` | Main paper explicitly reports it; S5 units/equation unavailable. |
| High/original interval | `F0` / measured original cadence | Main Equation 1; do not hard-code 1 s without dataset verification. |
| Middle interval | `5 s` | Main Equation 1/results. |
| Low interval | `30 s` | Main Equation 1/results. |
| Grade operators | both `<` → low; both `>` → high; otherwise middle | Main Equation 1. |
| Window size/step/anchor | **UNVERIFIED** | Obtain S5. |
| Representative cells | **UNVERIFIED** | Obtain S5. |
| VDD/CDD equations | **UNVERIFIED** | Obtain S5. |
| Square-wave options | **UNVERIFIED; disable only as an experiment, not as a claimed fix** | No main-paper evidence. |
| Segment minimum lengths | **UNVERIFIED** | Obtain S6. |
| Segment priority | subsequent higher-priority merge | Main Methods; exact priority and edge cases require S6. |
| Fixed-length fragments | required by main Methods conceptually; exact length **UNVERIFIED** | Obtain S6/LLM input protocol. |
| Overlap mode | **UNVERIFIED; do not claim `share` is paper baseline** | No main-paper evidence. |
| Retention metric | retained/original × 100%, fault-containing windows | Main Results. |

## Final summary

- **Exact paper equations:** Main PDF supplies Equation 1, the joint VDD/CDD sampling rule. Exact VDD and CDD equations are not present in the supplied file; the paper directs them to missing Methods S5.
- **Exact thresholds:** VDD `0.43`; CDD `0.007`.
- **Exact sampling rules:** both below thresholds → 30-second interval; both above → original `F0`; otherwise → 5-second interval. Strict inequalities make equality middle.
- **Exact differences from code:** VDD default 0.415; high interval fixed at 1 s rather than `F0`; segment correction/fixed-fragment behavior differs; shared masks, square waves, current-floor behavior, row-count ratio, and preprocessing are unsupported by the supplied paper.
- **What must be changed later:** only after obtaining S5/S6—threshold, original-cadence handling, segment algorithm, fixed-fragment generation, compression metric/reporting, and paper-compatible preprocessing/evaluation.
- **What must not be changed now:** all Python source files, `PAPER_VS_CODE_AUDIT.md`, and every unresolved scientific equation/parameter. This phase created only `PAPER_VERIFICATION_REPORT.md`; it does not claim successful reproduction.
