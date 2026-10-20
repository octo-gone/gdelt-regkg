# Benchmarking

`gdelt-regkg-cli benchmark` evaluates prepared [Global Knowledge Graph (GKG)](../get-started/concepts-and-glossary.md#gkg) rows or generates predictions from saved article bodies. It writes metrics into Markdown files and CSV tables for future use.

Install the [benchmark dependencies](../get-started/installation-and-setup.md#benchmark-and-development) before running this command.

## Compare prepared outputs

```shell
gdelt-regkg-cli benchmark --reference native.gkg.csv.zip --prediction reconstructed.tsv --output benchmark-results
```

`--reference` and `--prediction` each accept one or more files or directories. Directories are searched recursively, in sorted path order. Overlapping input paths include each resolved file only once. Rows are matched by document keys across all files. Filenames and file order do not determine the pairs.

```shell
gdelt-regkg-cli benchmark --reference data/native --prediction data/predicted --output benchmark-results
gdelt-regkg-cli benchmark --reference january.zip february.zip --prediction predictions-a.tsv predictions-b.jsonl --output benchmark-results
```

Input files must use one of these formats:

| Extension | Required contents |
| --- | --- |
| `.csv`, `.tsv` | UTF-8 GKG rows with exactly 27 **tab-separated** columns in GKG order<br>an official column-name header is optional |
| `.jsonl` | One JSON object per line, with encoded GKG fields as strings or `null` |
| `.csv.gz`, `.tsv.gz`, `.jsonl.gz` | A gzip-compressed file in the corresponding format above |
| `.zip` | CSV, TSV or JSONL members in the formats above, including members in subdirectories |

Extensions are case-insensitive. Directory discovery ignores other extensions. An explicitly supplied unsupported file is an error. ZIP readers ignore other member types and do not unpack nested archives. Compression wraps a supported format. Arbitrary CSV layouts, JSON arrays and unrelated JSON objects are not GKG inputs.

> [!CAUTION]
> Keep report outputs outside input directories. Recursive discovery can otherwise pick up generated report CSVs as GKG inputs on subsequent runs.

JSONL field names can be official column names, such as `V1THEMES`, or the short names below. Supply `document`, `date` and `source_collection` for default matching (`url` is also accepted for `document`). The default source-collection filter selects `"1"`. For example:

```json
{"document":"https://example.org/story","date":"20260101000000","source_collection":"1","themes":"PROTEST;","tone":"0,1,1,2,3,4,100"}
```

Field values use GKG's encoded cell syntax. Theme lists and tone arrays must not be supplied as JSON arrays. Missing fields and `null` mean unavailable. An empty string is an evaluated empty result. Malformed rows are audited and skipped, or fail the run with `--strict`. Malformed individual fields are audited separately.

For [Global Content Analysis Measures (GCAM)](../get-started/concepts-and-glossary.md#gcam-and-dimensions) count errors, declare the lexicon that produced the predictions:

```shell
gdelt-regkg-cli benchmark --reference native.jsonl --prediction reconstructed.jsonl --fields gcam --gcam-lexicon local-resources/lexicons/gcam.v5.json.gz --output benchmark-gcam
```

Add `--gcam-disable roget 26` to exclude dictionaries by canonical name or native ID from generation and scoring. The selection is recorded in the report and prediction cache signature. The declared inventory includes value-only score dimensions. Count/value pairs contribute one category to coverage. See [GCAM profiles](../reference/fields/gcam.md#profiles) and [dictionary selection](../reference/fields/gcam.md#select-dictionaries).

Without `--gcam-lexicon`, the selected profile in `--resources-dir` is used when available. With no inventory, category-presence and paired weighted-score rows are still evaluated, while supported count errors and coverage are unavailable. An omitted sparse count becomes zero only for declared implemented dimensions. For multilingual inventories, supported count errors use only languages evaluated for each article. Generated predictions record their evaluated languages. Prepared JSONL predictions can supply `_gcam_languages`, for example `["eng", "fra"]`, as an encoded JSON string. Without this metadata, a multilingual inventory assumes English analysis. Native count densities use `nwc`. English densities use `wc`. Missing native companion counts for weighted means are excluded, including from presence matching. Defined zero-valued means are valid score observations. Weighted-score sign agreement treats absolute values at most `1e-9` as zero to ignore floating-point cancellation. This does not change the scores used for [mean absolute error (MAE)](../get-started/concepts-and-glossary.md#mae), RMSE, bias or correlation. Tone uses its separate `--tone-neutral` threshold.

### GCAM agreement and sampling

Regular `metrics.md` and `metrics.csv` include a **GCAM / languages** overview with evaluated article counts, compiled dimensions and presence precision, recall and [F1](../get-started/concepts-and-glossary.md#f1-scores). Languages in the inventory with no evaluated text show zero articles and undefined scores. By default, each dictionary has one group across languages, such as **GCAM / ML-SENTICON Multilingual**. Dimension numbers sort numerically: `v23.1`, `v23.2`, …, `v23.10`. All weighted-score errors, availability, agreement and coverage rows stay under their dictionary. Markdown resolves dimension names from the supplied profile/codebook using **code / interpretation / calculation**, for example **v19.1 / Valence (Pleasure) (All) / score availability** or **v24.3 / French (fra) / Happiness / weighted score**. CSV retains the machine-readable `calculation` and adds `dimension_key` and `dimension_name` columns. Unknown dimension names retain their identifiers.

Add `--gcam-split-languages` for separate groups such as **GCAM / ML-SENTICON Multilingual / Catalan (cat)**. The language then appears in the heading rather than being repeated in each dimension interpretation. Each dimension's score rows appear once in either layout. Use `--no-gcam-split-languages` to explicitly select the default joined layout.

These groups identify the dictionary/text language. A French article supplied with an English translation contributes English dimensions to the English group and native French dimensions to the French group. Language article counts can therefore overlap. A supplied language without implemented native dimensions is shown with zero compiled dimensions. CSV `language` identifies split groups. `subset` retains any month, source or other article selection. A bilingual article can appear once per analyzed language in split article diagnostics. Joined article diagnostics contain one row per selected article and subset.

`--gcam-language` is optional. Omit it to score all analyzed streams together and retain the language overview. Set `--gcam-language eng` to evaluate English dimensions only, or `fra` for French dimensions only. This is a scoring filter. It does not select a translation engine or change which bodies were supplied. Native evaluation still requires `original_text` and `original_language`. `--include-translated` accepts records marked translated. Without per-article language metadata, encoded predictions assume English.

See [GCAM metrics](../evaluation/methodology.md#gcam-metrics) for presence scopes, count errors and weighted-score interpretation.

| Option | Effect |
| --- | --- |
| `--gcam-language fra` | Evaluate French dimensions on articles whose original French text was analyzed. English translation dimensions are excluded. Requires a language-aware inventory. |
| `--gcam-split-languages` | Split dictionary groups by language. The default joined layout shows every dictionary once. `--no-gcam-split-languages` explicitly joins groups. |
| `--gcam-max-word-count-difference 0.1` | Retain pairs with `abs(predicted-reference)/reference <= 0.1`. Uses `wc` for English and `nwc` for a selected native language<br>missing or zero counts exclude a pair. |
| `--gcam-sample-size 10000` | Reservoir-sample eligible matched pairs uniformly after language and size filtering. Other requested fields retain their original population. |
| `--gcam-bootstrap-samples 500` | Add 95% publisher-cluster percentile intervals for presence micro F1, mean article Jaccard and supported-count WAPE. |
| `--gcam-seed 17` | Fix sampling and bootstrap draws for reproducibility. |

`--gcam-bootstrap-samples 500` draws 500 replacement samples of publishers and recomputes the metrics from the existing predictions. All selected articles from a sampled publisher stay together, accounting for their shared source. The 2.5th and 97.5th percentiles form the reported 95% interval. This describes how sensitive a metric is to the publisher sample. It does not remove body differences or reference errors. The default `0` disables intervals. More replicates stabilize the interval estimates rather than improve the predictions. `--gcam-seed` makes the draws reproducible. Bootstrapping does not exclude articles or change the point estimates. It quantifies the uncertainty from having only a sample of publishers. Keeping publisher groups together avoids treating related articles from the same source as independent observations in the resampling model. It does not correct retrieval bias, missing dictionaries, segmentation errors or changed bodies.

For one combined multilingual report, omit `--gcam-language`:

```shell
gdelt-regkg-cli benchmark --reference native.jsonl --corpus multilingual-articles.jsonl --fields gcam --include-translated --gcam-lexicon local-resources/lexicons/gcam.v5.json.gz --gcam-bootstrap-samples 500 --gcam-seed 17 --output benchmark-multilingual
```

For a report restricted to French:

```shell
gdelt-regkg-cli benchmark --reference native.jsonl --corpus articles.jsonl --fields gcam --include-translated --gcam-language fra --gcam-lexicon local-resources/lexicons/gcam.v5.json.gz --gcam-bootstrap-samples 500 --gcam-seed 17 --output benchmark-french
```

For English body-size comparisons, run an unrestricted baseline and a second run adding `--gcam-max-word-count-difference 0.1`. Keep other settings fixed. Similar length does not establish identical historical text. Filtering changes the population. Intervals describe that selected subset and do not correct retrieval bias or uncertainty about dictionary sources and conversions. At least two publisher clusters are required. Small subsets yield unstable intervals. Publisher identifiers come from the reference source, falling back to its URL hostname. Each bootstrap draw retains all selected articles from the sampled publisher. Split language groups use the subset selected for the combined report. Sampling and size filtering are not repeated independently for each group. Without `--gcam-language`, the size filter uses English `wc`. Select a native language explicitly to filter on its `nwc` instead.

GCAM writes additional reports separately from the main metric table:

- `gcam-sources.md` / `.csv`: implemented source-backed, approximate and unspecified dimensions, following profile annotations. Source-backed does not imply independently verified matching or scores.
- `gcam-sampling.md` / `.csv`: selection counts, preselection word-count ratios and optional bootstrap intervals.
- `gcam-dimensions.csv`: category support, detection errors, active count errors and paired weighted-score diagnostics, including unsupported observed categories. The `source_type` column classifies each dimension as source-backed, approximate, unspecified or unimplemented.
- `gcam-articles.csv`: selected article identifiers, evaluated languages, word counts and category agreement for inspecting body and sampling differences.

### Prepare external corpora

Normalize saved `source_text` / English translation pairs and split them by source language without retrieving or translating articles:

```shell
python -m gdelt_regkg.benchmark.prepare --corpus saved-articles.jsonl --split-languages --output language-corpora --seed 17
```

Preparation retains at most 10,000 eligible records by default. For corpora containing the original 27 `native_cells`, export an aligned reference sample and select similar English body sizes before prediction:

```shell
python -m gdelt_regkg.benchmark.prepare --corpus saved-corpus --language eng --sample-size 10000 --max-word-count-difference 0.1 --reference-output sample-reference.jsonl --output sample.jsonl --seed 17
```

Omit the size option for the baseline. Sampling spans all supplied files. The manifest records language/month counts, eligibility and selection hashes. Preparation size matching accepts English bodies only. Native size matching is available during benchmarking when reference `nwc` exists.

To fetch original bodies from supplied GDELT translated archives, install the `benchmark` and `lang` extras and run:

```shell
python -m gdelt_regkg.benchmark.acquire --reference translated-archives --languages fra spa deu --target-per-language 50 --output native-corpus --seed 17
```

Acquisition screens new bodies in languages supported by Lingua, limits retrieval time and records failures and publisher counts. `--seed-corpus` reuses existing pairs with matching record IDs and URLs. Fetched original bodies have `text: ""`, `original_text`, `original_language` and `gcam_native_only: true`. Benchmark each language file with `--fields gcam`, `--include-translated` and its `--gcam-language` value. The analyzer's dual-text API is unchanged. Fresh bodies can differ from GDELT's original text, and reachable articles are a convenience sample. Corpus data stays external. Languages outside Lingua's inventory retain GDELT's source label and are marked as unverified in retrieval metadata and the manifest.

## Generate predictions from saved bodies

```shell
gdelt-regkg-cli benchmark --reference original-1.gkg.csv.zip original-2.gkg.csv.zip --corpus saved-articles.jsonl --resources-dir local-resources --ner-model en_core_web_lg --output benchmark-bodies
```

`--corpus` accepts JSONL files, `.jsonl.gz` files, ZIP archives containing JSONL, and directories searched recursively for those extensions. These article records use a different schema from the GKG rows accepted by `--prediction`.

Saved bodies are JSONL objects containing `text`, `url` (or `document`), and optionally `record_id` and `text_sha256`. Failed records and unavailable bodies are audited. Supplied text hashes are verified. Reference rows are restricted to documents in the selected corpus. Matching native rows provide alignment metadata. Validity of that supplied metadata is not an NLP accuracy measure. Media and extra XML are evaluated only when supplied in the article record. Supply these as encoded strings under their short field names, for example `"related_images": "https://example.org/a.jpg;https://example.org/b.jpg"`.

Only requested extractors and their dependencies run. Prepare their resources and the requested named entity recognition (NER) model first. Count geography also needs shared NER and the gazetteer. No article retrieval, model download, resource fitting, or translation runs during benchmarking. `--include-translated` accepts already translated saved bodies. Records marked `translation_pending` are excluded. For native GCAM scoring, retain `text` as the prepared English body and supply `original_text` and `original_language`:

```json
{"url":"https://example.org/story","text":"Love and happiness.","translated":true,"original_text":"Amour et bonheur.","original_language":"fra"}
```

`original_text_sha256` is optional and verified when supplied. Otherwise it is computed. Original text and language participate in prediction cache signatures. No translation engine is inferred from these inputs. Only GCAM analyzes the original body. Chinese original-text scoring requires the `build` extra. Prediction cache signatures include the Jieba package version. `--numeric-date-order mdy` or `dmy` applies to date and amount extraction.

### Checkpoints and memory

Benchmark runs stage article bodies and GKG rows in `OUTPUT/benchmark.sqlite3`. Use `--cache path/to/benchmark.sqlite3` to choose a different workspace. Encoded predictions commit after every batch and are reused automatically on subsequent runs. After interruption, rerun the same command. Only the unfinished batch and missing predictions need extraction again. Input files are read again and text hashes are checked before reuse.

Checkpoint compatibility includes text hashes, supplied metadata, selected fields, model files, resource files, extraction code, library versions, numeric date settings, device and batch settings. Changes produce new entries instead of reusing incompatible predictions. Scoring options such as offset tolerance can change without regenerating otherwise compatible predictions.

Bodies and encoded outputs stay on disk. RAM holds the model, dictionaries, small row handles and the current extraction batch or field's scoring data. Large runs therefore need disk space for the uncompressed bodies, references and predictions. The database retains compatible predictions across runs. Delete it while idle when those checkpoints are no longer needed. Keep it outside input directories so directory discovery includes only input data. One process may use a cache at a time.

### Model device and batching

NER uses batches of up to 16 articles by default. `--batch-size` changes that limit. `--batch-chars` limits the target total character count (default 100,000). A single longer article is processed intact. Smaller batches reduce peak model memory use.

```shell
gdelt-regkg-cli benchmark --reference native --corpus articles --ner-model en_core_web_lg --device cuda --gpu-id 0 --batch-size 16 --output benchmark-bodies
```

Choose the inference device using [GPU setup](gpu-setup.md#benchmark-generation). The selected device is recorded in `run.md`, and CPU and GPU checkpoints are kept separate because predictions can differ. Compiled CUDA kernels are cached in `cupy-kernels/` beside the SQLite workspace, unless `CUPY_CACHE_DIR` already selects a location.

To reuse cached NER, pass `--ner-cache cached-ner.jsonl`. Each cached record needs the matching `record_id`, `url`, `text_sha256`, and an `entity_mentions` list. Each mention supplies `text`, `start`, `end`, `label`, and optional `source_label`. Cached offsets must refer to the unchanged saved body. Optional `name_mentions` provide broad names, with `text`, `start`, `end`, and optional `source_label`. Without broad-name spans, all-name results are marked unavailable rather than approximated from entity spans. Missing or mismatched cache records fail the run.

## Select fields and calculations

Use space-separated or comma-separated names with `--fields`. The default is `all`. Use `--exclude` to omit fields or groups.

| Group | Included fields |
| --- | --- |
| `metadata` | `recordid`, `date`, `source_collection`, `source`, `document` |
| `counts` | `counts`, `enhanced_counts` |
| `themes` | `themes`, `enhanced_themes` |
| `ner` | `persons`, `enhanced_persons`, `organizations`, `enhanced_organizations` |
| `locations` | `locations`, `enhanced_locations` |
| `dates` | `enhanced_dates` |
| `media` | `sharing_image`, `related_images`, `social_image_embeds`, `social_video_embeds` |

Other fields are `tone`, `gcam`, `quotations`, `all_names`, `amounts`, `translation`, and `extras_xml`. Individual enhanced field names can also be selected directly.

```shell
gdelt-regkg-cli benchmark --reference native.tsv --prediction reconstructed.tsv --fields counts themes tone --output benchmark-selected
```

See [matching and field calculations](../evaluation/methodology.md#matching-and-field-calculations) for exact and relaxed comparisons, offset pairing, coordinate errors and invalid-value handling.

## Reports

Every run writes:

- `metrics.md`: field groups with calculations arranged by metric layout, using five metric slots.
- `metrics.csv`: the same results, with explicit metric columns and full numeric precision.
- `audit.csv`: unmatched documents, ambiguous duplicates, invalid fields and unavailable values.
- `run.md`: input hashes, resources, settings and interpretation notes.

For general metric definitions and formulas, see [Concepts and glossary](../get-started/concepts-and-glossary.md#evaluation-and-metrics). [Methodology](../evaluation/methodology.md) specifies matching rules, evaluated populations and undefined scores.

Markdown shows metric labels in bold above their values on the first row of each layout. Following rows with that layout show values only. Each field and subset starts a new group. A `-` means a metric has no value. An empty cell means there is no metric in that slot. CSV retains explicit columns and uses empty cells for undefined or inapplicable metrics. CSV percentage metrics are fractions. Markdown labels percentages explicitly. Density errors are in percentage points. Numeric error units are recorded per row. Raw input JSONL is supported. JSON reports are not written.

## Alignment, subsets and diagnostics

The default `--match document-date` uses source collection, the exact document identifier, and batch timestamp. `--match document` omits the timestamp. `--match record-id` uses record ID and document identifier together. Identical duplicate rows are deduplicated and counted. Conflicting duplicate keys are excluded from pairing instead of being paired by row order. Runs with no unambiguous matches fail. The default source collection is `1`. Use `--source-collections all` or a list of IDs to change it.

Malformed input rows are audited and skipped. `--strict` makes them fail the run. Per-field parse exclusions are visible in either mode.

`--stratify month translation word_count source` adds subset-specific rows. `--min-stratum` defaults to 10 documents and `--max-strata` to 20 reported subsets. The output records subset names separately in CSV and prefixes them in Markdown. `--diagnostics` adds legacy/enhanced set consistency and theme/person/location proximity scores. `--proximity-window` defaults to 200 characters.

Native GKG values are an imperfect reference. Saved bodies and offsets may differ from the text originally processed by GDELT. Coordinate errors concern paired geographic identities, and GCAM supported-category scores are distinct from full-reference coverage. Weighted scores require both values to be defined. Report the evaluated population and matching rules alongside accuracy claims.

## SQLite ownership and timeout

The default workspace is `OUTPUT/benchmark.sqlite3`. Select its path with `--cache` and its busy timeout with `--cache-timeout SECONDS` (default five seconds). File databases use WAL. Each run owns an independent connection and holds an exclusive workspace lock through batch commits. Use separate workspaces for simultaneous benchmark runs. Connections and locks close on completion or error, and uncommitted work is rolled back.

Library callers use `BenchmarkStore(path, timeout=5)` as a context manager or call its idempotent `close()`. Instances are thread-affine. Create one inside each worker rather than sharing it across threads. Build requests use frozen `BuildOptions`, prediction requests use `PredictionOptions`, and scoring requests use `BenchmarkOptions`.

### Article-level statistics

Add `--article-metrics articles.jsonl.gz` to stream article-level sufficient statistics for the main matched population. `.jsonl` writes uncompressed output. The export records document keys, publisher, date, field, calculation and language. Categorical rows contain matches, reference/prediction support, exact agreement and Jaccard; numeric rows contain reference/prediction values; GCAM count rows contain active supported count error and native count mass by dictionary. These contributions support publisher-cluster resampling and pooled subset analysis without repeating extraction. Optional `--stratify` report rows are not duplicated in this export. Missing numeric values remain `null`; field exclusions remain in the regular audit. The destination is replaced only after successful scoring.

## Archived implementation

For the previous benchmark scripts and reports, see version 1.0.2 on [PyPI](https://pypi.org/project/gdelt-regkg/1.0.2/) and the [GitHub v1.0.2 tag](https://github.com/octo-gone/gdelt-regkg/tree/v1.0.2).
