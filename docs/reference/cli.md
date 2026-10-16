# Command-line reference

Run `gdelt-regkg-cli` or `python -m gdelt_regkg` after [installation](../installation.md). From a development checkout, prefix the command with `uv run`. The CLI builds resources, benchmarks records and refines tone dictionaries; record extraction is available through the [Python API](python-api.md).

```shell
gdelt-regkg-cli --help
gdelt-regkg-cli build --help
gdelt-regkg-cli benchmark --help
gdelt-regkg-cli refine-tone --help
```

## Build

```text
gdelt-regkg-cli build TARGET [TARGET ...] [OPTIONS]
```

Targets are `tone`, `themes`, `counts`, `ner`, `locations` and `gcam`; `all` selects every target. At least one target is required. See [resource preparation](../guides/resources.md) for workflows and [dictionary imports](../guides/dictionary-imports.md) for source conversion.

| Argument | Default | Meaning |
| --- | --- | --- |
| `--output PATH` | `local-resources` | Destination resource root. |
| `--use RECIPE` | `best` | Recipe selection; supported versions depend on the target. `gcam: full` aliases `v5`. |
| `--suffix LABEL` | Unset | Filename label; does not change recipe contents. |
| `--source NAME=PATH` | None; repeatable | Explicit input overriding source-directory discovery. Names are listed by `build --help`. |
| `--sources-dir PATH` | Unset | Directory for recorded source files and explicitly permitted downloads. |
| `--download-sources` | Off | Download required recorded inputs. |
| `--download-mpqa` | Off | Add MPQA and explicitly permit its verified third-party mirror download; requires `--sources-dir`. |
| `--authored-themes-only` | Off | Build themes without CrisisLex, including their use in GCAM. |
| `--gazetteer-archives PATH ...` | Unset | Explicit reference GKG ZIPs for geographic lookup construction. |
| `--gazetteer-name NAME` | `gkg-reference-gazetteer-v1` | Geographic profile name. |
| `--gazetteer-filename NAME` | Unset | Complete JSON/gzip basename, instead of a suffix. |
| `--gcam-baseline PATH` | Unset | Existing GCAM JSON/gzip profile to expand. |
| `--gcam-add NAME ...` | None | Components to add or replace; accepted names are listed by help and the [dictionary reference](dictionaries.md). |
| `--gcam-filename NAME` | Unset | Complete GCAM basename ending in `.json` or `.json.gz`. |
| `--affect-propagate-hierarchy` | Off | Propagate WordNet Affect categories through the hierarchy. |
| `--affect-nouns-only` | Off | Restrict WordNet Affect matching to noun entries. |

