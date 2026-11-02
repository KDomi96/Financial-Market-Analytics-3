# Phase 5 analysis: LSTM forecasts and the entry filter

2 November 2026

The LSTM does not improve on persistence on the unseen interval for either
exploratory pair, at any of the five horizons. The day-five filter leaves AMZN
on META's trades unchanged. For AMZN on NVDA, it rejects the first long
crossing and accepts a later one, reducing the net account return from 21.83%
to 21.00%. On the 2024-2025 validation years, the same fixed filter had
already rejected seven of eight AMZN-on-NVDA short entries and turned a 6.43%
baseline return into -2.75%. The settings were fixed before either
evaluation; no model or filter search followed them.

All figures below come from run `phase5_v2`. It repeats the first evaluated
run, `phase5_v1`, with identical settings after review fixes to the saved
diagnostics; the reasons are given under verification.

## Historical model selection

Each pair uses 1,466 earlier training windows and 498 validation windows.
OLS is fitted on 2018-01-02 through 2023-12-29, with normalization from 250
sessions in 2023. The scaler uses the 1,485 distinct dates present in training
inputs. All training targets end by 2023-12-29; validation targets begin on
2024-01-02. Known earlier observations provide validation input context.

The shortlist and directions were selected through 2025. Refitting these
earlier objects prevents validation observations entering their estimates,
but validation remains conditional on that shortlist. It is not a separate
test of pair selection.

The four seed-42 configurations cross 16/32 hidden units with learning rates
0.001/0.0003. Both pairs select 32 units and learning rate 0.001. Their best
epochs are 22 and 29. The final networks start from fresh weights and train
for those counts on 1,968 windows through 2025, with no further stopping set.
Final OLS and normalization are loaded from Phases 3 and 4.

| Pair | Selected epoch | Validation LSTM RMSE | Persistence RMSE | Relative RMSE improvement |
| --- | ---: | ---: | ---: | ---: |
| AMZN_META, AMZN on META | 22 | 0.406094 | 0.405886 | -0.05% |
| NVDA_AMZN, AMZN on NVDA | 29 | 0.330322 | 0.340828 | 3.08% |

These are pooled errors across all five horizons, in Z units. Selection uses
this forecast error, not backtest returns, and the same validation years
also chose each trial's stopping epoch. The validation figures are therefore
selection evidence and flatter the chosen models.

For AMZN on META, no seed-42 configuration beat persistence on validation;
the four were worse by 0.05% to 0.63%. The seed-7 check stopped at its first
epoch with RMSE 0.405855, essentially the persistence value of 0.405886.
Seed choice mattered more than configuration: the three seeds of the chosen
design range from 0.400833 to 0.406094, while the four configurations range
from 0.406094 to 0.408457. The selection of 32 units and 0.001 therefore does
not show that this design is better for this pair. For AMZN on NVDA, all six
trials beat persistence on validation, by 1.8% to 3.1%, but that advantage
does not carry into the unseen period.

The validation curves are also flat near their minimum. For AMZN on META,
epochs 19, 25, 27, and 30 are within 0.0005 of epoch 22's validation MSE; for
AMZN on NVDA, epochs 25, 30, 31, 33, and 35 are within 0.0005 of epoch 29's. After the best
epoch, validation MSE rises from 0.1649 to 0.1820 and from 0.1091 to 0.1409
within 20 epochs while training error keeps falling. The final refit has 31
batches per epoch against 23 in selection, so the same epoch count gives
about 35% more updates. Whether that moved the final models past their best
point cannot be checked without using the unseen data. The trials, epochs,
settings, and unsuccessful alternatives are saved in
[`trials.csv`](../../outputs/metrics/lstm/phase5_v2/trials.csv) and
[`epoch_history.csv`](../../outputs/metrics/lstm/phase5_v2/epoch_history.csv),
and the learning-curve figures draw persistence for comparison. The chosen
records are in
[`selection.json`](../../outputs/metrics/lstm/phase5_v2/selection.json).

## Direction of the day-five forecast

The filter uses only the sign of the predicted day-five change, which RMSE
does not measure. The table compares the selected model's validation
direction accuracy with three rules that use no model: the more common
realized sign, a move toward the fitted-period resting level, and a move
toward zero.

| Pair | Selected LSTM | More common sign | Toward resting level | Toward zero |
| --- | ---: | ---: | ---: | ---: |
| AMZN_META | 53.61% | 51.61% | 48.39% | 53.01% |
| NVDA_AMZN | 62.45% | 50.80% | 59.44% | 49.20% |

For AMZN on NVDA, the model is about three points better than simply
predicting a move toward the selection-stage resting level of 2.784. For AMZN
on META, it matches a move toward zero. The AMZN-on-META seed checks agree
with seed 42 at all 22 forecast-covered validation crossings, but that is not
evidence of a stable signal. All 22 are long crossings, and the three seeds
predict a rise at 79%, 97%, and 88% of all validation origins (seeds 42, 7,
and 2026). They agree because they share the same upward lean. For AMZN on
NVDA, each extra seed agrees at 12 of 15 crossings. These counts include
crossings while a position is already held; they are not executed trades. See
[`seed_agreement.csv`](../../outputs/metrics/lstm/phase5_v2/seed_agreement.csv)
and the dated
[`direction diagnostics`](../../outputs/metrics/lstm/phase5_v2/direction_diagnostics.csv).

