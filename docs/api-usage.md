# API usage

## Generate a GKG record

```python
from gdelt_regkg import RecordMetadata, Resources, generate_gkg, write_gkg
from gdelt_regkg.fields.ner import SpacyNER

metadata = RecordMetadata(
    identifier="https://example.org/story",
    batch_time="20261001091500",
    sequence=1,
    published_at="20261001090023",
    sharing_image="",
    related_images=[],
    social_image_embeds=[],
    social_video_embeds=[],
    extras={},
)
resources = Resources(resources_dir="local-resources", recognizer=SpacyNER.from_model())
record = generate_gkg("Flooding killed 12 people in London.", metadata, resources, strict=True)
print(record.counts)
print(record["V1COUNTS"])
with open("articles.gkg.tsv", "w", encoding="utf-8", newline="") as stream:
    write_gkg([record], stream)
```

```text
CRISISLEX_T03_DEAD#12#people#4#London, London, City Of, United Kingdom#UK#UKH9#51.5#-0.116667#-2601889;KILL#12#people#4#London, London, City Of, United Kingdom#UK#UKH9#51.5#-0.116667#-2601889;
CRISISLEX_T03_DEAD#12#people#4#London, London, City Of, United Kingdom#UK#UKH9#51.5#-0.116667#-2601889;KILL#12#people#4#London, London, City Of, United Kingdom#UK#UKH9#51.5#-0.116667#-2601889;
```

File `articles.gkg.tsv`:

```text
20261001091500-1	20261001091500	1	example.org	https://example.org/story	CRISISLEX_T03_DEAD#12#people#4#London, London, City Of, United Kingdom#UK#UKH9#51.5#-0.116667#-2601889;KILL#12#people#4#London, London, City Of, United Kingdom#UK#UKH9#51.5#-0.116667#-2601889;	CRISISLEX_T03_DEAD#12#people#4#London, London, City Of, United Kingdom#UK#UKH9#51.5#-0.116667#-2601889#16;KILL#12#people#4#London, London, City Of, United Kingdom#UK#UKH9#51.5#-0.116667#-2601889#16;	CRISISLEX_C06_WATER_SANITATION;NATURAL_DISASTER_FLOODING;CRISISLEX_T03_DEAD;KILL;	CRISISLEX_C06_WATER_SANITATION,0;NATURAL_DISASTER_FLOODING,0;CRISISLEX_T03_DEAD,9;KILL,9;	4#London, London, City Of, United Kingdom#UK#UKH9#51.5#-0.116667#-2601889	4#London, London, City Of, United Kingdom#UK#UKH9#40110#51.5#-0.116667#-2601889#29					-16.6666666666667,0,16.6666666666667,16.6666666666667,16.6666666666667,0,6		wc:6,c2.9:1,c2.23:1,c2.34:1,c2.45:1,c2.76:3,c2.77:1,c2.87:1,c2.95:1,c2.110:1,c2.119:2,c2.129:1,c2.133:1,c2.143:1,c2.147:1,c2.185:1,c2.193:1,c3.1:1,c9.33:1,c9.76:1,c9.107:1,c9.195:1,c9.197:1,c9.292:1,c9.358:1,c9.372:1,c9.383:1,c9.667:1,c9.669:1,c9.762:1,c9.1040:1,c16.33:1,c16.57:5,c16.68:1,c16.70:3,c16.71:1,c16.89:1,c16.92:1,c16.94:1,c16.95:1,c16.101:1,c16.110:1,c16.115:1,c16.121:1,c16.125:1,c16.145:1,c16.156:1,c16.162:1,c17.1:2,c17.4:1,c17.5:2,c17.6:1,c17.7:1,c17.12:1,c17.15:1,c17.16:2,c17.19:1,c17.20:1,c17.24:3,c17.28:1,c17.31:3,c17.35:1,c17.36:2,c17.38:1,c17.40:1,c17.41:1,c17.42:1,c17.43:2,c18.1:1,c26.1:1,v26.1:-3.5						London,29	12,people,16		<PAGE_PRECISEPUBTIMESTAMP>20261001090023</PAGE_PRECISEPUBTIMESTAMP>
```

Record IDs and the batch-date column use `batch_time`; optional `published_at` supplies precise publication metadata in extras. A supplied `PAGE_PRECISEPUBTIMESTAMP` takes precedence. Sequence uniqueness is caller-managed.

The frozen record has 27 typed fields. `to_mapping()` returns ordered wire column names; `to_row(allow_incomplete=False)` returns ordered string cells. `serialize_gkg` and `write_gkg` also accept mappings and validate their exact keys and cell types. Output is headerless TSV, including its final newline.

