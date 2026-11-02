# Sentiment study: findings and limits

I retained 5,715 Google News headlines about the six companies from January
to July 2026 and scored them with the unchanged FinBERT checkpoint. The
external benchmark results are mixed: FinBERT has higher macro-F1 than VADER
on both collections, but its FinEntity accuracy is below a constant neutral
reference. Almost all collected news has date-only timestamps. The results
therefore describe this retrieved sample, without a claim about trading-time
availability or measured accuracy on the news itself.

These are the `sentiment_v2` results. A review of the first run
(`sentiment_v1`) found that cleaning ignored the saved responses of windows
that had been split, and that two benchmark rules were applied more broadly
than intended. The [corrections](#corrections-after-review) section explains
both; the v1 outputs are kept unchanged.

The methods are in [methodology](../methodology.md#sentiment), the ordered
work is in [the plan](sentiment_plan.md), and acquisition details are in
[data sources](../data_sources.md#sentiment-model-overlap-screen-and-saved-pilot).
EXP-008 to EXP-010 in [the experiment log](../experiment_log.md) record the
first benchmark evaluation, the unscored pilot, and the first full run.
EXP-011 records the corrected run and its local and Docker verification.

## External evaluation

I kept records with one annotation, excluded inconsistent spans and duplicate
texts, and screened against Financial PhraseBank. This left 376 FiQA headlines
and 378 FinEntity paragraphs. No retained record equals a PhraseBank sentence
or contains one of at least five words. The complete counts are in
[benchmark preparation](../../outputs/metrics/sentiment/sentiment_v2/benchmark_preparation.json).
PhraseBank was used only for the screen, because it is part of FinBERT's
documented fine-tuning data.

| Collection | Classifier | Accuracy | Macro-F1 |
| --- | --- | ---: | ---: |
| FiQA | FinBERT | 0.672872 | 0.681713 |
| FiQA | VADER | 0.545213 | 0.544374 |
| FiQA | Majority reference | 0.438830 | 0.203327 |
| FinEntity | FinBERT | 0.425926 | 0.438488 |
| FinEntity | VADER | 0.322751 | 0.322178 |
| FinEntity | Majority reference | 0.664021 | 0.266031 |

The 95% row-bootstrap interval for FinBERT macro-F1 is 0.6312-0.7227 on FiQA
and 0.3894-0.4856 on FinEntity. These intervals describe uncertainty within
the retained collections. They do not establish performance on the 2026 news.
The complete reports include per-class metrics and confusion matrices:
[FiQA](../../outputs/metrics/sentiment/sentiment_v2/fiqa_metrics.json) and
[FinEntity](../../outputs/metrics/sentiment/sentiment_v2/finentity_metrics.json).

FiQA classes are derived from its numeric scores using the fixed -0.3 and
0.3 boundaries. Its separate numeric diagnostics are MAE 0.345489, RMSE
0.429248, and Spearman correlation 0.762754. FinBERT's probability difference
is not calibrated to FiQA's regression targets. The labeled source is a
challenge-participant mirror; the organizer's original download was
unavailable. The separate test inputs have no gold scores and were not scored.

FinEntity retains its native labels. Its class balance is 66 negative,
251 neutral, and 61 positive paragraphs. FinBERT recognized 46 of the 251
neutral examples as neutral. Its higher macro-F1 does not compensate for
the lower overall accuracy when describing this limitation.

There were 123 FiQA disagreements and 217 FinEntity disagreements. Existing
records illustrate the target-definition problem: `fiqa_8` labels the named
customer, while the headline also describes its supplier losing business;
`finentity_14` labels the bank reporting a market observation, while the
paragraph's overall tone is positive. `finentity_0` combines results above
expectations with a cut in the outlook. I kept the source labels and the
model unchanged. Disagreement tables identify records by ID without copying
their text into the public outputs.

No retained benchmark record was truncated. The overlap check addresses the
documented fine-tuning corpus; it cannot prove that no text appeared in any
earlier pretraining data. A single annotation also does not guarantee that
the text mentions only one entity. The whole-text model does not solve the
full target-specific sentiment task.

## Retrieved news coverage

The unscored 42-company-week pilot passed the adopted rule for every company.
The queries and cleaning rules stayed unchanged before full collection.
The full snapshot is `20261102T195614519732Z`: 326 requests for 186 initial
Saturday-Friday windows. Seventy requests returned 100 items and were split.
The final 251 narrower requests succeeded and five single-day requests
remained capped; none failed. Every saved response hash was checked.

Google's results do not add up across windows. In 42 of the 70 split
windows, the final narrower requests together returned fewer than the 100
items of the window they replaced. Cleaning therefore reads every saved
response and keeps an item returned by several requests once. Of the
retained headlines, 1,908 are copies taken from split-window responses,
869 of them for NVIDIA. Counts depend on how the windows were split, so they
measure retrieved coverage, not how much news was published.

| Company | Retained headlines | Eligible comparison weeks | Weekly score/return Spearman |
| --- | ---: | ---: | ---: |
| Apple | 967 | 30 | 0.349944 |
| Amazon | 964 | 30 | 0.280534 |
| Alphabet | 697 | 27 | 0.034799 |
| Meta | 887 | 27 | 0.498779 |
| Microsoft | 734 | 30 | 0.232036 |
| NVIDIA | 1,466 | 27 | 0.087302 |

Cleaning logged 9,267 excluded items: 4,384 outside the intended request
window, 2,846 duplicate GUIDs, 1,111 without the queried company in the
title, 627 naming several of the six companies, and 299 duplicate titles.
These are request-item counts, not a count of unique excluded articles. Most
duplicate GUIDs are copies returned by both a split window and one of its
parts, and the expanded query boundaries account for many out-of-window
copies. The source responses remain unchanged.

Of the retained items, 5,704 have the Pacific-midnight date-only pattern and
11 have other reported times. Date-only items remain dated summaries.
Timed items use the recorded trading-session convention; it does not prove
when the story was available historically. Capped source dates also flag the
next session because missing after-close items could belong there.

The daily table has 1,272 company-date rows; the weekly table has 186 rows.
Counts accompany scores. A successfully queried empty day has zero retained
headlines and a missing mean, while failed coverage would remain missing.
A zero means nothing was retrieved, not that nothing was published. Meta's
request for 14-20 February returned an empty feed, and its weeks ending
26 June and 3 July also have no retained headline. Capped counts are lower
bounds. Publisher, monthly, and exclusion counts are saved beside
[the run record](../../outputs/metrics/sentiment/sentiment_v2/run_metadata.json).

The queries require a company name or ticker together with stock, shares,
or earnings. Cleaning also requires a company name in the title. This narrows
coverage to financial reporting and leaves out product or subsidiary stories
that do not name the parent. Equal normalized titles are deduplicated across
the study, which can also remove recurring titles. RSS results depend on the
query window and retrieval time; this is a saved sample of indexed coverage,
not a complete archive or a measure of all public sentiment.

## Descriptive comparisons

The table above comes from
[weekly return associations](../../outputs/metrics/sentiment/sentiment_v2/weekly_return_associations.csv).
Weekly scores average all of a week's headlines, and saved daily percentage
returns are compounded. The initial partial week, weeks without retained
headlines, and failed or capped weeks are excluded. There are no significance
or predictive claims from these correlations. Headlines often report the
week's price move, so a positive same-week association is expected even if
the news predicts nothing. Weekly aggregation reduces the importance of
intraday ambiguity, but it does not remove collection bias or establish
causation.

The capped-week rule removes some of the busiest news weeks, and they are
not quiet market weeks. Alphabet's three excluded weeks include its largest
absolute weekly return of the period, 11.99% in the week ending 1 May, and
its sixth largest. NVIDIA's include its second largest, 8.44% in the week
ending 8 May; its week ending 22 May is excluded only because the cap on
Friday 15 May carries to the next session. The near-zero Alphabet and NVIDIA
correlations leave these weeks out. At the other end, between five and seven
of each company's eligible weeks have fewer than five headlines, so their
mean scores rest on very few items. These facts come from the
[weekly comparison table](../../outputs/metrics/sentiment/sentiment_v2/weekly_market_comparison.csv).

The two pair figures place the dependent-minus-independent weekly news
score beside the saved Phase 4 Z-score. No hedge ratio or normalization was
refitted. They show descriptive co-movement for the exploratory pairs:
[AMZN on META](../../outputs/figures/sentiment/sentiment_v2/AMZN_META_news_and_zscore.png)
and [AMZN on NVDA](../../outputs/figures/sentiment/sentiment_v2/NVDA_AMZN_news_and_zscore.png).

The [signal context table](../../outputs/metrics/sentiment/sentiment_v2/entry_signal_context.csv)
contains two stock rows for each of the five eligible Phase 4 entries.
The 7 January event has only three prior sessions inside the study window,
so its five-session coverage is incomplete and the lookback means are missing.
The other four events have complete five-session windows, with between one
and 93 retained headlines per stock. Date-only items are not assigned to a
session, so weekend and holiday headlines between those five sessions are
not counted. Signal-day counts are reported separately. Five events cannot
support an inference that sentiment explains the signals or improves the
strategy. Sentiment was not added to the LSTM or trading rules.

## Corrections after review

The first full run read only the final narrower requests whenever a window
had been split. Because the split windows' own responses held items those
requests never returned, it kept 3,846 headlines instead of 5,715. The loss
came from the 70 windows that had reached the 100-item limit; NVIDIA's
retained count rises from 609 to 1,466. The corrected cleaning reads the
narrower requests first, so their copy is kept when both returned an item.
The pilot recount retains 1,287 items instead of 1,016. Every company has
the same number of usable weeks as before, so the pilot decision stands.

Two benchmark rules were also brought into line with their purpose. FiQA
lists one headline twice, under two IDs with different targets. The first
run kept one copy as a single-annotation record; both copies are now
excluded as multi-annotation text. The PhraseBank screen had excluded three
FinEntity paragraphs because each contained a PhraseBank entry of one to
three words, a greeting or a sentence fragment rather than evidence of
overlap. Containment now needs an entry of at least five words, while an
exact match of any length still counts. FiQA retains 376 records instead of
377, and FinEntity 378 instead of 375.

None of these changes was chosen from scores, and the model, thresholds,
queries, and comparison rules are unchanged. The v1 outputs remain in the
`sentiment_v1` folders; the corrected outputs use `sentiment_v2`.

## Verification

The 18 sentiment tests cover the plan's label, threshold, overlap, timestamp,
title, split, resume, and empty-day examples, plus split-window items, short
PhraseBank entries, and repeated benchmark text. All 103 tests in the suite
passed locally. Phases 1-5 were not rerun.

A script run from the saved snapshots was kept as the reference. The notebook
ran all eight code cells without errors and matched it exactly in every table,
metric file, and figure. The offline Docker run reproduced labels, counts,
exclusions, and classification metrics exactly; the largest probability
difference is `1.9e-6` and the largest score-derived difference `3.8e-6`,
within `1e-5`. The Phase 4 and Phase 5 contract files and the frozen code
folders are unchanged. The notebook output no longer contains local paths.

Evidence: [Docker reproduction](../../outputs/metrics/sentiment/sentiment_v2/docker_reproduction.json)
and [verification](../../outputs/metrics/sentiment/sentiment_v2/verification.json).
