# Phase 3 analysis: comparing the pairs

1 November 2026

AMZN_META is the only pair with nominal support from Engle-Granger and
Johansen at 5%. It does not survive the pair-level Holm adjustment. No pair
meets all the adopted support conditions, so the two shortlisted pairs,
AMZN_META and NVDA_AMZN, continue as exploratory candidates.

The input is `data/processed/master_historical.csv`: 2,011 sessions from
2018-01-02 to 2025-12-31, including the first session because these tests use
prices rather than returns. All 15 pairs were tested, with both OLS directions
retained. The settings in
[methodology](../methodology.md#phase-3-pair-selection) were adopted before the
run and were not varied in response to the results. No unseen master or raw
2026 observations were read by the analysis.

## Integration and directional tests

Source: [`integration_tests.csv`](../../outputs/metrics/pair_selection/integration_tests.csv)
and [`directional_tests.csv`](../../outputs/metrics/pair_selection/directional_tests.csv).

For every stock, ADF fails to reject a unit root in log levels with a trend
and rejects it in first differences with a constant. Level p-values range
from 0.301 for AMZN to 0.715 for META. These results are consistent with I(1),
which is the maintained assumption for the cointegration tests. Failure to
reject is not proof that a unit root exists.

Only one of the 30 directional Engle-Granger tests rejects at 5%: AMZN on
META, with p=0.01419. Reversing that relationship gives p=0.06575, so even
this pair's nominal finding depends on direction. The selected regression is

`log(AMZN) = 1.517679 + 0.599428 * log(META) + spread`.

The direction is chosen by the smaller Engle-Granger p-value, not by OLS
R-squared. The saved residual ADF statistic matches the Engle-Granger statistic,
but its ordinary ADF p-value is not used as cointegration evidence.

## Johansen and the multiple-testing check

Source: [`johansen_tests.csv`](../../outputs/metrics/pair_selection/johansen_tests.csv),
[`lag_selection.csv`](../../outputs/metrics/pair_selection/lag_selection.csv),
and [`pair_ranking.csv`](../../outputs/metrics/pair_selection/pair_ranking.csv).
Figure: [`method_comparison.png`](../../outputs/figures/pair_selection/method_comparison.png).

BIC chooses a levels lag of one for nine pairs and two for six pairs. No
choice reaches the upper bound of ten. Johansen therefore uses zero or one
lagged differences. Its trace and maximum-eigenvalue tests agree on the 95%
rank for every pair: rank one for AMZN_META and zero for the other fourteen.
There are no rank-two results at that confidence level.

For AMZN_META, the trace statistic for rank zero is 17.5972, above its 95%
critical value of 15.4943. The next statistic is 0.3813, below 3.8415, so the
sequential decision is rank one. The maximum-eigenvalue test gives the same
rank. At 99%, both methods give rank zero. The result depends on the selected
significance level; none of these tests supplies a Johansen p-value.

In the comparison figure, the rank-one statistic is above its critical value
for GOOGL_AMZN, GOOGL_META, and MSFT_GOOGL. Those pairs still have rank zero,
because the sequential test stops when rank zero is not rejected.

AMZN_META's pair p-value is `2 * 0.0141932 = 0.0283864`. After Holm adjustment
over all 15 pairs it is 0.425796. Every other adjusted pair p-value is 1.
The adjustment accounts for choosing a direction and searching across pairs.
Johansen uses the same prices and is not an independent replication. Its
nominal support does not remove the multiple-testing limitation.

## Shortlist and stability

Source: [`shortlist.csv`](../../outputs/metrics/pair_selection/shortlist.csv),
[`half_life.csv`](../../outputs/metrics/pair_selection/half_life.csv), and
[`hedge_stability.csv`](../../outputs/metrics/pair_selection/hedge_stability.csv).
Figures: [`residual_histories.png`](../../outputs/figures/pair_selection/residual_histories.png),
[`hedge_stability.png`](../../outputs/figures/pair_selection/hedge_stability.png), and
[`pair_fits.png`](../../outputs/figures/pair_selection/pair_fits.png).

| Rank | Pair | Selected direction | Raw EG p | Pair Holm p | Nominal agreement | Label |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | AMZN_META | AMZN on META | 0.01419 | 0.42580 | Both methods | Exploratory |
| 2 | NVDA_AMZN | AMZN on NVDA | 0.12107 | 1.00000 | Neither method | Exploratory |

The ranking rule puts agreement by both methods first, then one, then neither.
Within each group it uses the selected raw Engle-Granger p-value. AMZN_META
comes first under that rule. NVDA_AMZN has the smallest selected p-value among
the remaining pairs, but neither test rejects for it. It is included because
the adopted plan carries two candidates forward even when the evidence is
weak, not because its test result qualifies as cointegration.

The two methods disagree about NVDA_AMZN. Its selected Engle-Granger p-value,
0.121, is the second smallest, but its Johansen trace statistic for rank zero,
4.84, is the third smallest of the 15 pairs. Of the pairs Johansen does not
reject at 95%, MSFT_AAPL comes closest, at 14.77 against a critical value of
15.49, and it has rank one at 90%. It ranks fourth because the rule orders pairs within the
"neither" group by the Engle-Granger p-value alone. I kept that rule because
it was fixed before the run. Picking the second pair after seeing these
numbers would make the shortlist depend on the results.

The fitted spread for the second pair is

`log(AMZN) - 4.152697 - 0.239636 * log(NVDA)`.

For AMZN on META, beta changes from 1.0405 in 2018-2021 to 0.4639 in
2022-2025. For AMZN on NVDA it changes from 0.4730 to 0.2949. These are
material changes in the estimated relationship. The full-period coefficients
remain the ones saved for the Phase 4 handoff; the subperiod fits are
diagnostics, not replacements chosen after seeing the results. All 15
full-period betas are positive, and none changes sign between the subperiods.

The AR(1) half-life estimates are 77.5 sessions for AMZN on META and 104.1 for
AMZN on NVDA. These are descriptive estimates from fitted historical residuals.
A coefficient below one in this auxiliary regression does not override the
cointegration tests or establish that either spread will revert in 2026.
Both half-lives are long relative to the later five-session forecast horizon,
and each is more than half of the 145 unseen sessions, so the Phase 4 backtest
may have few trades. The AMZN on META residual is also much quieter late in
the period: its standard deviation is 0.057 over 2023-2025 against 0.193 over
2018-2022, calculated from the saved spread file. That is the case the Phase 4
methodology warns about: a small 2025 standard deviation can keep |Z| above 2
for long periods.

## Reproduction and limitations

The script saves eight metric tables, a historical file with 15 explicitly
oriented residual columns, 15 fitted JSONs, and four figures. The notebook
imports the shared package and verifies output hashes and reconstruction of
all saved spreads. Run checks and fitted-object dates are recorded in
[`run_metadata.json`](../../outputs/metrics/pair_selection/run_metadata.json).

The final run is logged as
[EXP-003](../experiment_log.md#exp-003--2026-11-01--phase-3-pair-selection).
All 43 offline tests pass locally and in Docker, and the notebook executes all
five code cells without errors. Its repeat run reproduces all 24 saved output
hashes. Independent checks use centered sums for all 30 OLS directions, verify
their residual statistics and MacKinnon p-values, recalculate the pair-level
Holm adjustment, and check all 90 sequential Johansen rank decisions. The
largest independent coefficient difference is 4.4e-14. These checks were run
with a local review script that is not part of the repository; their results
are in `phase3_review_validation.json`.

The historical-only Docker pipeline rebuilds the master from the pinned raw
snapshots, runs EDA, and writes its own Phase 3 outputs. Its historical input
hash matches the local file, and its processed directory contains no unseen
master. The largest difference across the eight metric tables is 8.6e-11;
spread differences are at most 5.4e-15. Ranks, directions, labels, and shortlist
membership match exactly. See the
[Docker record](../../outputs/metrics/phase3_docker_validation.json) and
[review/independent-check record](../../outputs/metrics/phase3_review_validation.json).

The installed Johansen implementation emits casting warnings because its
eigenvalues and eigenvectors have complex dtype with imaginary parts exactly
zero. The run checks that condition before accepting the statistics and
records the warnings. A nonzero imaginary part, collinearity warning, failed
fit, or non-finite statistic stops the run. This handling changes no test
setting or decision.

The results are conditional on the chosen constant and lag specifications,
and ADF has limited power. Historical residual plots and half-lives use
coefficients fitted to those same dates, so they are in sample. Prices exclude
dividends. Both shortlisted spreads have AMZN as the dependent stock, so their
later trading results share one leg and are not independent of each other.
Neither an equilibrium relationship nor profitable trading has been
established by this phase.

Phase 4 will load the full-history coefficients and estimate normalization
from 2025 residuals only. Phase 5 must refit the regression on 2018-2023 for
2024-2025 model validation. That validation remains conditional on a shortlist
chosen through 2025; it is not independent validation of the pair-selection
process. Both later phases must retain the exploratory labels.
