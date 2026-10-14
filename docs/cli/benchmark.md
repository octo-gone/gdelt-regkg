# Benchmark GKG fields

`gdelt-regkg-cli benchmark` evaluates prepared GKG rows or generates predictions
from saved article bodies. It writes Markdown and CSV tables.

Install the [benchmark dependencies](../installation.md#benchmark-and-development) before running this command.

## Compare prepared outputs

```shell
gdelt-regkg-cli benchmark --reference native.gkg.csv.zip --prediction reconstructed.tsv --output benchmark-results
```

`--reference` and `--prediction` each accept one or more files or directories.
Directories are searched recursively, in sorted path order. Overlapping input
paths include each resolved file only once. Rows are matched by document keys
across all files; filenames and file order do not determine the pairs.

```shell
gdelt-regkg-cli benchmark --reference data/native --prediction data/predicted --output benchmark-results
gdelt-regkg-cli benchmark --reference january.zip february.zip --prediction predictions-a.tsv predictions-b.jsonl --output benchmark-results
```

Input files must use one of these formats:

| Extension | Required contents |
| --- | --- |
| `.csv`, `.tsv` | UTF-8 GKG rows with exactly 27 **tab-separated** columns in GKG order; an official column-name header is optional |
| `.jsonl` | One JSON object per line, with encoded GKG fields as strings or `null` |
| `.csv.gz`, `.tsv.gz`, `.jsonl.gz` | A gzip-compressed file in the corresponding format above |
| `.zip` | CSV, TSV or JSONL members in the formats above, including members in subdirectories |

Extensions are case-insensitive. Directory discovery ignores other extensions;
an explicitly supplied unsupported file is an error. ZIP readers ignore other
member types and do not unpack nested archives. Compression wraps a supported
format; arbitrary CSV layouts, JSON arrays and unrelated JSON objects are not
GKG inputs. Keep report outputs outside input directories so subsequent runs do
not discover their CSV files.

JSONL field names can be official column names, such as `V1THEMES`, or the short
names below. Supply `document`, `date` and `source_collection` for default
matching (`url` is also accepted for `document`). The default source-collection
filter selects `"1"`. For example:

```json
{"document":"https://example.org/story","date":"20260101000000","source_collection":"1","themes":"PROTEST;","tone":"0,1,1,2,3,4,100"}
```

Field values use GKG's encoded cell syntax; theme lists and tone arrays must not
be supplied as JSON arrays. Missing fields and `null` mean unavailable; an empty
string is an evaluated empty result. Malformed rows are audited and skipped, or
fail the run with `--strict`. Malformed individual fields are audited separately.

For GCAM count errors, declare the lexicon that produced the predictions:

```shell
gdelt-regkg-cli benchmark --reference native.jsonl --prediction reconstructed.jsonl --fields gcam --gcam-lexicon local-resources/lexicons/gcam.full.json.gz --output benchmark-gcam
```

Without `--gcam-lexicon`, the selected profile in `--resources-dir` is used when
available. With no inventory, category-presence and paired weighted-score rows
are still evaluated, while supported count errors and coverage are unavailable.
An omitted sparse count becomes zero only for declared implemented dimensions.
Missing native companion counts for weighted means are excluded, including from
presence matching. Defined zero-valued means remain valid score observations.
Weighted-score sign agreement treats absolute values at most `1e-9` as zero to
ignore floating-point cancellation. This does not change the scores used for
MAE, RMSE, bias or correlation. Tone uses its separate `--tone-neutral` threshold.

## Generate predictions from saved bodies

```shell
gdelt-regkg-cli benchmark --reference original-1.gkg.csv.zip original-2.gkg.csv.zip --corpus saved-articles.jsonl --resources-dir local-resources --ner-model en_core_web_lg --output benchmark-bodies
```

`--corpus` accepts JSONL files, `.jsonl.gz` files, ZIP archives containing JSONL,
and directories searched recursively for those extensions. These article records
use a different schema from the GKG rows accepted by `--prediction`.

Saved bodies are JSONL objects containing `text`, `url` (or `document`), and
optionally `record_id` and `text_sha256`. Failed records and unavailable bodies
are audited. Supplied text hashes are verified. Reference rows are restricted to
documents in the selected corpus. Matching native rows provide alignment
metadata; validity of that supplied metadata is not an NLP accuracy measure.
Media and extra XML are evaluated only when supplied in the article record.
Supply these as encoded strings under their short field names, for example
`"related_images": "https://example.org/a.jpg;https://example.org/b.jpg"`.

Only requested extractors and their dependencies run. Prepare their resources
and the requested NER model first. Count geography also needs shared NER and the
gazetteer. No article retrieval, model download, resource fitting, or translation
runs during benchmarking. `--include-translated` accepts already translated
saved bodies; records marked `translation_pending` remain excluded.
`--numeric-date-order mdy` or `dmy` applies to date and amount extraction.

### Checkpoints and memory

Benchmark runs stage article bodies and GKG rows in `OUTPUT/benchmark.sqlite3`.
Use `--cache path/to/benchmark.sqlite3` to choose a different workspace. Encoded
predictions commit after every batch and are reused automatically on subsequent
runs. After interruption, rerun the same command; only the unfinished batch and
missing predictions need extraction again. Input files are read again and text
hashes are checked before reuse.

Checkpoint compatibility includes text hashes, supplied metadata, selected
fields, model files, resource files, extraction code, library versions, numeric
date settings, device and batch settings. Changes produce new entries instead
of reusing incompatible predictions. Scoring options such as offset tolerance
can change without regenerating otherwise compatible predictions.

Bodies and encoded outputs stay on disk. RAM holds the model, dictionaries,
small row handles and the current extraction batch or field's scoring data.
Large runs therefore need disk space for the uncompressed bodies, references
and predictions. The database retains compatible predictions across runs;
delete it while idle when those checkpoints are no longer needed. Keep it
outside input directories so directory discovery includes only input data.
One process may use a cache at a time.

### Model device and batching

NER uses batches of up to 16 articles by default. `--batch-size` changes that
limit; `--batch-chars` limits the target total character count (default 100,000).
A single longer article is processed intact. Smaller batches reduce peak model
memory use.

```shell
gdelt-regkg-cli benchmark --reference native --corpus articles --ner-model en_core_web_lg --device cuda --gpu-id 0 --batch-size 16 --output benchmark-bodies
```

`--device cpu` is the default. `--device cuda` requires working CUDA inference
and fails clearly if initialization is unsuccessful. `--device auto` attempts
CUDA and reports a CPU fallback when unavailable. The selected device is
recorded in `run.md`. Install [spaCy GPU support](../installation.md#gpu-inference)
first; CUDA-enabled PyTorch alone does not enable spaCy's CuPy backend.
Compiled CUDA kernels are cached in `cupy-kernels/` beside the SQLite workspace,
unless `CUPY_CACHE_DIR` already selects a location.
GPU acceleration applies to NER. Dictionary matching, count rules, geographic
resolution and metric calculations run on CPU. CPU and GPU model predictions
can differ, so their checkpoints are kept separate.

To reuse cached NER, pass `--ner-cache cached-ner.jsonl`. Each cached record needs
the matching `record_id`, `url`, `text_sha256`, and an `entity_mentions` list.
Each mention supplies `text`, `start`, `end`, `label`, and optional `source_label`.
Cached offsets must refer to the unchanged saved body. Optional `name_mentions`
provide broad names, with `text`, `start`, `end`, and optional `source_label`.
Without broad-name spans, all-name results are marked unavailable rather than
approximated from entity spans. Missing or mismatched cache records fail the run.

## Select fields and calculations

Use space-separated or comma-separated names with `--fields`; the default is
`all`. Use `--exclude` to omit fields or groups.

| Group | Included fields |
| --- | --- |
| `metadata` | `recordid`, `date`, `source_collection`, `source`, `document` |
| `counts` | `counts`, `enhanced_counts` |
| `themes` | `themes`, `enhanced_themes` |
| `ner` | `persons`, `enhanced_persons`, `organizations`, `enhanced_organizations` |
| `locations` | `locations`, `enhanced_locations` |
| `dates` | `enhanced_dates` |
| `media` | `sharing_image`, `related_images`, `social_image_embeds`, `social_video_embeds` |

Other fields are `tone`, `gcam`, `quotations`, `all_names`, `amounts`,
`translation`, and `extras_xml`. Individual enhanced field names can also be
selected directly.

```shell
gdelt-regkg-cli benchmark --reference native.tsv --prediction reconstructed.tsv --fields counts themes tone --output benchmark-selected
```

Exact comparisons are always reported. Their primary definitions preserve
document-level identity sets for themes, names, places, dates, amounts and
quotations. Count quantities and objects retain repeated tuples as multisets.
Text normalization applies Unicode NFKC, case folding, apostrophe normalization
and whitespace collapse; punctuation is retained. Theme codes match exactly.

Enhanced fields have separate content-occurrence, exact-offset and tolerant-offset
rows. Matches are one-to-one, maximizing the number of valid pairs before
minimizing offset distance. `--offset-tolerance` defaults to 100 characters.
Offset-error rows use content matches before the tolerance gate, so large errors
remain visible. Error units and tolerance settings appear in row labels or cells.
Repeated identical mentions can have multiple equally optimal pairings. Their
median and P90 errors can depend on the selected pairing even when match counts
and mean error agree. The run report records statistical-library versions.

`--relaxed` adds separate rows for approximate quantities and objects, and fuzzy
quotation spans. Its options are `--number-tolerance` (relative error, default
0.1), `--object-similarity` (default 0.6) and `--quote-similarity` (default 0.5).
Relative number error divides by the larger of the absolute reference value and
one. Similarity uses a character sequence ratio. Relaxed quotation matches also
use the configured offset tolerance. These scores have different definitions
from exact identity scores and should be compared separately.

## Reports

Every run writes:

- `metrics.md`: field groups with calculations arranged by metric layout, using five metric slots.
- `metrics.csv`: the same results, with explicit metric columns and full numeric precision.
- `audit.csv`: unmatched documents, ambiguous duplicates, invalid fields and unavailable values.
- `run.md`: input hashes, resources, settings and interpretation notes.

Metadata fields each receive one validity row. F1 calculations always include
precision and recall. Coverage rows carry evaluated-document, reference-support
and prediction-support counts. Tone components and GCAM families use separate
rows for numeric errors and associated diagnostics. Constant or insufficient
samples have undefined correlations and concordance rather than perfect scores.

Label-macro rows average over the union of observed reference and prediction
labels. Per-label precision or recall with zero support contributes zero to that
macro average; an entirely empty label population has undefined macro scores.
Validity rows concern the evaluated matched-document population; alignment and
input audits account separately for unmatched or structurally unreadable rows.

Markdown shows metric labels in bold above their values on the first row of
each layout. Following rows with that layout show values only. Each field and
subset starts a new group. A `-` means a metric has no value; an empty cell
means there is no metric in that slot. CSV retains explicit columns and uses
empty cells for undefined or inapplicable metrics.
CSV percentage metrics are fractions; Markdown labels percentages explicitly.
Density errors are in percentage points. Numeric error units are recorded per
row. Raw input JSONL is supported; JSON reports are not written.

Malformed native fields are excluded only from that field's evaluated population.
Malformed categorical predictions are audited and scored as empty predictions;
their reference observations remain false negatives. Numeric-score errors use
valid paired values, with missing/invalid coverage reported separately. Both-empty
documents do not increase F1. Extra XML uses canonical structure comparison and
rejects entity declarations. Translation-information scores concern provenance,
not translation quality.

## Alignment, subsets and diagnostics

The default `--match document-date` uses source collection, the exact document
identifier, and batch timestamp. `--match document` omits the timestamp;
`--match record-id` uses record ID and document identifier together. Identical
duplicate rows are deduplicated and counted. Conflicting duplicate keys are
excluded from pairing instead of being paired by row order. Runs with no
unambiguous matches fail. The default source collection is `1`; use
`--source-collections all` or a list of IDs to change it.

Malformed input rows are audited and skipped; `--strict` makes them fail the
run. Per-field parse exclusions remain visible in either mode.

`--stratify month translation word_count source` adds subset-specific rows.
`--min-stratum` defaults to 10 documents and `--max-strata` to 20 reported subsets.
The output records subset names separately in CSV and prefixes them in Markdown.
`--diagnostics` adds legacy/enhanced set consistency and theme/person/location
proximity scores; `--proximity-window` defaults to 200 characters.

Native GKG values are an imperfect reference. Saved bodies and offsets may differ
from the text originally processed by GDELT. Coordinate errors concern paired
geographic identities, and GCAM supported-category scores are distinct from
all-native coverage. Weighted scores require both values to be defined. Report
the evaluated population and matching rules alongside accuracy claims.

## SQLite ownership and timeout

The default workspace remains `OUTPUT/benchmark.sqlite3`. Select its path with `--cache` and its busy timeout with `--cache-timeout SECONDS` (default five seconds). File databases use WAL. Each run owns an independent connection and holds an exclusive workspace lock through batch commits; use separate workspaces for simultaneous benchmark runs. Connections and locks close on completion or error, and uncommitted work is rolled back.

Library callers use `BenchmarkStore(path, timeout=5)` as a context manager or call its idempotent `close()`. Instances are thread-affine; create one inside each worker rather than sharing it across threads. Build requests use frozen `BuildOptions`, prediction requests use `PredictionOptions`, and scoring requests use `BenchmarkOptions`.

## Archived implementation

For the previous benchmark scripts and reports, see version 1.0.2 on [PyPI](https://pypi.org/project/gdelt-regkg/1.0.2/) and the [GitHub v1.0.2 tag](https://github.com/octo-gone/gdelt-regkg/tree/v1.0.2).
