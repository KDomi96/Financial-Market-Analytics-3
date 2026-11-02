# Phase 4 analysis: the statistical baseline

The fixed baseline loses 3.69% on AMZN on META and gains 21.83% on AMZN on
NVDA over the 145 sessions from 2 January to 31 July 2026. Each pair uses a
separate USD 10,000 account. Both remain exploratory: these trading results
do not change the weak cointegration evidence recorded in Phase 3.

## Fixed inputs and normalization

The regressions are loaded from `artifacts/statistical/phase3_v1/`, fitted
over 2018-01-02 to 2025-12-31. Neither direction nor coefficient is refitted.
The historical master is checked against its manifest and the Phase 3 input
hash. Reconstructed residuals agree with the saved historical spread file.

Each normalization fit uses 250 residuals from 2025-01-02 to 2025-12-31:

| Pair | Direction | 2025 mean | 2025 sample standard deviation |
| --- | --- | --- | --- |
| AMZN_META | AMZN on META | -0.03490503 | 0.06083657 |
| NVDA_AMZN | AMZN on NVDA | 0.02494542 | 0.05345223 |

Source: the two `normalization_2025.json` files under
[`artifacts/statistical/phase4_v1/`](../../artifacts/statistical/phase4_v1/).
The standard deviation uses `ddof=1`. The same fitted objects transform every
unseen observation. Evaluation loads and validates the saved files.

## Signals and spread behaviour

Source: [`spread_diagnostics.csv`](../../outputs/metrics/statistical_baseline/phase4_v1/unseen/spread_diagnostics.csv),
[`reversion_events.csv`](../../outputs/metrics/statistical_baseline/phase4_v1/unseen/reversion_events.csv),
and [`signals.csv`](../../outputs/backtests/statistical_baseline/phase4_v1/unseen/signals.csv).
Figure: [`zscores.png`](../../outputs/figures/statistical_baseline/phase4_v1/unseen/zscores.png).

| Count | AMZN on META | AMZN on NVDA |
| --- | --- | --- |
| Days below -2 / above +2 | 0 / 84 | 8 / 19 |
| Raw long / short crossings | 0 / 4 | 3 / 4 |
| Eligible long / short entry signals | 0 / 2 | 1 / 2 |
| Executed long / short entries | 0 / 2 | 1 / 1 |
| Closed trades / positions still open | 1 / 1 | 2 / 0 |

The headline signal counts are eligible crossings while flat. Crossings while
a position is open are retained with an ignored reason. AMZN on NVDA has a
short entry signal on 31 July with no following session inside the window,
so it is counted but unfilled. No August price is used.

AMZN on META spends 84 sessions, 57.93% of the interval, above +2. Its longest
consecutive run above that level lasts 62 sessions. The first eligible short
excursion, on 7 January, reaches zero on 6 February after 21 sessions. The
second, on 10 April, has not reached zero by 31 July, after 77 observed
sessions. It stays in the event table as right-censored. Z ends at 5.4551.
This spread does not show consistent reversion to the fixed 2025 mean over
the evaluation interval.

AMZN on NVDA has two eligible excursions that reach zero: the long signal on
11 February reaches it on 9 April, and the short signal on 24 April reaches
it on 22 June. Both take 39 sessions from signal close to zero close. The
longest runs below -2 and above +2 are six and eleven sessions. These episodes
show reversion during this interval; they do not establish a stable equilibrium.
The final unfilled short signal has zero follow-up sessions and is also
right-censored.

## Account results and the stock legs

Source: [`summary.csv`](../../outputs/metrics/statistical_baseline/phase4_v1/unseen/summary.csv),
[`trades.csv`](../../outputs/backtests/statistical_baseline/phase4_v1/unseen/trades.csv),
and [`daily_account.csv`](../../outputs/backtests/statistical_baseline/phase4_v1/unseen/daily_account.csv).
Figures: [equity](../../outputs/figures/statistical_baseline/phase4_v1/unseen/equity.png)
and [drawdown](../../outputs/figures/statistical_baseline/phase4_v1/unseen/drawdown.png).

| Measure | AMZN on META | AMZN on NVDA |
| --- | --- | --- |
| Gross account return | -3.55% | 22.03% |
| Net account return | -3.69% | 21.83% |
| Final net equity | USD 9,630.83 | USD 12,183.17 |
| Charged costs | USD 14.60 | USD 20.06 |
| Maximum net drawdown | 12.37% | 5.77% |
| Closed-trade wins | 1 of 1 | 2 of 2 |
| Closed-trade net P&L | USD 967.19 | USD 2,183.17 |
| Open-trade net P&L at the endpoint | USD -1,336.36 | USD 0.00 |

AMZN on META's first short enters on 8 January and exits on 9 February.
The second enters on 13 April and remains open at the endpoint. Its marked
loss more than removes the earlier profit. The closed-trade win rate is 100%
because there is only one closed trade; it excludes that open loss. Account
return includes the loss and the entry cost. No hypothetical exit cost is
charged on the open position.

