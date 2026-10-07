# Maintained tools

These commands ship with the package and are available after installation or `uv sync`. Each tool can also be run with `python -m gdelt_regkg.scripts.<module>`. Imports and normal extraction never run maintenance tools or download resources.

From a checkout, prefix commands with `uv run` to use the project's virtual environment.

| Installed command | Purpose |
| --- | --- |
| `gdelt-regkg-build-resources` | Build local tone/theme/count/name/GCAM/geographic profiles from source inputs |
| `gdelt-regkg-build-gazetteer` | Compile geographic references from supplied GKG archives |
| `gdelt-regkg-build-gcam` | Build General Inquirer counts, VADER means and optional licensed Lexicoder input |
| `gdelt-regkg-expand-gcam` | Add General Inquirer, Roget, WordNet and GCAM theme dimensions using native keys |
| `gdelt-regkg-benchmark-fields` | Compare locations, dates, amounts, broad names, quotations and GCAM on saved bodies |
| `gdelt-regkg-benchmark-samples` | Collect fixed development/benchmark samples across seasonal months and daily windows |
| `gdelt-regkg-benchmark-tone` | Compare tone against original GDELT records and article bodies |
| `gdelt-regkg-benchmark-extraction` | Compare NER, counts, and themes on one fixed article sample |
| `gdelt-regkg-benchmark-ner` | Compare raw and normalized person/organization names |
| `gdelt-regkg-benchmark-counts` | Compare count labels, quantities, objects, and complete tuples |
| `gdelt-regkg-benchmark-themes` | Compare complete and supported theme vocabularies |
| `gdelt-regkg-refine-tone` | Fit and evaluate a candidate dictionary revision using separate training, validation, and test dates |

## Resource arguments

[Installation and setup](../docs/installation.md) is the guide for preparing dictionaries and models, selecting a basic or full profile, and obtaining benchmark/development inputs. Extraction and benchmark commands select prepared profiles with `--resources-dir` (default `local-resources`); explicit per-file overrides take precedence. Build commands select raw files with `--sources-dir` or individual source flags and write to `--output`.

The importers accept separately supplied sources and do not fit against article bodies. `gdelt-regkg-build-gcam` builds General Inquirer, VADER and optional Lexicoder profiles; `gdelt-regkg-expand-gcam` adds categories. `gdelt-regkg-build-gazetteer` accepts GKG ZIP archives and JSON/gzip output. Use each command's `--help` for its arguments.

`gdelt-regkg-expand-gcam --download-roget` and `--download-lexicoder` request checksum-verified downloads to `--sources-dir` (default `downloads/resources`). Review [Lexicoder's agreement](https://www.snsoroka.com/s/LSDagreement.pdf) before using its dictionary. Without download flags, the command uses only supplied local sources.

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

Use `--offline` to replay cached pages and `--lexicon path/to/tone.json` to compare a candidate dictionary. Use a separate output directory to preserve earlier measurements. Live pages may differ from the text originally processed by GDELT. See [benchmark methods and results](../CHANGELOG.md).

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
[Installation and setup](../docs/installation.md#best-supported-setup).

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
[name policies](../docs/usage.md#name-policies) for the tradeoff. Replay the original
baseline with `surface`, count v1, and theme v2 explicitly; defaults now select
the independently evaluated revisions.

Undefined metrics are `null`. Both-empty documents count toward exact document
agreement but are excluded from mean document F1. Fetch/language/NLP failures
are counted separately and excluded from score metrics. These are agreement
benchmarks on retrieved text, not gold-standard accuracy measurements. Enhanced
offsets and NER geocoding are not scored because identical native text and
geographic resolution are unavailable. See the [changelog results](../CHANGELOG.md).

## Refine a tone revision

```shell
gdelt-regkg-refine-tone --results ./benchmark-results/results.jsonl --train-dates 20260922 20260924 20260926 20260928 --validation-date 20261002 --test-date 20261003 --gi-source inqtabs.txt --output ./tone-revision --check-language
```

The tool starts from tone v1, fits candidate word edits on training records, selects on validation, and evaluates on the held-out test date. It writes the candidate dictionary, token edits, split audit, and comparisons. A candidate does not become the library default automatically; review its changes and independent measurements before recording a new numbered revision.

## Formatting

```shell
uv run pre-commit install
uv run pre-commit run --all-files
```

The hooks sort imports and format Python with Ruff. Type checking and broad lint checks are outside this formatting pass.

## Seasonal sample collection

The [fixed sample plan](benchmark-plan.json) selects eight days per split
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
