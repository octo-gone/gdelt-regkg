# Maintained tools

These commands ship with the package and are available after installation or `uv sync`. Run the resource CLI with `gdelt-regkg-cli` or `python -m gdelt_regkg`. Imports and normal extraction never run maintenance tools or download resources.

From a checkout, prefix commands with `uv run` to use the project's virtual environment.

All resource construction uses `gdelt-regkg-cli build`. Reusable converters live
in `gdelt_regkg.builders`; the `scripts` package contains benchmark and development tools.

| Installed command | Purpose |
| --- | --- |
| `gdelt-regkg-cli build` | Resolve source inputs and build local extraction resources |
| `gdelt-regkg-benchmark-fields` | Compare locations, dates, amounts, broad names, quotations and GCAM on saved bodies |
| `gdelt-regkg-benchmark-samples` | Collect fixed development/benchmark samples across selected months and daily windows |
| `gdelt-regkg-benchmark-tone` | Compare tone against original GDELT records and article bodies |
| `gdelt-regkg-benchmark-extraction` | Compare NER, counts, and themes on one fixed article sample |
| `gdelt-regkg-benchmark-ner` | Compare raw and normalized person/organization names |
| `gdelt-regkg-benchmark-counts` | Compare count labels, quantities, objects, and complete tuples |
| `gdelt-regkg-benchmark-themes` | Compare complete and supported theme vocabularies |
| `gdelt-regkg-refine-tone` | Fit and evaluate a candidate dictionary revision using separate training, validation, and test dates |

## Resource arguments

The `build` subcommand uses positional targets and repeatable named source inputs.

```shell
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
gdelt-regkg-cli build counts ner --output local-resources
gdelt-regkg-cli build themes --authored-themes-only --output local-resources
gdelt-regkg-cli build tone --source general-inquirer=downloads/resources/inqtabs.txt --output local-resources
```

Use `gdelt-regkg-cli build --help` for all build options. From a checkout, use
`uv run gdelt-regkg-cli build ...` or `python -m gdelt_regkg build ...` in an
environment where the package is installed.

Choose the targets explicitly, or use `all`; output defaults to `local-resources/`.
The resolver selects inputs required by the targets, including GCAM's theme
dependencies. Explicit `--source NAME=PATH` inputs take precedence over files discovered in
`--sources-dir`; discovered files are checked against the recorded recipe.
Downloads require `--download-sources`. Counts and name rules need no external
sources; `--authored-themes-only` also removes the CrisisLex requirement for themes
and their use within GCAM. Use `--gazetteer-archives` for explicit location-reference
inputs; the recorded gazetteer recipe is unchanged.

Each selected target produces exactly one profile. The default `--use best`
selects the current supported recipe, and partial builds preserve unrelated
`defaults.json` selections. Previous files remain available when you build another
recipe into the same directory; only the newly built profile becomes selected.

Build progress appears immediately on stderr: source checks and downloads, each
target and GCAM component, and output preparation and publication. The final
`Built ...` summary is written to stdout.

Builds also compare recorded output hashes from `recipes.json` with the compiled
JSON, independently of `--suffix` or filename overrides. A mismatch prints a
warning and the build continues; custom inputs or options may legitimately differ.
Matching hashes appear in progress output. Custom recipes without a recorded hash
are not compared. Hashes cover parsed JSON, including metadata and array order,
and do not depend on indentation, object key order, or gzip compression.

### Recipes and filenames

`--use` determines the contents. `--suffix` changes only the filename label,
preserving the resource stem and `.json` or `.json.gz` extension. For example,
`build tone --use v1 --suffix experiment` writes `lexicons/tone.experiment.json`
using the v1 recipe. Labeling a current build `v1` does not turn it into the v1 recipe.

| Target | Default recipe | Other recipes |
| --- | --- | --- |
| `tone` | `v3` | `v1`, `v2` |
| `themes` | `v3` | `v1`, `v2`, `authored` |
| `counts` | `v3` | `v1`, `v2` |
| `ner` | `v1` | — |
| `locations` | `v1` | — |
| `gcam` | `v3` | `v1`, `v2`, `full` |

