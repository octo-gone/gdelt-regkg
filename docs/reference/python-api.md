# Python API reference

This reference describes the public interfaces used by the [task guides](../README.md#guides). Import record generation and configuration from `gdelt_regkg`; import standalone analyzers from their corresponding field modules. This reference is maintained manually.

## Contents

- [Record generation](#record-generation)
- [Metadata](#metadata)
- [Records and export](#records-and-export)
- [Availability and errors](#availability-and-errors)
- [Resources](#resources)
- [Field analyzers and results](#field-analyzers-and-results)
- [NER and name policies](#ner-and-name-policies)
- [Language detection](#language-detection)
- [Translation](#translation)
- [Persistent translation cache](#persistent-translation-cache)
- [Build and benchmark interfaces](#build-and-benchmark-interfaces)

## Record generation

Import `generate_gkg` from `gdelt_regkg`.

```text
generate_gkg(
    text, metadata, resources=None, *, overrides=None, ner_result=None,
    count_locations=(), numeric_date_order=None, gcam_disabled_dictionaries=(),
    gcam_original_text=None, strict=False,
) -> GKGRecord
```

| Argument | Type / default | Behavior |
| --- | --- | --- |
| `text` | `str`, required | Prepared English body. All enhanced offsets index this exact string. |
| `metadata` | `RecordMetadata`, required | Caller-supplied identifiers, timestamps, media and extension metadata. |
| `resources` | `Resources` or `None` | `None` constructs default resource configuration. |
| `overrides` | Mapping of wire column names to strings or `None`; default `None` | Replaces text-derived, media or extra-XML output cells. Identity and translation-provenance columns cannot be overridden. Dependencies needed by other fields still run. |
| `ner_result` | `NERResult` or `None` | Precomputed entities for the exact body; takes precedence over the recognizer. |
| `count_locations` | Iterable of `CountLocation`; default `()` | A nonempty collection takes precedence over count geography derived from location analysis. |
| `numeric_date_order` | `"mdy"`, `"dmy"` or `None` | Applies the numeric-date policy consistently to dates and amounts. |
| `gcam_disabled_dictionaries` | Iterable of names, integer IDs or numeric strings; default `()` | Excludes dictionaries before GCAM matching; preserves `wc`. |
| `gcam_original_text` | `str` or `None` | Supplies the original-language body for native GCAM dictionaries. Its language comes from metadata. |
| `strict` | `bool`, default `False` | Raises for unavailable fields instead of returning an incomplete record with a warning. |

The result is a frozen `GKGRecord`. Translate non-English bodies separately and use `RecordMetadata.from_translation` for provenance. See [record generation](../guides/records.md) and [translation](../guides/translation.md).

## Metadata

Import `RecordMetadata` from `gdelt_regkg`.

| Argument | Default | Meaning |
| --- | --- | --- |
| `identifier` | Required | Nonempty document URL, DOI or citation. |
| `batch_time` | Required | UTC batch timestamp as a `datetime`, compact timestamp string or integer. |
| `sequence` | Required | Positive integer; the caller manages uniqueness. |
| `published_at` | `None` | Optional publication timestamp, added to extras as `PAGE_PRECISEPUBTIMESTAMP`. An explicitly supplied extra with this name takes precedence. |
| `source_collection` | `1` | Source collection ID from 1 through 6. |
| `source_name` | `None` | Explicit label; otherwise the hostname is taken from an HTTP(S) document URL. Offline identifiers require a label. |
| `sharing_image` | `None` | Image URL; `""` explicitly means no sharing image. |
| `related_images` | `None` | Iterable of image URLs; `[]` explicitly means none. |
| `social_image_embeds` | `None` | Iterable of supplied image-post URLs; `[]` means none. |
| `social_video_embeds` | `None` | Iterable of supplied video URLs; `[]` means none. |
| `extras` | `None` | Mapping of extension elements; `{}` explicitly means no extras. See [extra XML](fields/extras-xml.md). |
| `source_language` | `None` | Three-letter source-language code for translation provenance. |
| `translation_engine` | `None` | Engine citation, supplied together with `source_language`. |

The batch timestamp fills the record ID and batch-date column. Publication time is separate. Compact timestamps use `YYYYMMDDHHMMSS`; aware datetimes are converted to UTC and naive datetimes are treated as UTC. Record IDs require a known batch time.

`RecordMetadata.from_translation(result, metadata)` returns a new metadata object. It copies language and engine provenance for translated bodies, leaves English passthrough without translation provenance and rejects conflicts with existing provenance. Use `result.text` for record generation.

`metadata.to_mapping()` returns encoded identity and translation cells. `metadata.extensions()` resolves publication metadata into the extra-element mapping. Standalone metadata formatters live in `gdelt_regkg.fields.metadata`; their encodings are documented in the [field reference](fields/README.md).

## Records and export

Import `GKGRecord`, `GKG_COLUMNS`, `serialize_gkg` and `write_gkg` from `gdelt_regkg`.

`GKGRecord` is a frozen mapping with 27 typed attributes. Attribute names include `recordid`, `document`, `counts`, `enhanced_counts`, `themes`, `tone` and `gcam`. Mapping access uses official names, such as `record["V1COUNTS"]`. `GKG_COLUMNS` declares the wire order; see the [complete column index](fields/README.md).

| Interface | Result |
| --- | --- |
| `GKGRecord.from_mapping(values)` | Record from exactly the 27 official column keys. Unavailable values are permitted only for optional cells. |
| `record.to_mapping()` | Ordered dictionary of wire names and encoded values. |
| `record.to_row(allow_incomplete=False)` | Ordered tuple of 27 strings. |
| `serialize_gkg(record, allow_incomplete=False)` | One unquoted TSV line, including its final newline. |
| `write_gkg(records, stream, allow_incomplete=False)` | Writes headerless lines and returns the number written. The caller opens and closes the text stream. |

The export functions also accept mappings with exactly the official keys. Cells must be strings without tabs or newlines. `None` requires `allow_incomplete=True`, which exports it as an empty cell. Export validates records as it encounters them; earlier rows remain written if a later row fails. Open output with UTF-8 encoding and `newline=""`.

## Availability and errors

An empty string means an available result with no matches or values. `None` means unavailable metadata or model-dependent work. These states are distinct until an explicitly permitted incomplete export converts unavailable cells to empty strings.

| Exception or warning | Condition |
| --- | --- |
| `IncompleteGKGError` | `generate_gkg(..., strict=True)` encounters unavailable fields. |
| `IncompleteGKGWarning` | Default generation returns unavailable fields. |
| `OptionalDependencyError` | A selected feature requires an uninstalled optional backend. |
| `ResourceUnavailableError` | A required local dictionary or geographic reference has not been prepared. |
| `LanguageDetectionError` | No language candidate exists, or strict detection rejects the evidence. Import from `gdelt_regkg.fields.language`. |
| `TranslationUnavailableError` | The selected M2M100 model resources cannot be loaded. Import from `gdelt_regkg.fields.translation`. |
| `NERUnavailableError` | The requested spaCy model cannot be loaded. Import from `gdelt_regkg.fields.ner`. |
| `TypeError` / `ValueError` | Invalid input types, values, overrides or cell structure. |

The first four names are available from `gdelt_regkg`. Extractor and backend failures propagate; permissive record generation does not silently convert them into empty results.

## Resources

Import `Resources` from `gdelt_regkg`.

```text
Resources(
    resources_dir=None, tone_lexicon=None, theme_lexicon=None,
    count_rules=None, gazetteer=None, gcam_lexicon=None, recognizer=None,
)
```

`resources_dir` accepts a string or path object. Its default is `local-resources/` under the working directory. Explicit `ToneLexicon`, `ThemeLexicon`, `CountRules`, `Gazetteer` and `GCAMLexicon` objects override directory selections. `recognizer` accepts an `EntityRecognizer`; omitting it leaves NER-dependent cells unavailable unless precomputed NER is supplied.

`tone()`, `themes()`, `counts()`, `places()` and `gcam()` resolve their corresponding objects lazily. Packaged counts and name rules provide authored fallbacks; external vocabularies are prepared locally. Default compiled profiles are cached by resolved path. Reload explicit objects or restart after editing a cached file.

Rule loaders live in `gdelt_regkg.fields.rule_inputs`; field classes also expose `from_json` where documented. See [resource selection](../guides/resources.md#resource-selection) for custom-file examples and [dictionary sources](dictionaries.md).

## Field analyzers and results

Analyze a body once and call the result's `to_gkg()` when an encoded cell is needed. Standard/enhanced pairs use `to_gkg(enhanced=True)` for enhanced output. Entity analysis exposes separate person and organization results; location resolution accepts those precomputed entities.

| Module | Main interfaces | Reference |
| --- | --- | --- |
| `gdelt_regkg.fields.counts` | `analyze_counts(text, *, locations=(), rules=None)` | [Counts](fields/counts.md) |
| `gdelt_regkg.fields.themes` | `analyze_themes` and `ThemeLexicon` | [Themes](fields/themes.md) |
| `gdelt_regkg.fields.tone` | `analyze_tone` and `ToneLexicon` | [Tone](fields/tone.md) |
| `gdelt_regkg.fields.ner` | `analyze_entities` and `SpacyNER` | [Persons](fields/persons.md), [organizations](fields/organizations.md) |
| `gdelt_regkg.fields.locations` | `analyze_locations` and `Gazetteer` | [Locations](fields/locations.md) |
| `gdelt_regkg.fields.gcam` | `analyze_gcam` and `GCAMLexicon` | [GCAM](fields/gcam.md) |
| `gdelt_regkg.fields.dates` | `analyze_dates` | [Date mentions](fields/enhanced-dates.md) |
| `gdelt_regkg.fields.names` | `analyze_names` | [All names](fields/all-names.md) |
| `gdelt_regkg.fields.amounts` | `analyze_amounts` | [Amounts](fields/amounts.md) |
| `gdelt_regkg.fields.quotations` | `analyze_quotations` | [Quotations](fields/quotations.md) |

Structured results retain mention spans and, where applicable, rejected candidates, issues, provenance or diagnostics. The linked field pages describe their options and result access. Mention-based analyzers serialize no accepted matches as an empty cell; numeric fields such as tone and GCAM have their own empty-input and word-count behavior. Core analyzers expect strings; normalize missing dataset values before calling them. Standalone counts do not invoke NER or geographic resolution automatically.

For pandas, install pandas separately and normalize missing values before mapping an analyzer, for example `df["themes"] = df["text"].map(lambda text: analyze_themes(text).to_gkg())` with `analyze_themes` imported from its field module.


### Result types

| Result | Main data |
| --- | --- |
| `CountResult` | `mentions`, `issues` and `profile_name`; each mention retains quantity, object, label and source spans. |
| `ThemeResult` | `mentions` and `lexicon_name`; standard/enhanced encodings share one analysis. |
| `ToneResult` | Seven tone components, including word count; see the [tone field](fields/tone.md#behavior). |
| `NERResult` | Exact `text`, entity `mentions`, backend identity and name policy; `.persons`, `.organizations` and `.locations` select spans. Use `.to_gkg("PERSON")` or `.to_gkg("ORG")`, optionally with `enhanced=True`. |
| `LocationResult` | Resolved `mentions`, `issues`, `gazetteer_name` and compatible `.count_locations` spans. |
| `GCAMResult` | Category `counts`, weighted `values`, `implemented_dimensions`, English `word_count`, optional `native_word_count` and `lexicon_name`. |
| `DateResult`, `AmountResult`, `NameResult`, `QuotationResult` | Structured mentions plus field-specific diagnostics where applicable; `.to_gkg()` encodes their cells. |

Result types are imported from the same modules as their analyzers. Geographic mentions require `analyze_locations` before serialization; `NERResult.to_gkg("LOCATION")` is unsupported.

## NER and name policies

Import `SpacyNER` and `analyze_entities` from `gdelt_regkg.fields.ner`.

```text
SpacyNER.from_model(
    model="en_core_web_sm", *, name_policy="gdelt-full-names",
    name_rules=None, resources_dir=None,
)
```

The factory loads an installed spaCy model. `recognizer.analyze(text)` returns an `NERResult`; `analyze_many(texts, batch_size=32)` yields one result per body. `analyze_entities(text, recognizer=recognizer)` provides the standalone entry point. Results retain the exact body and original mention spans.

### Name policies

| Policy | Behavior |
| --- | --- |
| `"gdelt-full-names"` | Default: normalize names, remove configured person titles and filter organizations with selected name rules. |
| `"surface"` | Retain observed spelling. |
| `"gdelt"` | Canonical formatting, including single-word organizations. |

Supplying `NameRules()` disables learned name filtering. Caller-supplied recognizers retain their own policies and model settings. Select the spaCy device before loading the model; see [performance](../guides/performance.md).

## Language detection

Import `detect_language`, `LinguaDetector`, `LanguageDetection` and `LanguageDetectionError` from `gdelt_regkg.fields.language`.

`detect_language(text, detector=None)` returns `LanguageDetection(language, confidence, margin, detector)`. The language is a three-letter code; `margin` is the difference between the first two candidate scores. The default detector is permissive.

`LinguaDetector(strict=False, min_letters=40, min_confidence=0.8, min_margin=0.2)` loads Lingua. Thresholds apply when `strict=True`; text with no detectable language fails in either mode. A custom `LanguageDetector` implements `detect(text)` and returns `LanguageDetection`.

## Translation

Import `translate_text`, `TranslationResult` and `M2M100Translator` from `gdelt_regkg.fields.translation`.

```text
translate_text(
    text, *, language=None, translator, detect_missing_language=True,
    language_detector=None, language_check="script",
) -> TranslationResult
```

Missing language labels are detected when enabled. `language_check="script"` verifies script mismatches, `"all"` verifies every supplied label and `"none"` trusts supplied labels. Detection/verification can correct the source label. English bypasses the translator.

The result contains `original_text`, English `text`, normalized `source_language`, `engine` and optional `language_detection`; `translated` is true when the source is not English. A custom translator supplies an `engine` identity and `translate(text, source_language)` returning a nonempty English string.

```text
M2M100Translator.from_model(
    model="facebook/m2m100_418M", *, device="cpu", allow_download=False,
    revision=None, batch_size=4, num_beams=4,
)
```

The factory loads local weights by default. Explicitly permit downloading with `allow_download=True`, or supply a local snapshot directory as `model`. Select `device="cuda:0"` for PyTorch CUDA inference. `translate_many(texts, source_language)` returns strings in input order for one source language. Reuse a loaded backend sequentially. See [translation](../guides/translation.md) for record provenance and native GCAM.

## Persistent translation cache

Import `CachedTranslator` from `gdelt_regkg.translation_cache`.

`CachedTranslator(translator, path, timeout=60)` wraps a translator with a SQLite cache. It supports `translate`, `translate_many`, context management and `close()`. Keys include engine identity, normalized language and exact body. The wrapper trusts supplied language labels and does not perform detection.

Each instance owns one thread-affine connection. Independent instances may share a translation database; create them inside their workers. Closing discards uncommitted work and leaves the underlying translator open. See [cache and workspace ownership](../guides/performance.md#connection-and-workspace-ownership).

## Build and benchmark interfaces

Build requests use frozen `BuildOptions` from `gdelt_regkg.cli.inputs`; prediction requests use `PredictionOptions` from `gdelt_regkg.benchmark.corpus`; scoring uses `BenchmarkOptions` from `gdelt_regkg.benchmark`. `BenchmarkStore` lives in `gdelt_regkg.benchmark.storage` and accepts `path` plus `timeout=5`.

These interfaces support the same resource and workspace conventions as the commands. Use the [resource guide](../guides/resources.md), [benchmark guide](../guides/benchmarking.md) and [CLI reference](cli.md) for the maintained workflows.