`None` means unavailable; an empty string means an available empty result. Strict generation raises `IncompleteGKGError`. Otherwise it emits `IncompleteGKGWarning`. Incomplete export requires `allow_incomplete=True`, which converts unavailable cells to empty strings. Extractor failures propagate.

## Standalone fields

```python
from gdelt_regkg.fields.counts import analyze_counts
from gdelt_regkg.fields.dates import analyze_dates

result = analyze_counts("12 people were killed.")
print(result.to_gkg())
print(result.to_gkg(enhanced=True))
print(analyze_dates("02/03/2025", numeric_order="dmy").to_gkg())
```

```text
CRISISLEX_T03_DEAD#12#people#0######;KILL#12#people#0######;
CRISISLEX_T03_DEAD#12#people#0#######0;KILL#12#people#0#######0;
3#3#2#2025#0
```

Each analyzer lives in its owning `gdelt_regkg.fields` module and returns a structured result with diagnostics/provenance where applicable. Metadata formatters live in `gdelt_regkg.fields.metadata`. The `extract_*` convenience wrappers have been removed.

## Resource selection

```python
from gdelt_regkg import Resources
from gdelt_regkg.fields.rule_inputs import load_count_rules, load_theme_lexicon

custom = Resources(
    resources_dir="local-resources",
    count_rules=load_count_rules("counts.json"),
    theme_lexicon=load_theme_lexicon("themes.json"),
)
```

Explicit objects override directory defaults. Resources load only when required. The default root is `local-resources/` relative to the working directory. External dictionaries must be prepared locally; extraction does not fetch resources. Authored counts and name rules have packaged fallback. Existing schema IDs and historical build recipes remain supported.

Compiled default profiles are cached by resolved path. Reload explicit objects or restart after editing a cached profile in place. Caller-supplied recognizers retain their own name rules and model settings.

## Name policies

`SpacyNER.from_model` defaults to `name_policy="gdelt-full-names"`, using the selected name rules to normalize names, remove configured person titles and filter organization cells. Use `name_policy="surface"` to retain observed spelling, or `"gdelt"` for canonical formatting with single-word organizations. Supplying `NameRules()` disables learned name filtering. Original mention spans remain available on structured results.

## Overrides and precomputed NER

```python
from gdelt_regkg import generate_gkg
from gdelt_regkg.fields.ner import analyze_entities

text = "Flooding killed 12 people in London."

entities = analyze_entities(text, recognizer=resources.recognizer)
record = generate_gkg(
    text,
    metadata,
    resources,
    ner_result=entities,
    overrides={"V1THEMES": "CUSTOM;"},
)
print(record.themes)
```

```text
CUSTOM;
```

`ner_result` takes precedence over the recognizer and must describe the exact analyzed body. Encoded overrides replace individual output cells. They do not disable analysis needed by other fields: counts can still resolve geography when both location cells are overridden. Explicit nonempty `count_locations=` takes precedence over derived geography. `numeric_date_order="mdy"` or `"dmy"` applies consistently to dates and amounts.

## Language detection and translation

