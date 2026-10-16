# Quickstart

Extract an individual field, then generate and write a complete GKG record. The library accepts article bodies as plain text; HTML retrieval and body extraction are the caller's responsibility.

## Prerequisites

Use Python 3.12 or newer. For all examples on this page, install the English NER backend and small model, then build the standard resources:

```shell
python -m pip install "gdelt-regkg[ner]"
python -m spacy download en_core_web_sm
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
```

Run Python from the directory containing `local-resources/`. Setup explicitly downloads external inputs; extraction uses the prepared files. See [installation](installation.md) for feature-specific dependencies and [resource preparation](guides/resources.md) for sources and profiles.

## Standalone fields

Counts use packaged authored rules and can also run with only the core package:

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

Import analyzers from their corresponding `gdelt_regkg.fields` modules. Analyze once and serialize standard or enhanced cells from the structured result. The [field reference](reference/fields/README.md) provides formats and examples for each column.

## Generate a GKG record

```python
from gdelt_regkg import RecordMetadata, Resources, generate_gkg, write_gkg
from gdelt_regkg.fields.ner import SpacyNER

text = "Flooding killed 12 people in London."
metadata = RecordMetadata(
    identifier="https://example.org/story",
    batch_time="20261001091500",
    sequence=1,
    sharing_image="",
    related_images=[],
    social_image_embeds=[],
    social_video_embeds=[],
    extras={},
)
resources = Resources(
    resources_dir="local-resources",
    recognizer=SpacyNER.from_model("en_core_web_sm"),
)
record = generate_gkg(text, metadata, resources, strict=True)
assert len(record.to_row()) == 27
assert record["V1COUNTS"] == record.counts
with open("articles.gkg.tsv", "w", encoding="utf-8", newline="") as stream:
    write_gkg([record], stream)
```

The file contains one headerless, tab-separated row with 27 columns and a final newline. Counts receive geography from the shared NER and location analysis. The record supports typed attributes and mapping access through native column names.

> [!NOTE]
> The empty media values and `extras={}` explicitly declare that these inputs are available and empty. Omitting them leaves those fields unavailable. `strict=True` rejects incomplete records; see [record availability and export](reference/python-api.md#availability-and-errors).

## Next steps

- [Generate records](guides/records.md) with publication metadata, overrides or precomputed NER.
- [Select resources](guides/resources.md#resource-selection) or supply custom dictionaries.
- [Translate non-English articles](guides/translation.md) before extraction and preserve the analyzed body for enhanced offsets.
- [Review measured agreement](evaluation/results.md) before interpreting reconstructed fields as native GKG values.
