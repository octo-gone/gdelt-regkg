# Generate and export records

Prepare article text and caller-supplied metadata, then combine field results into a GKG record. See [Quickstart](../quickstart.md) for a first run.

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

The file contains one headerless TSV record. The [field index](../reference/fields/README.md) lists all 27 columns in output order.

Record IDs and the batch-date column use `batch_time`; optional `published_at` supplies precise publication metadata in extras. A supplied `PAGE_PRECISEPUBTIMESTAMP` takes precedence. Sequence uniqueness is caller-managed.

The frozen record has 27 typed fields. `to_mapping()` returns ordered wire column names; `to_row(allow_incomplete=False)` returns ordered string cells. `serialize_gkg` and `write_gkg` also accept mappings and validate their exact keys and cell types. Output is headerless TSV, including its final newline.

`None` means unavailable; an empty string means an available empty result. Strict generation raises `IncompleteGKGError`. Otherwise it emits `IncompleteGKGWarning`. Extractor failures propagate.

> [!CAUTION]
> Exporting with `allow_incomplete=True` converts unavailable cells to empty strings. The TSV then loses the distinction between an unavailable field and an available field with no matches. Resolve missing inputs first when that distinction matters to your analysis.

## Overrides and precomputed NER

The following example reuses `metadata` and `resources` from the record-generation example above.

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

Use `gcam_disabled_dictionaries=("roget", "wordnet-affect", 26)` to omit selected GCAM dictionaries before matching. The standalone `analyze_gcam` option is `disabled_dictionaries=...`. Collections accept canonical names, integer IDs and numeric strings; `wc` is preserved. See [GCAM dictionary selection](../reference/fields/gcam.md#select-dictionaries).

For standalone field extraction, see [quickstart](../quickstart.md#standalone-fields).