Install the [`lang` extra](installation.md#non-english-articles) to detect a language without loading a translation model:

```python
from gdelt_regkg.fields.language import detect_language

body = (
    "El museo abrió una nueva exposición sobre instrumentos musicales. "
    "Los visitantes pueden escuchar grabaciones y participar en talleres "
    "para aprender cómo se producen los diferentes sonidos."
)
detection = detect_language(body)
print(detection.language)  # (ISO 639-3)
print(detection.confidence)
print(detection.margin)
```

```text
spa
1.0
1.0
```

By default, detection returns the best candidate even for short or uncertain text. Inspect `confidence` and `margin` to decide whether to accept it, request more text, or supply a language yourself. To reject weak evidence automatically, opt into strict checks:

```python
from gdelt_regkg.fields.language import LinguaDetector, detect_language

strict_detector = LinguaDetector(
    strict=True, min_letters=40, min_confidence=0.8, min_margin=0.2
)
detection = detect_language(body, detector=strict_detector)
```

Strict mode raises `LanguageDetectionError` when a threshold is not met. An input with no detectable language, such as empty or numeric-only text, still raises in either mode. See [detection details](fields/translation-info.md#language-detection).

After [installing PyTorch separately and the `translate,lang` extras](installation.md#non-english-articles), translate an article whose language is unknown by omitting `language=`:

```python
from gdelt_regkg.fields.translation import M2M100Translator, translate_text

backend = M2M100Translator.from_model(device="cpu", allow_download=False)
result = translate_text(body, translator=backend)
print(result.source_language)
print(result.text)
```

```text
spa
The museum opened a new exhibition on musical instruments. Visitors can listen to recordings and participate in workshops to learn how the different sounds are produced.
```

This example uses previously downloaded M2M100 weights; use `allow_download=True` once to explicitly permit downloading them. English input passes through unchanged. Model wording can vary. When the source language is already known, supply it and generate a record from the translated body:

```python
from gdelt_regkg import RecordMetadata, generate_gkg
from gdelt_regkg.fields.translation import M2M100Translator, translate_text

source_body = "Des inondations ont tué 12 personnes à Londres."

backend = M2M100Translator.from_model(device="cpu", allow_download=False)
result = translate_text(source_body, language="fra", translator=backend)
translated_metadata = RecordMetadata.from_translation(result, metadata)
record = generate_gkg(result.text, translated_metadata, resources)
print(record.themes)
```

```text
CRISISLEX_T01_CAUTION_ADVICE;NATURAL_DISASTER;NATURAL_DISASTER_FLOODS;CRISISLEX_T03_DEAD;KILL
```

The generator receives prepared English text. `from_translation` copies language/engine provenance into a new metadata object and rejects conflicts. English passthrough adds no translation provenance; translated records retain `T` in their IDs. Metadata titles, media and identifiers are not translated.

**Enhanced offsets index `result.text`, not `result.original_text`.** Preserve the analyzed body with the generated rows and compute NER/count-location spans after translation.

`translate_text` detects missing language labels with the `lang` extra. A supplied label uses `language_check="script"` by default; `"all"` verifies all labels, and `"none"` trusts the supplied label. Custom translators expose an engine identity and `translate(text, source_language)`. See [translation details](fields/translation-info.md).

## Batching and persistent caching

```python
from gdelt_regkg.translation_cache import CachedTranslator

with CachedTranslator(backend, "translations.sqlite", timeout=60) as cached:
    translated = translate_text(source_body, language="fra", translator=cached)
    bodies = cached.translate_many([source_body, another_body], "fra")
```

Scalar and batch cache calls use identical language normalization, English passthrough and output validation. Keys include a format namespace, engine identity, normalized language and exact input body. The cache trusts its supplied language; use `translate_text` for verification before caching.

`SpacyNER.analyze_many(texts, batch_size=32)` yields one result per body. `M2M100Translator.translate_many(texts, source_language)` batches same-language inputs; internal chunking preserves long articles.

File-backed caches use WAL and configurable SQLite timeouts. Each instance owns one thread-affine connection. Create independent instances inside each worker/thread/process; do not share instances across threads. Independent translation caches may share a database. Use a context manager or `close()`; closure is idempotent, discards uncommitted work and does not close the wrapped translator. Successful cache operations commit explicitly.

The benchmark uses `OUTPUT/benchmark.sqlite3` workspace and exclusive workspace lock; concurrent benchmark writers cannot share a workspace. `BenchmarkStore(path, timeout=5)` supports context management and `close()` with the same ownership rules. In-memory databases use SQLite's memory journal.

## GPU inference

For translation, [install PyTorch separately](installation.md#non-english-articles) and select `device="cpu"` or `device="cuda:0"` when loading the translator. For spaCy NER, [install CuPy and select the GPU before loading the model](installation.md#gpu-inference), or select `--device` in the benchmark CLI. CuPy is not required for translation, and the standard spaCy English model does not require PyTorch.

## Complete pipeline example

```python
from gdelt_regkg import RecordMetadata, generate_gkg, write_gkg
from gdelt_regkg.fields.translation import translate_text

rows = []
for sequence, article in enumerate(articles, 1):
    meta = RecordMetadata(
        article["url"],
        article["batch_time"],
        sequence,
        sharing_image="",
        related_images=[],
        social_image_embeds=[],
        social_video_embeds=[],
        extras={},
    )
    translated = translate_text(
        article["text"], language=article.get("language"), translator=backend
    )
    rows.append(
        generate_gkg(
            translated.text,
            RecordMetadata.from_translation(translated, meta),
            resources,
            strict=True,
        )
    )
with open("articles.gkg.tsv", "w", encoding="utf-8", newline="") as stream:
    write_gkg(rows, stream)
```

Missing article language labels are detected automatically; supplied labels follow the verification policy above. The caller owns corpus iteration and saving translated bodies. For benchmark/build function calls, use frozen `PredictionOptions` and `BuildOptions`; scoring settings are in `BenchmarkOptions`.