## Validation trading

The selection stage also ran the matched baseline and the filtered strategy on
2024-2025, using the 2018-2023 spread and its beta. These runs describe the
fixed filter. They did not choose the model, and no rule changed after them.

| Pair and strategy | Executed entries | Closed / open | Filter rejections | Net account return | Maximum net drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| AMZN_META, matched baseline | 2 | 2 / 0 | 0 | 27.45% | 9.05% |
| AMZN_META, LSTM filter | 2 | 2 / 0 | 0 | 27.45% | 9.05% |
| NVDA_AMZN, matched baseline | 1 | 0 / 1 | 0 | 6.43% | 30.42% |
| NVDA_AMZN, LSTM filter | 1 | 0 / 1 | 7 | -2.75% | 26.94% |

For AMZN on META, both long entries pass the filter and the accounts are
identical. For AMZN on NVDA, all seven rejections are short crossings at Z
between 2.03 and 2.34, each with a small predicted rise of 0.04 to 0.08. Those
forecasts point toward the selection-stage resting level of 2.784, which sits
above the +2 entry threshold. By the fifth session, Z had in fact risen after
four of the rejections and fallen after three. The eighth crossing, on 1 July
2024, was accepted with a predicted change of -0.002, a margin too small to
mean much. Neither AMZN-on-NVDA position ever closed: Z never returned to zero
in these two years. The baseline's short, entered on 5 February 2024, was
marked at USD 642.80; the filtered short, entered on 2 July 2024, at a loss
of USD 275.34. Every eligible entry and its forecast are listed in
[`filter_decisions.csv`](../../outputs/metrics/lstm/phase5_v2/filter_decisions.csv).

This result was available before the unseen evaluation. The final-stage
resting levels, 0.574 and -0.467, lie inside the ±2 band, so the same
mechanism should not reject 2026 entries in the same way. The validation
result therefore says more about the 2023 normalization than about how the
filter would behave on the final scale.

## Unseen forecast errors

The final artifacts use the same OLS and fixed 2025 normalization as Phase 4.
There are 141 forecast origins per pair, from 2025-12-31 through 2026-07-24,
and 705 origin/horizon predictions. Their targets finish on 2026-07-31.
Each horizon has 141 errors. Overlapping horizons reuse target dates, so
705 predictions do not represent 705 independent market outcomes.

| Pair | LSTM MAE | Persistence MAE | LSTM RMSE | Persistence RMSE | Relative RMSE improvement |
| --- | ---: | ---: | ---: | ---: | ---: |
| AMZN_META | 0.394595 | 0.376237 | 0.575604 | 0.538715 | -6.85% |
| NVDA_AMZN | 0.516850 | 0.493530 | 0.710382 | 0.688589 | -3.16% |

Persistence is better on both pooled measures and at every horizon. By
horizon, the LSTM's RMSE is 2.5% to 8.2% worse for AMZN on META and 1.4% to
4.1% worse for AMZN on NVDA. The forecasts often track persistence closely
because the learned change is small relative to Z. That visual resemblance
does not establish useful incremental skill. The last AMZN-on-META move is
also visible in the horizon-five plot rather than removed from scoring.

Per-horizon and pooled results are in
[`unseen_forecast_metrics.csv`](../../outputs/metrics/lstm/phase5_v2/unseen_forecast_metrics.csv).
Every forecast, origin, target date, and realized value is saved in
[`forecasts.csv`](../../outputs/predictions/lstm/phase5_v2/unseen/forecasts.csv).
The figures under `outputs/figures/lstm/phase5_v2/unseen/` compare observed,
LSTM, and persistence values at horizons one and five and show errors by
horizon.

## Strategy comparison

Each account starts flat on 2 January 2026. The 31 December forecast is
scored but cannot carry an entry order into the period. The two strategies
share 140 entry-eligible origins, ending on 24 July. Observed-Z exits,
next-open fills, and daily valuation continue through 31 July. The final
calendar restriction suppresses a final-day AMZN-on-NVDA short signal that
would have remained unfilled in Phase 4, so it changes no completed return.
The original full-period baseline is retained in the comparison table.

| Pair and strategy | Executed entries | Closed / open | Closed-trade win rate | Net account return | Costs (USD) | Maximum net drawdown |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AMZN_META, matched baseline | 2 | 1 / 1 | 100% | -3.69% | 14.60 | 12.37% |
| AMZN_META, LSTM filter | 2 | 1 / 1 | 100% | -3.69% | 14.60 | 12.37% |
| NVDA_AMZN, matched baseline | 2 | 2 / 0 | 100% | 21.83% | 20.06 | 5.77% |
| NVDA_AMZN, LSTM filter | 2 | 2 / 0 | 100% | 21.00% | 20.03 | 5.75% |

