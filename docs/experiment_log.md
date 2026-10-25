# Experiment log

Append-only record of runs that produced citable numbers. Interpretation and decisions are in the phase analysis documents.

## EXP-001 | 2026-10-25 | Phase 2 exploratory analysis

- **Question:** Describe return and risk, all 15 pair correlations, S&P 500 sensitivity, their stability, and VIX context for 2018-2025.
- **Change from previous:** First run.
- **Data:** `data/processed/master_historical.csv` (SHA-256 `99fdcd48...f0b4`), 2,011 sessions from 2018-01-02 to 2025-12-31; returns from 2018-01-03. Nothing is fitted for later use. VIX boundaries were estimated on the same 2,010 return dates they describe. The unseen period was not touched.
- **Settings:** `configs/eda.json` (60-session rolling window, sqrt(252) annualization, VIX terciles with linear quantiles, minimum 3 observations); no random seed involved. Command `uv run --locked python scripts/run_eda.py`; methods adopted before the run, with no variants tried.
- **Environment:** Python 3.12.13, pandas 3.0.6, NumPy 2.5.4, statsmodels 0.15.0, matplotlib 3.11.2 (uv.lock after adding the last three).
- **Result:** 22 checks passed. Daily-return correlations 0.525 (NVDA_META) to 0.708 (MSFT_GOOGL); whole-period betas 1.16 (GOOGL) to 1.82 (NVDA); VIX boundaries 15.93 and 20.743; rolling correlations -0.040 to 0.952. Tables in `outputs/metrics/eda/`, figures in `outputs/figures/eda/`.
- **Status:** Completed. Repeated in Docker with `run_pipeline.py --historical-only`: same input hash, largest table difference 1.3e-15 (`outputs/metrics/phase2_docker_validation.json`).
- **Interpretation:** All pairs are positively but loosely correlated in returns, and the correlations moved a lot over time; this says nothing yet about cointegration.
- **Next:** Phase 3 tests all 15 pairs for cointegration.

## EXP-002 | 2026-10-25 | Phase 2 review and rerun

- **Question:** Do the implemented calculations reproduce independently, and do the review corrections change EXP-001's results?
- **Change from previous:** Fixed missing correlations in the symmetry check and matrix diagonal, and the count of incomplete windows when history is shorter than the rolling window. Both new regression tests failed before the fixes and passed afterwards. Corrected the notebook and analysis explanations of correlation, unexplained variation, and log-price gaps.
- **Data:** Same historical master and SHA-256 as EXP-001. Prices cover 2018-01-02 to 2025-12-31; returns cover 2018-01-03 to 2025-12-31. OLS fits and VIX groups describe their own historical estimation dates; there is no separate evaluation window. The historical-only Docker run has no unseen master. The default full pipeline also rebuilt the 2026 master as part of Phase 1; EDA never read it, and no analytical choice used unseen results.
- **Settings:** Unchanged `configs/eda.json`; 60-session rolling window, sqrt(252) annualization, linear VIX terciles, minimum 3 observations, no random seed. Re-executed `notebooks/02_eda.ipynb` with `uv run --locked jupyter nbconvert --to notebook --execute --inplace notebooks/02_eda.ipynb`; Docker commands are in the README.
- **Environment:** Same locked dependencies as EXP-001; Python 3.12.13 on Windows and in Docker. Corrected code hashes are in `outputs/metrics/eda/run_metadata.json` and `outputs/metrics/phase2_review_validation.json`.
- **Result:** All ten local CSV hashes match EXP-001. All nine notebook code cells executed without errors; 22 run checks and 31 tests passed locally and in Docker. Independent checks covered 63 return/drawdown windows, 54 benchmark regressions, 29,265 complete rolling windows, and 45 VIX pair correlations. Docker table differences are at most 1.3322676295501878e-15. See `outputs/metrics/phase2_review_validation.json` and `outputs/metrics/phase2_docker_validation.json`.
- **Status:** Completed; historical-only and default full Docker pipelines exited with code 0.
- **Interpretation:** EXP-001's numeric results are unchanged. Its description of correlations as "loosely" correlated is replaced by the actual range, 0.525 to 0.708, in the analysis; these descriptive results do not establish cointegration or explain the causes of residual variation.
- **Next:** Phase 3 tests all 15 pairs for cointegration.