The result depends heavily on the last two sessions. On 29 July the account
stood at USD 10,985.25 (+9.85%), with the open trade about break-even. It lost
USD 510.09 on 30 July and USD 844.33 on 31 July, when AMZN closed 15.32% higher
and META 3.28% higher, and Z rose from 1.98 to 5.46. Phase 1 flagged that AMZN
move as a daily return above 15% without investigating it. The 12.37% maximum
drawdown is this final fall from the 10 July peak, and the same move produced
AMZN on NVDA's unfilled short signal. The -3.69% therefore reflects the final
two sessions far more than the trade's behaviour over the rest of the period.

AMZN on NVDA enters long on 12 February and exits on 10 April for USD 1,315.63
net. Its short enters on 27 April and exits on 23 June for USD 867.54 net.
There are only two completed trades, so a 100% win rate has little evidence
behind it. These are execution dates; each decision was available at the
previous session's Close.

The beta-weighted holdings are not dollar-neutral or market-neutral. AMZN on
NVDA starts each trade with USD 6,130.71 of net exposure in the direction of
the trade. Leg P&L cannot show how much of a result came from the market: it
records which stock moved, not whether the move was shared. Instead I
estimate the market's share from the 2018-2025 S&P 500 betas saved in Phase 2
(AMZN 1.18, NVDA 1.82, META 1.32) and the S&P 500 move between each trade's
signal closes. The AMZN on NVDA position carries about USD 6,000 of market
exposure, and AMZN on META about USD 2,400. During both AMZN on NVDA trades
the S&P 500 moved against the position (-1.68% and +4.29%), so market exposure
accounts for roughly USD -357 of the USD 2,203 gross profit. The profit came
from AMZN moving relative to NVDA, not from the market. For AMZN on META, the
market accounts for about USD -239 of the open trade's USD -1,331 loss; the
rest is AMZN rising 14.4% while META fell 11.6%. This is a single-factor
estimate with historical betas, not an exact attribution. Source:
[`market_exposure.csv`](../../outputs/metrics/statistical_baseline/phase4_v1/unseen/market_exposure.csv),
calculated in the notebook after the unseen run.

Both accounts share AMZN. I report them separately rather than add the returns
or treat them as independent trials. Gross and net results use identical
fills and quantities; their difference is the charged cost allowance.

## Historical exercise and verification

The 2018-2025 replay produces five entries for AMZN on META and ten for AMZN
on NVDA. Their net account returns are 47.51% and 17.48%, respectively. These
are in-sample descriptions: the regressions use the entire historical period,
and even the early years use normalization estimated from 2025. They are
neither independent validation nor evidence of returns available at those
earlier dates. The replay also shows the risk of having no stop: AMZN on
NVDA's net equity falls 62.68% from its peak at one point, although nine of
its ten trades close with a profit, and AMZN on META's maximum drawdown is
25.33%. The unseen accounts carry no historical position or order.

All eight notebook code cells execute without errors. All 55 offline tests
pass locally and in Docker. Each period has 16 passing run checks. Repeated
local runs reproduce all 18 distinct CSV/artifact hashes. Independent checks
use scalar logarithms and sample statistics for normalization, verify signal
conditions, and rebuild every daily equity value from fills and source
Open/Close prices. The largest independent difference is 1.82e-11 USD. These
checks were run with a local review script that is not part of the
repository; their results are in `phase4_review_validation.json`.

Both Docker pipeline modes complete. The historical-only container has no
unseen master or Phase 4 unseen outputs. Eight CSVs per period and the two
normalization artifacts agree within `rtol=1e-7`, `atol=1e-9`. Signals, trade
dates, directions, counts, and statuses agree exactly. The largest CSV
difference is 2.18e-11. See the
[review record](../../outputs/metrics/phase4_review_validation.json),
[Docker record](../../outputs/metrics/phase4_docker_validation.json), and
[EXP-004](../experiment_log.md#exp-004--phase-4-statistical-baseline).

## Limits and Phase 5 handoff

The cost allowance is assumed, not a broker quote. Fills use Yahoo's Open,
which may differ from the official opening auction price; Phase 1 found
Yahoo's opens within 0.15% of IBKR's on 97-99% of historical days per stock.
The backtest allows
fractional shares, full fills, and short availability. It omits dividends,
borrowing fees, financing, cash interest, and broker margin rules. There is
no stop-loss or time stop. The fixed 2025 scale and unstable historical hedge
ratios can leave a trade open through a long drift. The seven-month interval
and small trade counts do not establish behaviour across market conditions.

Phase 5 can reuse the fixed final normalization, baseline ledgers, execution
engine, and metric definitions. Historical model validation still needs the
earlier regression and preprocessing fits. The comparison must align trading
eligibility, capital, costs, and endpoint handling. Its forecast and trading
choices must be selected from historical data without tuning against these
unseen results.