For AMZN on META, both short entries pass the filter. The closed trade earns
USD 967.19 net; the remaining open trade is marked at a net loss of
USD 1,336.36. That open loss is included in the account return but excluded
from win rate. The 100% win rate therefore describes one closed trade and
does not mean the account made money.

For AMZN on NVDA, the filter rejects the long signal on 11 February. Z was
-2.181 and the model expected it to fall to -2.401 by 19 February. Z did fall
at first, to -2.522 on 12 February, and stayed below -2.181 for three
sessions, but by 19 February it had risen to -2.058, so the day-five direction
was wrong. A fresh crossing on
23 February is accepted and filled on 24 February. This is a new crossing,
not a delayed fill of the rejected order. Both versions exit that long on 10
April. The baseline's net long-trade P&L is USD 1,315.63; the filtered version
earns USD 1,232.46. Their later short trade is the same. The difference in
final equity is USD 83.17, or 0.83 percentage points of initial capital. The
whole unseen comparison therefore rests on this one decision. Of the five
unseen filter decisions with a scored forecast, the day-five direction was
right twice; they are listed in
[`unseen_filter_decisions.csv`](../../outputs/metrics/lstm/phase5_v2/unseen_filter_decisions.csv).

The filtered AMZN-on-NVDA account sees four state-eligible entry signals
versus three for the baseline because their positions differ after the first
rejection. It records one forecast rejection and one calendar exclusion.
Signals, accepted orders, and executed trades remain separate counts.

The accounts use the same USD 10,000, 5-bps turnover charges, beta-weighted
fixed shares, and final marking rules. The filtered AMZN-on-NVDA gross leg
contributions are USD 2,116.52 from AMZN and USD 3.51 from NVDA. This exposure
is not dollar neutral. Neither the positive return nor the two closed wins
establish general trading skill. Both pairs share AMZN and remain separate
exploratory accounts.

The figures and
[`unseen_strategy_comparison.csv`](../../outputs/metrics/lstm/phase5_v2/unseen_strategy_comparison.csv)
use the detailed ledgers under
`outputs/backtests/lstm_comparison/phase5_v2/unseen/`. No rule was changed to
improve these outcomes.

## Fitted scales and limits

The regression-window residual mean is zero, but normalization centers Z on
the final year. Its corresponding level, `-mean/std`, is 1.066 and 2.784 in
selection-stage Z units and 0.574 and -0.467 in final-stage units. The
validation section shows the consequence for the earlier AMZN-on-NVDA spread.
I retain the fixed rule and report this difference rather than translating a
validation trading result directly into a final-stage expectation. The
model's change targets reduce the need to learn the level itself but do not
remove this interpretation problem.

Only two pairs, a single validation block, and a few unseen trades are
available. The 2026 interval was already examined in Phase 4. It stayed out
of this model's fitting and selection, but is not a newly untouched test.
Borrow charges, financing, dividends, and broker margin constraints remain
omitted as in Phase 4.

## Verification and reproducibility

The first evaluated run, `phase5_v1`, saved diagnostics that left out base
rates and the dated filter decisions, and its `ignored_reason` field mixed
filter rejections with Phase 4's ignored crossings. Its evaluation contract
fixes the code of an evaluated version, so I repeated the run as `phase5_v2`
with identical settings instead of editing v1. Of the 102 files the two runs
share, 84 are byte-identical, including every weight file, forecast, ledger,
and daily account. The other 18 differ only in version labels, run records,
the added base-rate columns, the restored `ignored_reason` field, and the two
learning-curve figures. The v1 files are kept unchanged.

The notebook runs top to bottom and imports the shared implementation; its
re-execution repeated the frozen v2 run, which would have stopped if any saved
byte had changed. All 77 tests pass locally and in Docker. Both local pipeline
modes complete, and afterwards the 104 v2 files, the 104 v1 files, and the
tracked earlier-phase outputs keep their hashes.

Both fresh Docker pipeline modes complete. Linux retraining gives the same
sample dates, selected configurations, epochs, and trading decisions in all
72 compared files. Its forecasts differ from the Windows run by up to 0.017
Z units. The plan required exact discrete agreement for retraining and set
its float32 tolerance for inference with identical weights, because PyTorch
does not promise identical training across platforms. Loading the saved
Windows weights in Docker reproduces the known forecasts within 1.49e-8. The
reported tables and final artifacts use the Windows CPU run.

Verification records are
[`phase5_review_validation.json`](../../outputs/metrics/phase5_review_validation.json)
and [`phase5_docker_validation.json`](../../outputs/metrics/phase5_docker_validation.json);
the v1 records are kept with a `phase5_v1_` prefix. The experiment log records
EXP-005 to EXP-007. The runnable notebook is
[`05_lstm_comparison.ipynb`](../../notebooks/05_lstm_comparison.ipynb).
