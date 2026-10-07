# Shared API usage

See the [gdelt-regkg README](../README.md) for row generation and installation. Field-specific behavior, research, and configuration live in the [field pages](README.md).

## Independent fields and pandas

Functions in `gdelt_regkg.fields` accept prepared field inputs and return encoded GKG cells. NLP functions take plain article body text; metadata formatters take supplied values or collections. They work without the row generator and can be mapped over a pandas column, for example `df["themes"] = df["text"].map(extract_themes)`. Install pandas separately and normalize missing values before calling field functions.

The caller prepares body text, title, authors, publication metadata, DOI or URL, and media URLs. The generator’s `extras=` argument accepts additional data without a dedicated GKG column, including custom annotations and processing results. Titles and authors are common examples, supplied as `extras={"PAGE_TITLE": title, "PAGE_AUTHORS": ";".join(authors)}`. The [extra XML example](fields/extras-xml.md#example) includes both common metadata and application-defined elements.

`generate_gkg` accepts `sharing_image`, `related_images`, `social_image_embeds`, and `social_video_embeds` directly. These arguments require absolute media URLs; relevance selection, provider normalization, and resolving relative URLs belong to the caller.

`batch_time` supplies `V2.1DATE` and the record-ID timestamp, shared across a batch. Optional `published_at` adds the available publication time to `PAGE_PRECISEPUBTIMESTAMP` in extra XML; it never changes the batch date. A supplied extras timestamp takes precedence. Include the available timestamp regardless of its precision and omit it when no timestamp is known.

Use `analyze_counts` or `analyze_themes` once when both legacy and enhanced output are needed. Their results support `to_gkg()` and `to_gkg(enhanced=True)`; the pipeline already shares this analysis.

For [persons](fields/persons.md), [organizations](fields/organizations.md), [locations](fields/locations.md) and [all names](fields/all-names.md), use `analyze_entities(text, recognizer=recognizer)`. Pass the recognizer or its `NERResult` through `ner=` to the generator. It shares recognition across these columns and resolves locations with the locally prepared gazetteer; unresolved places remain diagnostics outside geographic cells.

Access `result.persons`, `result.organizations` and `result.locations` for recognized spans before GKG formatting. The [shared NER and location example](fields/locations.md#shared-ner-and-geographic-resolution) shows all three, geographic resolution and offsets; the [unresolved-place example](fields/locations.md#unresolved-mentions) explains why a recognized place may have no geographic cell.

## Dates and offsets

GKG has one body-date field, [`V2.1ENHANCEDDATES`](fields/enhanced-dates.md), which includes each mention's character offset. Date mentions already had offsets in GKG 2.0; GKG 2.1 added month-and-day references without a year. There is no legacy `V1DATES` column. [`V2.1DATE`](fields/date.md) holds the batch timestamp, and `PAGE_PRECISEPUBTIMESTAMP` in extras holds a supplied publication timestamp.

```python
from gdelt_regkg import analyze_dates

dates = analyze_dates("On June 5, 2025, officials announced the decision.")
cell = dates.to_gkg()  # 3#6#5#2025#3
mention = dates.mentions[0]
calendar_date = (mention.year, mention.month, mention.day)  # (2025, 6, 5)
```

The structured result gives calendar components separately from offsets. Missing components remain zero; the extractor does not infer them from publication metadata. Use `numeric_order="mdy"` or `"dmy"` for ambiguous slash dates in `analyze_dates` and `analyze_amounts`. The generator's `numeric_date_order=` applies the convention to both fields; the default skips ambiguous slash dates.

## Resource and model arguments

See [Installation and setup](installation.md) for installation, source downloads and model choices. Select the resource root explicitly; environment variables do not configure extraction.

```python
from gdelt_regkg import SpacyNER, default_extraction_config, generate_gkg

resources_dir = "local-resources"
ner = SpacyNER.from_model("en_core_web_lg", resources_dir=resources_dir)
config = default_extraction_config(resources_dir=resources_dir)
# Pass resources_dir=resources_dir and ner=ner to generate_gkg.
```

`generate_gkg(..., resources_dir=path)` selects tone, theme, count, geographic and GCAM defaults from that directory. `SpacyNER.from_model(..., resources_dir=path)` selects name rules when its default name policy uses them. A supplied recognizer keeps its own model and name policy. Explicit lexicon/rule/gazetteer objects and encoded field overrides retain precedence.

The default root is `local-resources/` relative to the working directory. Every `default_*` resource loader accepts `resources_dir=`; standalone analyzers accept the loaded objects through their existing `lexicon=`, `rules=` or `gazetteer=` arguments. CLI commands use `--resources-dir` and retain per-file overrides. No resource selection is process-global. Profiles are cached by resolved path; reload custom objects or restart after editing a cached file in place.

## Name policies

`SpacyNER.from_model` defaults to `name_policy="gdelt-full-names"`. GKG names
are lowercased, leading articles and terminal possessives are removed, and
periods in initials become spaces. Single-word person and organization names
are omitted from the cells. This improves measured native agreement but also
omits genuine names such as `Microsoft` and `CNN`. Original `EntityMention`
text and offsets remain unchanged and available in the result.

Use `name_policy="gdelt"` to keep single-word organizations while retaining
canonical formatting and full person names, or `name_policy="surface"` to
serialize all recognized names with source spelling and case. A directly
constructed `SpacyNER(nlp)` and supplied `NERResult` default to `surface`.
The same policy applies to legacy and enhanced cells; enhanced offsets still
anchor the original recognized span. Policies do not resolve identities. The default `gdelt-full-names` factory also applies bundled name rules v1: it removes common leading person titles and filters organization cell names with fixed coefficients learned only from development articles. This trades organization recall for precision against native GKG. Recognized mentions remain available even when their cell name is omitted.

Load the large model with `SpacyNER.from_model("en_core_web_lg")`. For batched processing, `recognizer.analyze_many(texts, batch_size=32)` yields one `NERResult` per body. Iterate over the results or collect them with `list(...)`, then pass each result through `ner=` with its unchanged body text.

To keep canonical formatting without the learned filter, pass `name_rules=NameRules()` after importing `NameRules` from `gdelt_regkg`. Load another profile with `NameRules.from_json(path)` and pass it through the same argument. The `surface` and `gdelt` factories do not load the bundled profile automatically. The large-model comparison is in [the seasonal benchmark](../CHANGELOG.md#seasonal-benchmark).

Locations and all names share the same recognition pass. The tagger remains enabled to recover proper-noun names outside entity spans; dependency parsing and lemmatization are disabled. Use `result.all_names` or `analyze_names(text, ner=result)` for broad names. `analyze_locations(text, ner=result)` resolves geography and exposes unresolved-name diagnostics.

The generator accepts `gazetteer=Gazetteer.from_json(path)` and `gcam_lexicon=GCAMLexicon.from_json(path)` for additional resources. GCAM supports 809 of 2,888 dimensions (28.01%) using locally compiled English dictionaries from General Inquirer, WordNet, theme rules and VADER; optional Roget and Lexicoder imports raise coverage to 1,855 of 2,888 dimensions (64.23%). Both loaders accept plain JSON and gzip-compressed profiles. See [implemented and missing measures](fields/gcam.md).

## Language detection and translation

The text extractors use English bodies. For other languages, follow the [full pipeline example](installation.md#complete-pipeline-example) to detect language locally, translate when needed, retain the analyzed body and extract all fields with the large NER model and full GCAM profile.

Alternatively, pass a loaded translator through `translator=` to `generate_gkg`, with `input_language=` when known. Missing labels are detected locally; `language_check="all"` also checks supplied labels, including languages sharing the same alphabet. Translation runs before text extraction and supplies provenance automatically. See [translation options and caching](fields/translation-info.md#local-translation).

Enhanced offsets refer to the English body actually analyzed. For precomputed NER results or count locations, translate separately first and compute spans on `result.text`; automatic translation rejects those precomputed inputs when it changes the body. Encoded field overrides must also refer to the analyzed body.

## Custom resources

After [resource setup](installation.md), copy the selected local theme profile and authored count rules for editing:

```python
from gdelt_regkg.utils import packaged_resource_path, resource_path
import json
from pathlib import Path

resources_dir = Path("local-resources")
for name in ("counts.v3.json", "themes.v3.json"):
    data = json.loads(resource_path("lexicons", name, resources_dir=resources_dir).read_text(encoding="utf-8"))
    schema_name = Path(data["$schema"]).name
    data["$schema"] = schema_name
    with Path(schema_name).open("x", encoding="utf-8") as stream:
        stream.write(packaged_resource_path("schemas", schema_name).read_text(encoding="utf-8"))
    with Path(name).open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(data, indent=2) + "\n")
```

Run the copy example once in your chosen resource directory; it creates files in the current directory and refuses to overwrite existing files. This copies each JSON Schema beside its input and updates the `$schema` editor link. The `schema` property without a dollar sign is the library's versioned format identifier, not a file path. Schemas use [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-core); Python loaders retain semantic validation, so the library needs no JSON Schema runtime dependency.

Edit the copies using the [count](fields/counts.md#rules) and [theme](fields/themes.md#rules) schemas. Then load a configuration once and pass it as `config=` to `generate_gkg`:

```python
from gdelt_regkg import ExtractionConfig

config = ExtractionConfig.from_rule_inputs("counts.v3.json", "themes.v3.json")
```

Standalone extractors accept `rules=config.count_rules` or `lexicon=config.theme_lexicon`. Reload custom files after edits; defaults are cached for the process lifetime. The older combined JSON format remains accepted by `ExtractionConfig.from_json`, but is not required.

## Incomplete rows and overrides

`generate_gkg` returns all 27 fields. An empty string means no accepted match; `None` means missing supplied metadata or a model-dependent field without `ner`. It emits `IncompleteGKGWarning` for these unavailable values. Use `strict=True` to reject incomplete records. With `ner` and explicitly supplied media/extras metadata, every column can now be generated.

`write_gkg` rejects incomplete records unless `allow_incomplete=True`, which exports `None` as blank cells. Keep the dictionaries if that distinction matters. Output is headerless TSV; embedded tabs and newlines are rejected.

To use another extractor, pass encoded results as `field_values={"V1PERSONS": "Jane Doe", "V2ENHANCEDPERSONS": "Jane Doe,0"}` to the generator. Overrides skip the corresponding built-in functions; legacy and enhanced partners must be supplied independently. Internal subfield syntax is not validated. Supply metadata through the generator's explicit arguments.

`parse_counts_cell`, `parse_themes_cell`, `serialize_counts_cell`, and `serialize_themes_cell` preserve order and duplicates when handling existing count/theme cells and they do not run extraction.
