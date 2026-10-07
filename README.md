# gdelt-regkg

Package for reconstructing GDELT GKG files from article text and metadata.

`gdelt-regkg` converts prepared article bodies and supplied metadata into GKG records. It can be used for reconstructing gaps in GKG coverage, processing your own news datasets, or extract individual fields for analysis. To make it work you just need article text and some metadata, while the library extracts and formats the fields automatically. You can generate full GKG entry or extract data only for specific fields.

The row structure, metadata formatting and field encodings are documented in [GDELT Global Knowledge Graph Codebook](https://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf). Extraction from text **approximates** GDELT's processing, so themes, counts, entities, tone and other inferred values **can differ** from native GKG results.

See the [field documentation and measured agreement](docs/README.md), [resource and benchmark tools](scripts/README.md), and [changelog](CHANGELOG.md).

## Installation

Requires Python 3.12 or newer. Install the library and its English model, then prepare the extraction dictionaries:

```shell
python -m pip install gdelt-regkg
python -m spacy download en_core_web_sm
gdelt-regkg-build-resources --sources-dir downloads/resources --download-sources --output local-resources
```

[Installation and setup](docs/installation.md) explains what is downloaded, how to run your first extraction, and how to add larger models, GCAM dictionaries or translation.

> [!NOTE]
> You can improve extraction quality and expand GCAM coverage by following the [best supported setup](docs/installation.md#best-supported-setup). It explains how to select the larger English NER model, add optional GCAM dictionaries, and check language and translate non-English bodies before extraction. Results vary by field; see [measured agreement](docs/README.md#agreement-with-gdelt).

## Usage

### Extract individual fields

Each field has a standalone function, so you do not need to generate a full GKG row.

```python
from gdelt_regkg.fields import extract_counts, extract_themes, extract_tone

text = "Flooding killed 12 people and displaced 300 residents."

counts = extract_counts(text)
# CRISISLEX_T03_DEAD#12#people#0######;KILL#12#people#0######;AFFECT#300#residents#0######;CRISISLEX_CRISISLEXREC#300#residents#0######;CRISISLEX_T09_DISPLACEDRELOCATEDEVACUATED#300#residents#0######;DISPLACED#300#residents#0######;
themes = extract_themes(text)
# CRISISLEX_C06_WATER_SANITATION;NATURAL_DISASTER_FLOODING;CRISISLEX_T03_DEAD;KILL;AFFECT;CRISISLEX_CRISISLEXREC;CRISISLEX_T09_DISPLACEDRELOCATEDEVACUATED;DISPLACED;MANMADE_DISASTER_IMPLIED;
tone = extract_tone(text)
# -12.5,0,12.5,12.5,12.5,0,8
```

Functions return GKG-formatted cell strings and work with pandas, for example `df["themes"] = df["text"].map(extract_themes)`. pandas package is optional and must be installed separately.

Tone, themes, geographic references and GCAM require locally prepared profiles. The default directory is `local-resources/`; select another with `resources_dir=` in Python or `--resources-dir` in the CLI. Explicit resource objects override directory defaults. Counts and name rules are available directly from the package.

### Generate and save a row

```python
from gdelt_regkg import SpacyNER, generate_gkg, write_gkg

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")  # Load once and reuse.

record = generate_gkg(
    "Volunteers rescued 12 people in Paris, France.",
    identifier="https://example.org/story",
    published_at="20261001090023",  # Known precise publication time, stored in extra XML.
    batch_time="20261001091500",
    sequence=1,
    ner=ner,
    resources_dir="local-resources",
    sharing_image="",
    related_images=[],
    social_image_embeds=[],
    social_video_embeds=[],
    extras={},
    strict=True,
)

with open("example.gkg.csv", "w", encoding="utf-8", newline="") as stream:
    write_gkg([record], stream)

for column in ("V1COUNTS", "V1LOCATIONS", "V2.1AMOUNTS"):
    print(f"{column}: {record[column]}")
```

```text
V1COUNTS: CRISISLEX_T08_MISSINGFOUNDTRAPPEDPEOPLE#12#people#4#Paris, France (General), France#FR#FR00#48.8667#2.33333#-1456928;
V1LOCATIONS: 4#Paris, France (General), France#FR#FR00#48.8667#2.33333#-1456928;1#France#FR#FR#46#2#FR
V2.1AMOUNTS: 12,people,19
```

These are three cells from the generated record. `example.gkg.csv` contains the complete 27-column GKG entry, including themes, tone, GCAM and enhanced fields. The generator resolves locations from NER and adds the nearest resolved location to each count.

The generator returns a dictionary of 27 fields. This example explicitly supplies a recognizer and empty media/extras metadata, so `strict=True` verifies a complete row. Missing supplied metadata or model-dependent fields without `ner` remain `None` and produce a warning. `allow_incomplete=True` exports those unavailable values as blank cells. Output is headerless and tab-delimited, even when the filename ends in `.csv` (GDELT specifics).

For non-English articles and the full GCAM profile, use the [complete pipeline example](docs/installation.md#complete-pipeline-example) in the setup guide.

## Field implementation map

Columns appear in output order. Model-dependent fields require an installed recognizer; missing supplied metadata remains `None`.

| Column | Standalone function | Status |
| --- | --- | --- |
| GKGRECORDID | `format_record_id` | Supplied metadata |
| V2.1DATE | `format_date` | Batch timestamp |
| V2SOURCECOLLECTIONIDENTIFIER | `format_source_collection` | Supplied metadata |
| V2SOURCECOMMONNAME | `source_common_name` | Explicit label or hostname |
| V2DOCUMENTIDENTIFIER | `document_identifier` | Supplied metadata |
| V1COUNTS | `extract_counts` | Experimental approximation |
| V2.1COUNTS | `extract_enhanced_counts` | Same counts with number offsets |
| V1THEMES | `extract_themes` | Rule-based approximation |
| V2ENHANCEDTHEMES | `extract_enhanced_themes` | Same theme mentions with phrase offsets |
| V1LOCATIONS | `extract_locations` | Offline reference gazetteer and NER approximation |
| V2ENHANCEDLOCATIONS | `extract_enhanced_locations` | Same resolved places with ADM2 and offsets |
| V1PERSONS | `extract_persons` | spaCy NER approximation |
| V2ENHANCEDPERSONS | `extract_enhanced_persons` | Same person mentions with offsets |
| V1ORGANIZATIONS | `extract_organizations` | spaCy NER approximation |
| V2ENHANCEDORGANIZATIONS | `extract_enhanced_organizations` | Same organization mentions with offsets |
| V1.5TONE | `extract_tone` | Benchmark-refined dictionary approximation |
| V2.1ENHANCEDDATES | `extract_enhanced_dates` | Explicit English dates with resolutions 1–4 |
| V2GCAM | `extract_gcam` | Dictionary category counts and weighted scores; coverage depends on local dictionaries |
| V2.1SHARINGIMAGE | `format_sharing_image` | Supplied image URL |
| V2.1RELATEDIMAGES | `format_related_images` | Supplied image URLs |
| V2.1SOCIALIMAGEEMBEDS | `format_social_image_embeds` | Supplied social-post URLs |
| V2.1SOCIALVIDEOEMBEDS | `format_social_video_embeds` | Supplied video URLs |
| V2.1QUOTATIONS | `extract_quotations` | Quoted spans and reporting-verb approximation |
| V2.1ALLNAMES | `extract_all_names` | Broad named entities and proper-noun spans |
| V2.1AMOUNTS | `extract_amounts` | Numeric/textual quantities with bounded objects |
| V2.1TRANSLATIONINFO | `format_translation_info` | Supplied metadata |
| V2EXTRASXML | `extract_extras_xml` | Custom extension data, including supplied metadata |

See the [field documentation](docs/README.md) for implementation status, research, and usage for each field.

## Contributing

Use the GitHub issue forms to report bugs, extraction differences or feature requests. [Contributing](CONTRIBUTING.md) describes local checks, pull requests and evaluation on data separate from rule development.

## Security

Report vulnerabilities through the repository's **Security → Report a vulnerability** form rather than a public issue. Include the affected version, a minimal reproduction and impact. Do not include credentials or article bodies you cannot share. If private reporting is unavailable, use a private contact listed on the maintainer's GitHub profile.

Security fixes target the latest release. Ordinary extraction disagreements and model errors belong in the issue forms.

## Disclaimer

This is an independent implementation, unaffiliated with and not endorsed by the GDELT Project. It produces approximate GKG fields, not guaranteed copies of GDELT's outputs. Results depend on article text, translation, models and dictionaries; validate them for your intended analysis. Differences from native GKG can also reflect different input bodies.

The code and original rules use the [MIT license](LICENSE) and are provided without warranty. MIT does not grant rights to external dictionaries, models, article bodies or generated profiles derived from them; their [source terms](docs/installation.md#third-party-terms) still apply.
