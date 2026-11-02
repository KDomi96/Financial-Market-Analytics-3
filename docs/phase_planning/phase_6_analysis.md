# Phase 6: what the application shows and how I checked it

The application tests one pair on supplied closing prices, and for a pair that
passes it shows the spread, Z-scores, and Phase 4 signals after a chosen fit
end. A second route serves the saved Phase 5 LSTMs. I checked it in two ways.
First, it must reproduce Phases 3-5 exactly on the project's own prices.
Second, all 15 project pairs are run through it with the same fit end as
Phase 4, to see what a user would be told about each. The design is in
[methodology](../methodology.md#api-and-web-application) and the order of work
in [the plan](phase_6_plan.md). Commands are in
[deployment](../deployment.md).

All numbers below come from
`outputs/metrics/phase6_review_validation.json` and
`outputs/metrics/api/project_pair_verdicts.csv`, both produced on 2 November
2026.

## Reproducing Phases 3-5

With the project's prices and a 2025-12-31 fit end, the service fits on the
same 2,011 sessions as Phase 3 and normalizes on the same 250 sessions of 2025
as Phase 4. For AMZN_META and NVDA_AMZN:

- The kept regression direction is Phase 3's (AMZN on META, AMZN on NVDA), and
  the intercept and beta are identical to the saved Phase 3 artifacts.
- The 2025 mean and standard deviation are identical to the Phase 4
  artifacts.
- The 145 unseen Z-scores per pair differ from Phase 4's saved values by at
  most 8.9e-16, which is floating-point rounding. Every date's crossings,
  eligible entries, exits, positions, and actions are the same as in Phase 4's
  `signals.csv`.
- Forecasts from all 141 saved unseen origins per pair match the `phase5_v2`
  predictions to within 8.9e-16, and both bundles reproduce their saved
  example forecasts exactly at startup.

These hold because the service calls the Phase 3-5 functions rather than
reimplementing them. The only new calculation is the normalization window,
which Phase 4 fixed to 2025 and the service measures back from the fit end.
The 72 files that the Phase 4 and Phase 5 evaluation contracts hash still
match their recorded hashes. The one recorded hash that differs is Phase 5's
`uv.lock`, which the sentiment libraries and this phase's five libraries
changed. Adding the Phase 6 libraries changed no version already in the lock.

## What a user is told about each project pair

Run one pair at a time with a 2025-12-31 fit end, only AMZN_META passes:

| Pair | Phase 3 rank | Direction-adjusted EG p | Johansen rank (95%) | Verdict |
| --- | ---: | ---: | ---: | --- |
| AMZN_META | 1 | 0.0284 | 1 | cointegrated |
| NVDA_AMZN | 2 | 0.2421 | 0 | not cointegrated |
| GOOGL_AMZN | 3 | 0.3731 | 0 | not cointegrated |
| MSFT_AAPL | 4 | 0.3953 | 0 | not cointegrated |
| MSFT_NVDA | 5 | 0.5360 | 0 | not cointegrated |
| Other ten pairs | 6-15 | 0.6285 to 1 | 0 | not cointegrated |

For every pair the test statistics and Johansen rank equal the Phase 3 values,
which is expected because the fitting sessions and settings are the same.

AMZN_META passing here does not contradict Phase 3. Phase 3 tested all 15
pairs together and applied Holm's correction across them, which raised
AMZN_META's p-value to 0.426 and left it labelled exploratory. A single-pair
test has no such correction because the user names the pair before testing
it. But anyone who picks AMZN_META because it topped the Phase 3 ranking has
already searched, so 0.0284 overstates the evidence. The page prints this
next to the result for each of the 15 project pairs, together with the Phase 3
rank and label.

## Signals after the fit end

For AMZN_META the page shows two short entries (2026-01-07 and 2026-04-10)
and one exit (2026-02-06) over the 145 unseen sessions. The second short is
still open at 2026-07-31, so the crossings on 2026-07-13 and 2026-07-30 are
ignored. There are no long crossings. These are Phase 4's signals. The page
shows no profit and loss; Phase 4 reports the backtest.

NVDA_AMZN fails, so by default the page shows its test results only. With the
exploratory option it shows one long entry, two short entries, and two exits,
under a warning that the pair failed the test and that these values are not
evidence of mean reversion.

## Forecasts

The forecast panel appears only for the two pairs with saved models, and each
forecast uses the model's own 2018-2025 regression and 2025 normalization,
not the user's fit. From the close of 2026-03-16, the AMZN_META model starts
at Z = 0.1853 and predicts a day-five change of -0.0275. The panel repeats the
Phase 5 finding that a persistence forecast was more accurate than both LSTMs
on the unseen period, so the path is illustrative. A forecast needs at least
39 consecutive sessions and an origin no later than 2026-07-31, the last
session in the project calendar.

## Checks on the service and the page

The test suite (136 tests, all passing locally and in Docker) covers the cases
in the plan. Malformed files are rejected with the line of the first problem.
Too little history before or after the fit end is rejected. Synthetic
cointegrated and independent series give the expected verdicts. Changing
prices after the fit end leaves the tests, regression, and normalization
unchanged. A missing bundle leaves the statistical routes working and returns
503 for that pair's forecasts. A changed `model.pt` fails the startup check.

The interface was checked by driving the real page against a running API.
Streamlit's test harness compares the p-value and signal counts on the page
with the API's response for a passing pair, a failing pair, the exploratory
view, and a forecast. A headless browser was used for the upload path, which
that harness cannot drive: an uploaded GOOGL_AMZN file showed p = 0.3731 and
Johansen rank 0, the same values the API returned for that file. The
screenshots are in `outputs/figures/app/`.

## Limits

- The verdict is one test on one pair at one fit end. Trying several fit ends
  or pairs and reporting the one that passes is a search, and the page cannot
  correct for it.
- Uploaded prices are taken as given. The service checks the format and that
  prices are positive, not whether they are adjusted consistently or come from
  the same market.
- Forecasts are limited to two pairs and to origins on the project calendar.
- No hosted deployment exists. The application runs locally and through
  Docker Compose with the saved files mounted read-only.