Rebuild the historical profiles explicitly (the source directory must contain
the recorded input files; add `--download-sources` to fetch missing inputs):

```shell
gdelt-regkg-cli build tone themes counts gcam --use v1 --suffix v1 --sources-dir downloads/resources
gdelt-regkg-cli build tone themes counts gcam --use v2 --suffix v2 --sources-dir downloads/resources
gdelt-regkg-cli build tone themes counts gcam --use v3 --suffix v3 --sources-dir downloads/resources
```

Or request one resource and one recipe:

```shell
gdelt-regkg-cli build counts --use v1 --suffix baseline
gdelt-regkg-cli build tone --suffix experiment --sources-dir downloads/resources
gdelt-regkg-cli build themes --use authored --suffix custom
```

Tone v1 imports General Inquirer; v2 and v3 replay the recorded edits in order.
Theme v1 restores the original candidates and CrisisLex; v2 adds the seed rules;
v3 applies the evaluated revision. Count recipes select the corresponding authored
rule file. Earlier stages may be needed to compute a recipe, but only the requested
result is written. `--use` applies to every target in that invocation; incompatible
target/recipe combinations are rejected before downloading.

[Installation and setup](../docs/installation.md) is the guide for preparing dictionaries and models, selecting a basic or full profile, and obtaining benchmark/development inputs. Extraction and benchmark commands select prepared profiles with `--resources-dir` (default `local-resources`); explicit per-file overrides take precedence. Build commands select raw files with `--sources-dir` or individual source flags and write to `--output`.

### GCAM profiles and expansion

GCAM `--use v1` builds the General Inquirer subset; `v2` adds VADER.
`v3` (the default) also includes full General Inquirer categories, WordNet and themes.
`--use full` adds Roget and Lexicoder. Review [Lexicoder's agreement](https://www.snsoroka.com/s/LSDagreement.pdf)
before using its dictionary.

```shell
gdelt-regkg-cli build gcam --use full --sources-dir downloads/resources --download-sources
gdelt-regkg-cli build gcam --use v2 --gcam-add lexicoder --source general-inquirer=downloads/resources/inqtabs.txt --source vader=downloads/resources/vader_lexicon.txt --source lexicoder=downloads/resources/LSDaug2015.zip --suffix custom
gdelt-regkg-cli build gcam --gcam-baseline local-resources/lexicons/gcam.v3.json.gz --gcam-add roget lexicoder --sources-dir downloads/resources --suffix full
```

`--gcam-add` adds or replaces selected components. It accepts `general-inquirer`,
`vader`, `roget`, `wordnet-lexical`, `wordnet-affect`, `wordnet-domains`, `themes`
and `lexicoder`. A baseline needs only the sources for the selected additions.
Use `--affect-propagate-hierarchy` and `--affect-nouns-only` for experimental
WordNet Affect variants. `--source wordnet-annotations=PATH` supplies both Affect
and Domains; separate inputs use `--source wordnet-affect=PATH` and
`--source wordnet-domains=PATH`.

Default filenames are `gcam.v1.json`, `gcam.v2.json`, `gcam.v3.json.gz`,
`gcam.full.json.gz` and `gcam.custom.json.gz` for customized builds.
`--suffix` overrides the label; `--gcam-filename` accepts a complete basename
when you also need to choose JSON versus gzip. All profiles go into `--output/lexicons/` and become selected in
`defaults.json`. Converters use the supplied dictionaries without fitting to articles.

### Custom gazetteer

```shell
gdelt-regkg-cli build locations --gazetteer-archives reference/first.gkg.csv.zip reference/second.gkg.csv.zip --gazetteer-name my-places --suffix custom --output local-resources
```

Use `--gazetteer-name` to name the profile and `--suffix` to label its filename.
`--gazetteer-filename` accepts a complete basename when you need JSON instead of
gzip. Complete GCAM and gazetteer filenames accept `.json` or `.json.gz`; use
either a complete filename or a suffix.

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