Progress and hash-comparison warnings go to stderr; the final `Built ...` summary goes to stdout. Each selected target produces one profile; `defaults.json` selects the new revisions while unrelated selections and previous files remain. See [output layout](../guides/resources.md#output-layout).

## Benchmark

```text
gdelt-regkg-cli benchmark --reference PATH [PATH ...]
    (--prediction PATH [PATH ...] | --corpus PATH [PATH ...]) [OPTIONS]
```

Supply native GKG inputs and exactly one prediction mode. Prepared prediction files are compared directly; corpus mode generates predictions from saved English article bodies and does not translate. Inputs accept files or recursively searched directories. See [benchmarking](../guides/benchmarking.md) for file schemas, examples and reports.

### Inputs and selection

| Argument | Default | Meaning |
| --- | --- | --- |
| `--reference PATH ...` | Required | Native GKG files or directories. |
| `--prediction PATH ...` | Alternative to `--corpus` | Reconstructed GKG files or directories. |
| `--corpus PATH ...` | Alternative to `--prediction` | Saved article-body JSONL files or directories. |
| `--output PATH` | `benchmark-results` | Report and workspace directory. |
| `--fields NAME ...` | `all` | Fields/groups, separated by spaces or commas. |
| `--exclude NAME ...` | None | Fields/groups to omit. |
| `--match MODE` | `document-date` | `document-date`, `document` or `record-id`; see [alignment](../guides/benchmarking.md#alignment-subsets-and-diagnostics). |
| `--source-collections ID ...` | `1` | Source collection IDs, or `all`. |
| `--strict` | Off | Fail on malformed input rows instead of auditing and skipping them. |
| `--stratify [NAME ...]` | None | Subsets by `month`, `source`, `translation` or `word_count`. |
| `--min-stratum N` | `10` | Minimum documents in a reported subset. |
| `--max-strata N` | `20` | Maximum reported subsets. |

### Scoring

| Argument | Default | Meaning |
| --- | --- | --- |
| `--relaxed` | Off | Add explicitly labelled fuzzy/tolerant comparisons. |
| `--offset-tolerance N` | `100` | Character-offset tolerance for relaxed comparisons. |
| `--number-tolerance X` | `0.1` | Relative numeric tolerance in relaxed matching. |
| `--object-similarity X` | `0.6` | Object-text similarity threshold. |
| `--quote-similarity X` | `0.5` | Quotation similarity threshold. |
| `--tone-neutral X` | `0.5` | Absolute tone threshold for neutral sign classification. |
| `--diagnostics` | Off | Add consistency and proximity calculations. |
| `--proximity-window N` | `200` | Character window for proximity diagnostics. |

See [evaluation methodology](../evaluation/methodology.md) for interpretation and [field calculations](../guides/benchmarking.md#select-fields-and-calculations) for the supported groups.

### GCAM

| Argument | Default | Meaning |
| --- | --- | --- |
| `--gcam-lexicon PATH` | Selected local profile when available | Declare implemented dimensions; also overrides GCAM in corpus mode. |
| `--gcam-disable NAME_OR_ID ...` | None | Exclude dictionaries from generation and scoring. |
| `--gcam-language CODE` | All analyzed streams | Restrict scoring to one language. |
| `--gcam-split-languages` / `--no-gcam-split-languages` | Joined | Split or join language groups within dictionaries. |
| `--gcam-max-word-count-difference X` | Unset | Maximum relative predicted/reference word-count difference. |
| `--gcam-sample-size N` | Unset | Reservoir sample after language and size selection. |
| `--gcam-bootstrap-samples N` | `0` | Publisher-cluster bootstrap replicates; zero disables intervals. |
| `--gcam-seed N` | `0` | Sampling and bootstrap seed. |

Language filters select evaluated text streams, not translation engines. Native scoring requires the original body and its language. See [GCAM agreement and sampling](../guides/benchmarking.md#gcam-agreement-and-sampling).

### Models, resources and workspace

| Argument | Default | Meaning |
| --- | --- | --- |
| `--resources-dir PATH` | `local-resources` | Prepared resource root. |
| `--ner-model NAME` | `en_core_web_sm` | Installed spaCy model for corpus generation. |
| `--device MODE` | `cpu` | `cpu`, `cuda` or `auto`; CUDA NER requires CuPy. |
| `--gpu-id N` | `0` | spaCy GPU index. |
| `--batch-size N` | `16` | Maximum articles per NER/checkpoint batch. |
| `--batch-chars N` | `100000` | Target batch character limit; a longer single article remains intact. |
| `--ner-cache PATH` | Unset | Saved entity-mention JSONL matching corpus text hashes. |
| `--include-translated` | Off | Accept already translated saved bodies; performs no translation. |
| `--numeric-date-order ORDER` | Unset | `mdy` or `dmy` for ambiguous numeric dates. |
| `--cache PATH` | `OUTPUT/benchmark.sqlite3` | SQLite workspace and prediction cache. |
| `--cache-timeout SECONDS` | `5` | SQLite busy timeout. |

Reports include `metrics.md` and `metrics.csv`, with additional audit and GCAM files where applicable. Concurrent benchmark writers need separate workspaces. See [reports](../guides/benchmarking.md#reports), [checkpoints](../guides/benchmarking.md#checkpoints-and-memory) and [performance](../guides/performance.md).

## Refine tone

```text
gdelt-regkg-cli refine-tone --results PATH [PATH ...]
    --train-dates DATE [DATE ...] --validation-date DATE --test-date DATE
    --gi-source PATH --output PATH [--check-language]
```

| Argument | Default | Meaning |
| --- | --- | --- |
| `--results PATH ...` | Required | Successful-article JSONL inputs with bodies and native tone scores. |
| `--train-dates DATE ...` | Required | Training dates in `YYYYMMDD` form. |
| `--validation-date DATE` | Required | Separate date for candidate selection. |
| `--test-date DATE` | Required | Held-out evaluation date. |
| `--gi-source PATH` | Required | General Inquirer source file. |
| `--output PATH` | Required | Candidate dictionaries, audits and report destination. |
| `--check-language` | Off | Screen inputs for English. |

The command fits candidates on training dates, selects variants on validation data and evaluates frozen choices on the held-out date. It writes `lexicon.json`, `training_edits.json`, `split_audit.jsonl`, `report.json` and `test_comparison.csv`; candidates do not become defaults automatically. See [tone refinement](../guides/tone-refinement.md) for the input schema and split requirements.
