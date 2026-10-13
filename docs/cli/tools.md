# Additional command-line tools

These commands collect evaluation data, fit candidate tone revisions, or run specialized evaluations. For the field metric tables, see [Benchmark](benchmark.md). Install the [benchmark dependencies](../installation.md#benchmarking) and prepare any extraction resources before running them.

## Collect new samples

1. **Write a sampling plan** and save it as `sample-plan.json`. Use separate dates for development and benchmarking:

   ```json
   {
     "seed": 1729,
     "utc_windows": ["001500", "084500", "163000"],
     "english_per_window": 90,
     "translated_per_window": 10,
     "per_source_per_day": 2,
     "development": {"days": ["20240110", "20240710"]},
     "benchmark": {"days": ["20250211", "20250811"]}
   }
   ```

2. **Collect development articles first**, then exclude their URLs when collecting the reserved benchmark:

   ```shell
   gdelt-regkg-benchmark-samples --resources-dir local-resources --plan sample-plan.json --split development --cohort english --output samples/development
   gdelt-regkg-benchmark-samples --resources-dir local-resources --plan sample-plan.json --split benchmark --cohort english --exclude-manifest samples/development/manifest.json --exclude-corpus samples/development/results.jsonl --output samples/benchmark
   ```

3. **Handle translated articles separately.** Use `--cohort translated` to collect source-language bodies, then translate them and save their analyzed English text before field benchmarking.

The example plan samples winter and summer dates at several UTC times. These windows describe *collection* times, not publication times; sampling only around midnight can underrepresent topics and regions. See the [collection arguments](#seasonal-sample-collection).

## Good practice

- Keep development, validation and benchmark data separate, and do not tune against the benchmark.
- Add any earlier corpora to the exclusion arguments, and check body hashes for duplicate articles published under different URLs.
- Publisher bodies retrieved today can differ from GDELT's original text and lower F1 even when extraction is correct on the retrieved body. Report retrieval failures, translation differences and input lengths alongside agreement.

Further reading: [Changelog](../../CHANGELOG.md) and [current metrics](../README.md#agreement-with-gdelt).

## Seasonal sample collection

The [fixed sample plan](../../scripts/benchmark-plan.json) selects eight days per split
from four seasonal months, six UTC windows per day, and 90 English plus 10
translated records per window. The source cap is two URLs per source/day.
Collection keeps failures without replacements and does not score the benchmark.
The reported run collected English first and Translingual records separately
with `--cohort english` / `--cohort translated`, sharing source caps through
`--exclude-manifest`. The commands below collect both cohorts together for a
new run; exact score replay requires the saved retained bodies and archives.
Pass older corpora with `--exclude-corpus` to remove known URLs.

```shell
gdelt-regkg-benchmark-samples --plan scripts/benchmark-plan.json --split development --output sample-development --resume
gdelt-regkg-benchmark-samples --plan scripts/benchmark-plan.json --split benchmark --output sample-benchmark --exclude-manifest sample-development/manifest.json --resume
```

Fit and select candidates only on development data, then freeze resource hashes
before examining benchmark results. These windows cover six of the day's 96
archive batches; seasonal and source caps do not make the sample representative
of all news. Article failures, topic mix, and time zones still affect coverage.

Replay a saved, deduplicated corpus with its original archives to keep exactly
the same bodies across models and dictionaries:

```powershell
$archives = (Get-ChildItem sample-benchmark/*.gkg.csv.zip).FullName
gdelt-regkg-benchmark-extraction --archives $archives --corpus retained-corpus.jsonl --output seasonal-lg --sample-size 100000 --per-source 100000 --ner-model en_core_web_lg --include-translated --translation-device cuda --translation-cache translations.sqlite --translation-batch-size 8 --translation-beams 1 --offline
```

The collector writes pending source-language bodies for translated records;
`--include-translated` prepares them before extraction. Already prepared bodies
are replayed verbatim. Use the same retained corpus for small and medium models,
and separate output directories for every comparison. Corpus deduplication is
a separate audit step; benchmark commands do not remove duplicate text silently.

## Refine a tone revision

```shell
gdelt-regkg-refine-tone --results ./benchmark-results/results.jsonl --train-dates 20260922 20260924 20260926 20260928 --validation-date 20261002 --test-date 20261003 --gi-source inqtabs.txt --output ./tone-revision --check-language
```

This development tool learns candidate dictionary changes from saved benchmark
article bodies and their original GDELT scores. It derives the tone v1 baseline
from `--gi-source`, fits additions/removals on training dates, chooses variants
using a separate validation date, and evaluates the frozen choices on a held-out
test date. It excludes duplicate bodies across splits and reserves a subset of
publishers for testing. It needs no previously built tone profiles.

The output contains `lexicon.json`, `training_edits.json`, `split_audit.jsonl`,
`report.json` and `test_comparison.csv`. The candidate does not become the default
automatically. Use `build` to reproduce existing recipes; use refinement to
experiment with a new revision and review its independent evaluation.

## Field benchmark

Reuse saved `results.jsonl` article bodies from the maintained collection/benchmark tools, with the original GKG archives containing those record IDs. This benchmark performs no retrieval or fitting.

Original records must match both the saved record ID and URL. Unrelated rows sharing an ID are ignored and counted; conflicting rows matching the same ID/URL pair are rejected.

```shell
gdelt-regkg-benchmark-fields --corpus benchmark-results/results.jsonl --archives original.gkg.csv.zip --output fields-report.json --ner-model en_core_web_lg
```

It compares document-level sets of geographic feature IDs, calendar dates, normalized broad names, numeric-value/object pairs and quotation content. Numeric values alone and quotation content with reporting verbs are separate diagnostics. Quotation matching normalizes Unicode, case, apostrophes and whitespace, retaining punctuation and requiring complete content equality. Offsets and repeated mentions are excluded. Malformed native fields are excluded only from their corresponding metrics.

Reports include precision, recall, F1, identity totals, positive-document counts and results by month, novel sources and similar body length. `--bootstrap-samples 1000` adds 95% document-bootstrap F1 intervals with seed 1729; these describe sampling uncertainty within the retrieved corpus and do not account for source clustering or input differences. To evaluate these fields without recomputing GCAM:

```shell
gdelt-regkg-benchmark-fields --corpus benchmark-results/retained-english.jsonl --archives original.gkg.csv.zip --output fields-report.json --ner-model en_core_web_lg --fields-only --bootstrap-samples 1000
```

GCAM reports count/density MAE, count bias, count correlation and native/local nonzero-document totals for supported categories. Weighted dimensions add mean-score MAE, bias, Pearson correlation and sign agreement. Unreported native weighted match counts are excluded from count errors; native zero-valued means remain valid. Missing original records and malformed fields are audited. `--include-translated` accepts saved translated English bodies; it does not translate source text. Use separate reports for English and translated corpora. `--sample-size` selects ordered record IDs for a smoke check and is not source-balanced; evaluate the full reserved corpus for final metrics.

For GCAM alone, avoid loading NER:

```shell
gdelt-regkg-benchmark-fields --corpus benchmark-results/results.jsonl --archives original.gkg.csv.zip --output gcam-report.json --gcam-only
```

Add `--gcam-lexicon gcam.json` to evaluate a frozen custom profile, including an optional licensed Lexicoder import. The report records its configuration checksum. No dictionaries are fitted by this command.

GCAM reports also separate codebook dimension coverage, observed native document/dimension coverage and positive-count occurrence coverage. Per-dictionary summaries include presence precision/recall/F1, total absolute count error divided by native counts (WAPE), density MAE and median correlation for categories appearing in at least twenty native articles. Matcher, tokenizer and theme-engine hashes accompany resource hashes. Counts and means without reported native companion counts retain the exclusions described above.

## Tone benchmark against original articles

Install the benchmark extra with `uv sync --extra benchmark` or `python -m pip install -e "./path/to/gdelt-regkg[benchmark]"`.

```shell
gdelt-regkg-benchmark-tone --batches 20260930120000 20260930121500 --output ./benchmark-results --sample-size 150
```

Alternatively pass `--archives original.gkg.csv.zip`. The benchmark retrieves GKG archives and article pages, extracts bodies with Trafilatura, and compares all seven tone components using the default dictionary. Saved bodies, scores, failures, original selections, and metrics support inspection. This HTML extraction belongs to the benchmark; the library requires prepared text.

Use `--offline` to replay cached pages and `--lexicon path/to/tone.json` to compare a candidate dictionary. Use a separate output directory to preserve earlier measurements. Live pages may differ from the text originally processed by GDELT. See [benchmark methods and results](../../CHANGELOG.md).

## NER, count, and theme benchmarks

Use the same benchmark extra as for tone. Compare all three fields on one
source-balanced sample, or run the individual entry points:

```shell
gdelt-regkg-benchmark-extraction --batches 20261003120000 20261003210000 --output extraction-results --sample-size 300 --ner-model en_core_web_md
gdelt-regkg-benchmark-ner --batches 20261003120000 --output ner-results --sample-size 300
gdelt-regkg-benchmark-counts --batches 20261003120000 --output count-results --sample-size 300
gdelt-regkg-benchmark-themes --batches 20261003120000 --output theme-results --sample-size 300
```

`--archives` accepts downloaded ZIPs instead of `--batches`. Archive downloads
use HTTP; article URLs retain their protocols. Untranslated web records are
sampled before retrieval, with `--seed`, `--per-source`, and optional `--per-day`.
Conflicting reference versions of the same URL are excluded. Lingua screens
bodies for English independently; `--no-language-check` explicitly disables
that screen. Translation is opt-in with `--include-translated`; it retrieves the separate
Translingual archives and translates complete bodies before English NLP.
Use `--translation-device cuda --translation-cache translations.sqlite
--translation-batch-size 8 --translation-beams 1` with already downloaded
M2M100 weights. Summaries separate English and translated cohorts and record
translation failures. No automatic model download runs. Install
`en_core_web_md` or `en_core_web_lg` separately using the model URLs in
[Installation and setup](../installation.md#english-models).

`--offline` reuses HTML in the output's `html/` directory. To reuse another tone
benchmark's HTML, add `--cache-dir path/to/tone-results`. Alternatively,
`--corpus path/to/results.jsonl` reads its saved bodies verbatim and retains
failed entries without fetching articles. Original archives are still required
for native count/theme/entity fields; selection is then drawn from the
archive/corpus URL intersection. This preserves the source corpus's selection
bias. For example, in PowerShell:

```powershell
$archives = (Get-ChildItem benchmark-results/*.gkg.csv.zip).FullName
gdelt-regkg-benchmark-extraction --archives $archives --corpus benchmark-results/results.jsonl --output extraction-replay --per-day 100 --ner-model en_core_web_md --offline
```

All tools save `manifest.json`, `results.jsonl` with bodies and comparisons,
`comparison.csv`, and `summary.json`. The summary includes micro precision,
recall and F1, document agreement, per-label count/theme metrics, per-date/source
breakdowns, failures, and the subset within 10% of GDELT's word count.
Configuration and selected references protect existing outputs from accidental
overwrites; use a new directory for a model/rule/implementation change.

Themes compare per-article sets against both the complete native vocabulary and
the enabled local labels. Counts primarily compare label-plus-quantity
multisets; deduplicated pairs, label sets, normalized objects, and full tuples
are separate measurements. NER compares per-article person/organization names,
both raw and normalized by NFKC, case folding, whitespace, and apostrophes;
there is no alias resolution. `--tone-lexicon`, `--ner-name-rules`, `--count-rules`, and `--theme-lexicon` accept custom
JSON resources for later experiments. `--workers` controls retrieval threads;
the NLP model is loaded once and reused sequentially.

`--ner-name-policy` selects `surface`, `gdelt`, or the default
`gdelt-full-names`. The latter uses bundled name rules v1, canonicalizes names and omits single-word
person/organization names from GKG cells; original entity mentions and spans
remain available. `gdelt` keeps single-word organizations. See
[name policies](../api-usage.md#name-policies) for the tradeoff. Replay the original
baseline with `surface`, count v1, and theme v2 explicitly; defaults now select
the independently evaluated revisions.

Undefined metrics are `null`. Both-empty documents count toward exact document
agreement but are excluded from mean document F1. Fetch/language/NLP failures
are counted separately and excluded from score metrics. These are agreement
benchmarks on retrieved text, not gold-standard accuracy measurements. Enhanced
offsets and NER geocoding are not scored because identical native text and
geographic resolution are unavailable. See the [changelog results](../../CHANGELOG.md).
