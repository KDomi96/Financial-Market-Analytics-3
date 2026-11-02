# Sentiment plan: news sentiment for the six stocks

Status: implemented and verified, 2 November 2026. Steps 1-16 are complete.
Step 16 corrected the cleaning of split request windows and two benchmark
rules after a review; the reported run is `sentiment_v2`, and the first run's
`sentiment_v1` outputs are kept unchanged. The eight-cell notebook, the full
test suite locally and in Docker, and saved-input reruns passed. See
[findings](sentiment_analysis.md) and the
[verification record](../../outputs/metrics/sentiment/sentiment_v2/verification.json).
The pinned model, benchmark downloads, unscored pilot, and full news snapshot
are saved; see
[data sources](../data_sources.md#sentiment-benchmark-snapshots). All rules
below were adopted on 2 November 2026 (step 2). Decisions and their reasons are in
[methodology](../methodology.md#sentiment).

The study scores Google News headlines about the six companies with FinBERT
and describes how sentiment and coverage changed from January to July 2026.
It is separate from the six numbered phases and runs before Phase 6. The work
has two halves that meet only at scoring: checking the unchanged model on two
labelled benchmarks, and collecting and cleaning the headlines. Sentiment is
not an input to the Phase 5 LSTM or to the trading rules, and nothing from
Phases 1-5 is refitted or rerun. A weak benchmark result or thin news coverage
is reported as found.

## Inputs

| Input | Used for |
| --- | --- |
| `data/raw/sentiment/benchmarks/20261102T173344495719Z/` | FiQA headline files and FinEntity, saved unchanged with hashes |
| Financial PhraseBank v1.0 from `takala/financial_phrasebank`, downloaded in step 5 | Overlap screen only; never scored |
| `ProsusAI/finbert`, downloaded in step 5 | The sentiment model, used without fine-tuning |
| Google News RSS search, collected in steps 8 and 10 | Headlines from 1 January to 31 July 2026 |
| `data/processed/master_unseen.csv` | Daily returns for the weekly comparison |
| `data/processed/statistical_baseline/unseen_zscores.csv`, `outputs/backtests/statistical_baseline/phase4_v1/unseen/signals.csv` | Phase 4 Z-scores and the five eligible entry signals |

Repository details looked up on 2 November 2026, before any download:

- FinBERT's head revision was `0bc2ac10dda6929bcb1f77ccc43c7ec5c424f031`. Its
  licence terms (CC BY-NC-SA 4.0, copyright MIH AI B.V.) and a
  `model.safetensors` file were added on 12 October 2026. At that revision the
  configuration maps label 0 to positive, 1 to negative, and 2 to neutral,
  with a 512-token limit. The repository also holds `.bin`, TensorFlow, and
  Flax copies of the weights, about 438 MB each; only the safetensors file is
  needed.
- Financial PhraseBank's head revision was
  `8d3fe0c36d5feec6b3cc5e455b0fcb4820fb9964`: a 682 KB zip under
  CC BY-NC-SA 3.0. The repository's loader is a dataset script, so the zip is
  read directly instead of through the `datasets` library.

The revisions and file hashes actually used are recorded when the files are
saved.

## Decisions

| Decision | Rule | Status |
| --- | --- | --- |
| Role | Descriptive study; not an LSTM input or trading rule | Adopted |
| Source | Google News RSS headlines, scored locally | Adopted |
| Model | `ProsusAI/finbert` at a pinned revision, without fine-tuning | Adopted |
| Benchmarks | FiQA headlines and FinEntity paragraphs with one annotation, reported separately against VADER and a majority-class reference | Adopted |
| Overlap screen | Drop benchmark records equal to a Financial PhraseBank sentence (50%-agreement file) or containing one of at least five words | Adopted; length limit added in step 16 |
| Thresholds | FiQA below -0.3 negative, above 0.3 positive; VADER compound at least 0.05 positive, at most -0.05 negative | Adopted |
| Query | One query per company, read directly from RSS: its names and tickers, then `(stock OR shares OR earnings)` | Adopted |
| Relevance | A headline counts for a company only if its title names that company | Adopted |
| Several companies | Titles naming two or more of the six are left out of the company series and counted | Adopted |
| Pilot | First full week of each month for each company, with the pass rule below | Adopted |
| Timestamps | Midnight in Los Angeles marks a date-only item; date-only items are summarized by date | Adopted |
| Description | Daily table saved; comparisons by Saturday-Friday week; three listed comparisons | Adopted |
| Storage | Text and model files stay local; IDs, counts, scores, and metrics are committed | Adopted |

The finance terms in each query and leaving out headlines that name several
of the six companies were choices rather than technical necessities; I kept
both. Step 9 may still change the queries, names, or cleaning rules, on pilot
counts and relevance only, with the reason recorded in methodology.

## Design

### Queries

Each request uses `hl=en-US`, `gl=US`, and `ceid=US:en`. Names count in a
title as whole words, ignoring case.

| Ticker | Query (`q`, before the date terms) | Names that count in a title |
| --- | --- | --- |
| MSFT | `(Microsoft OR MSFT) (stock OR shares OR earnings)` | Microsoft, MSFT |
| GOOGL | `(Alphabet OR Google OR GOOGL OR GOOG) (stock OR shares OR earnings)` | Alphabet, Google, GOOGL, GOOG |
| NVDA | `(Nvidia OR NVDA) (stock OR shares OR earnings)` | Nvidia, NVDA |
| AAPL | `(Apple OR AAPL) (stock OR shares OR earnings)` | Apple, AAPL |
| AMZN | `(Amazon OR AMZN) (stock OR shares OR earnings)` | Amazon, AMZN |
| META | `Meta (stock OR shares OR earnings)` | Meta |

Google is a subsidiary, but it is how most headlines name Alphabet. Product
and other subsidiary names (AWS, Instagram, iPhone) are not used, so every
company is matched the same way. The finance terms limit results to coverage
of each company as a business and a stock; none of them favours good or bad
news. The pilot checks that the grouped `OR` terms behave as expected.

### Windows and requests

Each window is queried one day wider on each side (`after:` the day before,
`before:` the day after), and items are kept by their reported date, because
the preliminary requests returned items dated on the `before:` day. A window
that returns 100 items is split in two until it returns fewer or covers one
day; a one-day window still at 100 is flagged as capped. The split window's
own response is still read during cleaning: Google's results for a window and
for its parts do not add up, so the narrower requests can miss items the
wider one returned (step 16).

Requests run one at a time with at least 3 seconds between them. A timeout or
an HTTP 429 or 5xx response is retried after 30, 60, and 120 seconds and then
recorded as failed; a later run collects only the failed windows. Every
response is saved unchanged with the request URL, query, window, collection
time, status, size, SHA-256 hash, and attempt number.

The pilot covers the first full Monday-Friday week of each month (5-9 January,
2-6 February, 2-6 March, 6-10 April, 4-8 May, 1-5 June, and 6-10 July) for each
company: 42 company-weeks. A sampled week is usable when at least five
headlines remain after the relevance, several-company, and duplicate rules,
about one per trading day. The full collection goes ahead if at least four
companies have at least four usable weeks out of seven. A company below that
is still collected, but its results are reported as sparse coverage, without
trend comparisons. If fewer than four companies pass, I revise the procedure in
methodology before collecting. Pilot headlines are not scored.

The full collection uses Saturday-Friday windows from 1 January to 31 July 2026;
the first window covers only 1-2 January.

### Cleaning

Applied in this order, with every exclusion logged with its reason:

1. Parse each item's title, link, GUID, reported time, and source name and URL.
   Items with the same GUID from overlapping windows are kept once. Narrower
   requests are read before the split windows they replaced, so their copy
   is the one kept.
2. Keep items whose reported date lies inside the requested window.
3. If the title ends with ` - ` followed by the item's source name, remove that
   suffix. Otherwise leave the title unchanged and flag it.
4. Keep the headline for the queried company only if the title names it.
5. Leave out titles that also name any of the other five companies.
6. Within a company, treat titles as duplicates when they are equal after
   Unicode NFKC normalization, lower case, and single spacing. Keep the
   earliest reported time, breaking ties by collection time.

The rules are fixed before any headline is scored. A later change needs a
recorded reason and may not be based on scores.

### Timestamps

The reported time is the RSS `pubDate`, in UTC. An item is date-only when that
time is exactly midnight in `America/Los_Angeles`. Both preliminary historical
requests fit this pattern: 08:00 UTC in January and 07:00 UTC in July. A rule
based on one UTC hour would misread items after the daylight-saving change on
8 March 2026. Date-only items are dated by their Los Angeles date and are not
assigned to a trading session.

If the pilot shows a useful number of items with real times, those items are
converted to US Eastern time, and items after the close, at weekends, or on
holidays move to the next session in the masters' calendar. Early closes come
from a list in the settings, with the NYSE holiday calendar as the source.
Neither the reported time nor the collection time shows when a story was
available historically.

### Scoring

FinBERT loads from local files only, with the label order read from its saved
configuration and a fixed batch size from the settings. Each text gets the
three class probabilities, the label with the highest probability, and the
score `P(positive) - P(negative)`. Truncation at 512 tokens is counted; none is
expected for headlines. VADER is used only on the benchmarks.

### Benchmark evaluation

FinBERT and VADER are scored on the same prepared rows, and each benchmark is
reported separately: class counts, accuracy, macro-F1, per-class precision,
recall, and F1, confusion matrices, and the majority-class reference. Seeded
bootstrap 95% intervals are added for accuracy and macro-F1, because each
benchmark keeps only a few hundred records. FiQA also gets the MAE, RMSE, and
Spearman correlation between FinBERT's score and the original FiQA scores,
since the two are not on the same scale. Disagreements are saved as record IDs
with gold and predicted labels. The model stays fixed whatever the results
show.

### Description

The daily table holds, for each company and calendar date, the kept headline
count, the mean score (missing when the count is zero), the share of date-only
items, and flags for failed or capped windows. A queried day with no kept
headline has a count of zero; a failed window is never shown as zero.

Comparisons with market data use Saturday-Friday weeks, so weekend headlines
join the trading week after them. A date-only day runs past the 16:00 close,
and a weekly unit makes that uncertainty matter less. Three comparisons are
fixed before scoring:

1. For each company, the Spearman correlation between weekly mean score and the
   week's compounded return from `master_unseen.csv`, with the number of
   weeks. This is described as an association.
2. For each shortlisted pair, a figure of the weekly score difference
   (dependent minus independent stock) beside the Phase 4 unseen Z-scores.
3. A table for the five eligible Phase 4 entry signals (AMZN on META: two
   short; AMZN on NVDA: one long and two short). For each stock in the pair it
   gives the headline count and mean score over the five sessions ending the
   session before the signal, plus the count on the signal day. Five events are
   too few for statistics.

Any other comparison is recorded in methodology before it is computed, or
labelled exploratory.

### Storage

| Kept local and out of Git | Committed |
| --- | --- |
| `data/raw/sentiment/` (already ignored) | `configs/sentiment.json`, code, and tests |
| `data/interim/sentiment/`: prepared benchmark rows and the cleaned, excluded, and scored headlines | `data/processed/sentiment/sentiment_v2/`: daily and weekly tables without text |
| `artifacts/sentiment/sentiment_v1/finbert/`: model files (438 MB, over GitHub's 100 MB file limit) | `artifacts/sentiment/sentiment_v1/model_revision.json` |
| | `outputs/metrics/sentiment/sentiment_v2/`, `outputs/figures/sentiment/sentiment_v2/`, and the executed notebook, with records identified by ID |

The model folder keeps its `sentiment_v1` name in both runs: FinBERT is not
fitted, and the corrected run uses the same pinned files.

The notebook does not print tables of headline or benchmark text. Docker
excludes the model folder from the build and mounts it read-only, with
`HF_HUB_OFFLINE=1`. The sentiment runner is a separate command, not part of
`scripts/run_pipeline.py`: a fresh clone has the Yahoo and Cboe snapshots that
Phases 1-5 need, but not the local sentiment inputs.

## Steps

### A. Rules before code

**1. Record the plan.** Done on 2 November 2026: this file, the methodology
entries, and the checklist links.

**2. Confirm the rules.** Done on 2 November 2026: all proposed rules were
adopted as written, including the finance terms and leaving out headlines that
name several companies.

**3. Ignore rules.** Done on 2 November 2026. `.gitignore` now covers
`data/interim/sentiment/` and `artifacts/sentiment/*/finbert/`, and
`.dockerignore` excludes the model folder. `git check-ignore` confirmed that
headline tables and model weights are ignored, while the daily tables, metrics,
`model_revision.json`, and the existing interim files are not.

### B. Model side

**4. Add the libraries.** Done on 2 November 2026 with
`uv add transformers vaderSentiment scikit-learn`. A repeated trial on a copy
of the lock and the real change agreed: all 91 locked packages kept their
versions, none was removed, and 26 were added, including transformers 5.22.1,
tokenizers 0.23.3, safetensors 0.8.0, huggingface-hub 2.4.0, vaderSentiment
3.3.2, and scikit-learn 1.9.1. numpy 2.5.4, pandas 3.0.6, matplotlib 3.11.2,
statsmodels 0.15.0, and torch 2.15.0+cpu are unchanged. All 77 tests pass,
transformers detects the CPU torch build, and VADER loads its lexicon. The
earlier lock remains in Git at the Phase 5 commit.

Phase 3's freeze check and Phase 4's saved normalization compare library
versions, so they stay valid while no version changes. Phase 5's contract
hashes the whole lock, and the master manifest records its hash, so after this
step `scripts/run_pipeline.py` refuses to rerun Phase 5 against the evaluated
outputs. That refusal is intended, as in the Phase 6 plan. Do not rerun Phases
1-5 locally.

**5. Download the model and the screen file.** Add Financial PhraseBank to
`configs/sentiment_benchmarks.json` at a pinned revision and take a new
benchmark snapshot. FiQA and FinEntity are pinned to commits, so their hashes
should match the first snapshot; the FiQA organizer page is live and may
differ. Download FinBERT's `config.json`, `model.safetensors`,
`tokenizer_config.json`, `special_tokens_map.json`, `vocab.txt`, and
`README.md` at a pinned revision into `artifacts/sentiment/sentiment_v1/finbert/`,
and write `model_revision.json` with the revision, file hashes, licence, and
download time. Record both in data sources.

Completed on 2 November 2026. The new benchmark snapshot is
`20261102T194353691191Z`; all nine source hashes and all six model-file hashes
were checked. The model weights also match the repository's LFS SHA-256.

**6. Prepare the benchmarks.** Working in `notebooks/06_sentiment.ipynb` from
saved files, keep single-annotation records; drop duplicate texts, FinEntity
span mismatches, and the unlabelled FiQA test file; run the PhraseBank screen;
and derive the FiQA classes. Save the prepared rows locally with counts by
exclusion reason.

Preparation retains 377 FiQA headlines and 375 FinEntity paragraphs. The saved
preparation report accounts for every exclusion, including three FinEntity
PhraseBank matches. The explanatory notebook ran top to bottom in step 14.
Step 16 changes the counts to 376 and 378: a FiQA headline repeated under a
second ID for another target is excluded, and the three PhraseBank matches,
each on an entry of one to three words, are kept.

**7. Evaluate the benchmarks.** As described above. This finishes the model
side before any news is collected, so environment or label-order problems
show up early.

Completed before the pilot. Separate metrics, bootstrap intervals, confusion
matrices, and disagreements by ID are saved under
`outputs/metrics/sentiment/sentiment_v1/`.

### C. News side

**8. Pilot.** Write the collector and run the 42 company-week pilot. Report
counts before and after cleaning, publishers, the title format, the date-only
share by month, capped windows, and failed requests, and apply the pass rule.

Completed with snapshot `20261102T195054616236Z`: 1,016 retained headlines,
1,015 date-only items, and one capped leaf window. All six companies pass;
see `pilot_report.json` and the accompanying coverage tables. The step 16
recount retains 1,287 headlines with the same usable weeks for every company.

**9. Settle the rules.** Using pilot counts and relevance only, confirm or
change the queries, names, and cleaning rules, and record any change with its
reason in methodology. Nothing is scored at this point.

Completed: the adopted queries and cleaning rules stay unchanged. The pilot
decision and aggregation details are recorded in methodology before news
scoring.

**10. Collect.** Run the full collection for the six companies, splitting
capped windows and resuming failed ones.

Completed with snapshot `20261102T195614519732Z`: 326 requests, of which 70
were split, 251 succeeded, and five remained capped at one day. None failed.

**11. Clean.** Apply the cleaning rules and save the cleaned and excluded tables
locally, with counts by company, month, and reason.

Completed; step 16 corrected which saved responses are read.

### D. Scoring and results

**12. Score.** Run FinBERT on the kept headlines.

Completed; no headline exceeded the token limit.

**13. Describe.** Build the daily and weekly tables, the figures, and the three
comparisons.

Completed: daily and weekly tables, the three comparisons, and five figures.

**14. Promote and verify.** Move stable notebook logic into the sentiment
package and `scripts/run_sentiment.py`, add the tests below, run the notebook
top to bottom, and rerun offline from the saved snapshots and model files in
the venv and in Docker. Compare the reruns under the tolerance in Checks.

**15. Record the findings.** Write `sentiment_analysis.md`, append the run to
the experiment log, and update data sources, the data dictionary, the local
checklist, and the README commands. Phase 6 step 1 then decides whether the
interface shows the results.

**16. Review corrections.** Done on 2 November 2026, after a review of the
first full run. Cleaning had read only the final narrower requests of split
windows, although the split windows' own saved responses held items those
requests never returned. It now reads every saved response, which raises the
retained headlines from 3,846 to 5,715. In the benchmarks, a FiQA headline
repeated for a second target counts as multi-annotation, and PhraseBank
containment needs an entry of at least five words. The study was rerun from
the saved snapshots into new `sentiment_v2` folders, and the notebook, tests,
and local and Docker reproduction checks were repeated. Methodology and the
findings give the reasons; EXP-011 records the run.

## Files

| File | Responsibility |
| --- | --- |
| `pyproject.toml`, `uv.lock` | Three new libraries; no version already in the lock changed |
| `configs/sentiment_benchmarks.json` | Adds Financial PhraseBank at a pinned revision |
| `configs/sentiment.json` | Queries, names, windows, request limits, pilot rule, cleaning rules, thresholds, early closes, batch size, and paths |
| `src/market_analytics/sentiment/model.py` | FinBERT download at a pinned revision, local loading, scoring, and VADER |
| `src/market_analytics/sentiment/news.py` | RSS requests, windows, splitting, retries, and saved responses |
| `src/market_analytics/sentiment/headlines.py` | Parsing, timestamps, suffix removal, and the relevance, several-company, and duplicate rules |
| `src/market_analytics/sentiment/evaluation.py` | Benchmark preparation, overlap screen, and metrics |
| `src/market_analytics/sentiment/study.py` | Daily and weekly tables, comparisons, and the run record |
| `scripts/download_finbert.py`, `scripts/download_google_news.py`, `scripts/run_sentiment.py` | Thin entry points |
| `notebooks/06_sentiment.ipynb` | The study's explanation, from saved files |
| `data/raw/sentiment/google_news/<snapshot>/` | Pilot and full responses with their request records (local) |
| `data/interim/sentiment/sentiment_v2/` | Prepared benchmarks and cleaned, excluded, and scored headlines (local) |
| `data/processed/sentiment/sentiment_v2/` | Daily and weekly tables without text |
| `artifacts/sentiment/sentiment_v1/` | FinBERT files (local) and `model_revision.json`, shared by both runs |
| `outputs/metrics/sentiment/sentiment_v2/`, `outputs/figures/sentiment/sentiment_v2/` | Benchmark metrics, coverage and exclusion counts, comparisons, run record, and figures |

The `sentiment_v1` output folders hold the first full run, kept unchanged
after step 16.
| `tests/test_sentiment.py` | The checks below |
| `tests/verify_sentiment_reproduction.py` | Compare saved reruns and check earlier-phase file contracts |
| `docs/phase_planning/sentiment_analysis.md` | Findings and limitations |

The module split may change when notebook logic is promoted.

## Checks

Known-input tests for errors that would change results without failing:

- Labels and scores: under the saved configuration, logits whose largest value
  is at index 1 give `negative`. Probabilities of 0.7, 0.2, and 0.1 for
  positive, negative, and neutral give a score of 0.5. A configuration with a
  different label set is rejected.
- Thresholds: FiQA scores of -0.3 and 0.3 are neutral, -0.31 is negative, and
  0.31 is positive. VADER compounds of 0.05 and -0.05 are positive and
  negative; 0.0499 is neutral.
- Overlap screen: a paragraph containing a PhraseBank sentence is dropped; one
  that shares only a few words with it is kept. An entry shorter than five
  words drops a record only by an exact match (step 16).
- Repeated benchmark text: a headline listed under two IDs for different
  targets counts as multi-annotation; an exact repeat keeps one copy (step 16).
- Date-only times: 2026-01-05 08:00 UTC, 2026-07-06 07:00 UTC, and 2026-03-09
  07:00 UTC are date-only; 2026-03-09 08:00 UTC (01:00 in Los Angeles) is not.
- Sessions: a timed item at 2026-01-06 21:30 UTC (16:30 Eastern) moves to
  7 January, one at 14:00 UTC (09:00 Eastern) stays on 6 January, and one on
  Saturday 10 January moves to 12 January.
- Windows: an item dated the day after a window is dropped and one dated its
  last day is kept. A stubbed 100-item response for a seven-day window produces
  two smaller requests; a one-day window at 100 is flagged as capped. Items
  that only the split window returned are kept, and an item both returned is
  kept once from the narrower request (step 16).
- Failures: a window whose attempts all fail is marked failed and produces no
  zero-count days.
- Titles: `Nvidia shares rise - Reuters` with source Reuters becomes
  `Nvidia shares rise`. `Microsoft beats estimates` is kept for MSFT,
  `Pineapple prices climb` is not kept for AAPL, and `Nvidia and Microsoft
  extend deal` is left out as naming several companies. The same title from two
  publishers is kept once, at the earlier time.
- Empty days: a queried day with no kept headline has a count of zero and a
  missing score, never a neutral one.

The offline rerun must reproduce labels, counts, exclusions, and classification
metrics exactly. Probabilities and score-derived numeric diagnostics/tables
must agree within an absolute 1e-5. Exact floating-point equality between
Windows and Linux is not assumed. This distinction was clarified during
verification because FiQA MAE/RMSE inherit the small probability differences;
the observed differences and reason are recorded in methodology. The 1e-5
tolerance is unchanged.

Review checks added during implementation reject snapshots with the wrong
pilot/full role, acquisition settings, or expected windows, and settings with
changed thresholds. Failed/capped source dates also flag the next session,
without recursive propagation. Empty kept/excluded tables retain their schemas.
These checks prevent missing data or metadata from silently changing results.

Before reporting completion, confirm that the files hashed by the Phase 4 and
Phase 5 contracts match their recorded hashes and that Git shows no changes in
`trading/`, `features/`, `models/`, `cointegration/`, or `data/master.py`.
Check that `master_unseen.csv` is opened only for the weekly comparison, and
that no committed file holds headline or benchmark text.

Acquisition, the benchmark and full runners, the notebook, and local/Docker
checks have been exercised. The README records the verified commands.

```powershell
uv add transformers vaderSentiment scikit-learn
uv run --locked python scripts/download_sentiment_benchmarks.py
uv run --locked python scripts/download_finbert.py
uv run --locked python scripts/download_google_news.py --pilot
uv run --locked python scripts/download_google_news.py
uv run --locked python scripts/run_sentiment.py
uv run --locked python -m unittest discover -s tests -v
docker build -t financial-market-analytics-3:sentiment .
# The offline run needs read-only mounts for raw sentiment snapshots, the model,
# settings, master_unseen.csv, Phase 4 Z-scores, and Phase 4 signals. Its output
# folders are mounted separately for comparison; see the verified README command.
```

The initial one-mount Docker example was insufficient: `.dockerignore` also
excludes the processed market inputs and Phase 4 outputs, and raw sentiment
snapshots are now excluded from the build. Offline verification mounts those
saved inputs rather than rebuilding any earlier phase. The default image
command is not used for the sentiment check.

## Handoff

Phase 6 step 1 uses the saved results to decide whether the interface shows
sentiment. Packaging must decide whether the archive carries the sentiment
snapshots and model files or only download instructions. The news results can
be reproduced only from the saved Google News responses, because a later
search returns different items.
