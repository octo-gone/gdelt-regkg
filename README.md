# gdelt-regkg

[![CI](https://github.com/octo-gone/gdelt-regkg/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/octo-gone/gdelt-regkg/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gdelt-regkg)](https://pypi.org/project/gdelt-regkg/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://pypi.org/project/gdelt-regkg/)
[![License](https://img.shields.io/github/license/octo-gone/gdelt-regkg)](https://github.com/octo-gone/gdelt-regkg/blob/master/LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23314745-blue)](https://doi.org/10.5281/zenodo.23314745)

Package for reconstructing GDELT GKG files from article text and metadata.

`gdelt-regkg` converts prepared article bodies and supplied metadata into GKG records. It can be used for reconstructing gaps in GKG coverage, processing your own news datasets, or extract individual fields for analysis. To make it work you just need article text and some metadata, while the library extracts and formats the fields automatically. You can generate full GKG entry or extract data only for specific fields.

The row structure, metadata formatting and field encodings are documented in [GDELT Global Knowledge Graph Codebook](https://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf). Extraction from text **approximates** GDELT's processing, so themes, counts, entities, tone and other inferred values **can differ** from native GKG results.

See the [field documentation and measured agreement](docs/README.md), [resource and benchmark tools](docs/cli/README.md), and [changelog](CHANGELOG.md).

## Installation

Requires Python 3.12 or newer. Install the library and its English model, then prepare the extraction dictionaries:

```shell
python -m pip install "gdelt-regkg[ner]"
python -m spacy download en_core_web_sm
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
```

[Installation](docs/installation.md) covers package dependencies and model setup. See [API usage](docs/api-usage.md) for Python examples and [Build resources](docs/cli/build.md) for dictionary profiles and source files.

> [!TIP]
> You can improve extraction quality and expand GCAM coverage, install the [large English model](docs/installation.md#english-models) and build the [full GCAM profile](docs/cli/build.md#gcam-profiles-and-expansion). The [complete pipeline example](docs/api-usage.md#complete-pipeline-example) also handles non-English bodies. Results vary by field; see [measured agreement](docs/README.md#agreement-with-gdelt).

## Usage

### Extract individual fields

Import structured analyzers from their field modules. Serialize the result when a GKG cell is needed:

```python
from gdelt_regkg.fields.counts import analyze_counts
from gdelt_regkg.fields.themes import analyze_themes
from gdelt_regkg.fields.tone import analyze_tone

text = "Flooding killed 12 people."
counts = analyze_counts(text)
print(counts.to_gkg())
print(counts.to_gkg(enhanced=True))
print(analyze_themes(text).to_gkg())
print(analyze_tone(text).to_gkg())
```

```text
CRISISLEX_T03_DEAD#12#people#0######;KILL#12#people#0######;
CRISISLEX_T03_DEAD#12#people#0#######16;KILL#12#people#0#######16;
CRISISLEX_C06_WATER_SANITATION;NATURAL_DISASTER_FLOODING;CRISISLEX_T03_DEAD;KILL;
-25,0,25,25,25,0,4
```

Tone, themes, geographic references and GCAM need prepared local profiles. Counts and name rules are included. Default profiles are cached by resolved path; reuse explicit objects or reload them after edits. For pandas, use `df["themes"] = df["text"].map(lambda text: analyze_themes(text).to_gkg())`; install pandas separately and normalize missing values.

### Generate a GKG record

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
resources = Resources(resources_dir="local-resources", recognizer=SpacyNER.from_model())
record = generate_gkg(text, metadata, resources, strict=True)
with open("articles.gkg.tsv", "w", encoding="utf-8", newline="") as stream:
    write_gkg([record], stream)
```

The frozen `GKGRecord` has 27 typed attributes, native column-name mapping access, `to_mapping()` and `to_row()`. An empty cell means no matches; `None` means unavailable metadata or model-dependent work. `strict=True` raises `IncompleteGKGError`; otherwise unavailable fields produce `IncompleteGKGWarning`. Export them explicitly with `allow_incomplete=True`.

Translate non-English bodies first and use `RecordMetadata.from_translation(result, metadata)`. Enhanced offsets refer to `result.text`. See [API usage](docs/api-usage.md) for translation, batching, caching, overrides and resource composition, and the [Unreleased migration guide](CHANGELOG.md#unreleased) for breaking API changes.

## Supported fields

All 27 GKG wire columns are supported. Text-derived fields approximate GDELT processing; metadata and media fields format values supplied by the caller. Enhanced fields add offsets into the analyzed English body. Follow the field links for formats, examples and limitations.

| GKG column | How it is produced | Setup |
| --- | --- | --- |
| [GKGRECORDID](docs/fields/record-id.md) | Batch timestamp and sequence; `T` marks translated records | Supplied `RecordMetadata` |
| [V2.1DATE](docs/fields/date.md) | Batch timestamp; publication time is kept separately in extra XML | Supplied metadata |
| [V2SOURCECOLLECTIONIDENTIFIER](docs/fields/source-collection.md) | Validated source collection identifier | Supplied metadata |
| [V2SOURCECOMMONNAME](docs/fields/source-name.md) | Supplied source name or hostname derived from the document URL | Supplied metadata |
| [V2DOCUMENTIDENTIFIER](docs/fields/document-identifier.md) | Supplied document URL or identifier | Supplied metadata |
| [V1COUNTS](docs/fields/counts.md) | Authored English number/event rules with optional resolved geography | Rules included; [NER and geography](docs/installation.md#basic-english-setup) for place enrichment |
| [V2.1COUNTS](docs/fields/enhanced-counts.md) | Count matches with character offsets | Same as counts |
| [V1THEMES](docs/fields/themes.md) | Phrase matching against theme dictionaries | [Build local resources](docs/cli/build.md) |
| [V2ENHANCEDTHEMES](docs/fields/enhanced-themes.md) | Theme matches with offsets | Same as themes |
| [V1LOCATIONS](docs/fields/locations.md) | NER place mentions resolved against an offline gazetteer | [spaCy model and local resources](docs/installation.md#basic-english-setup) |
| [V2ENHANCEDLOCATIONS](docs/fields/enhanced-locations.md) | Resolved place occurrences with offsets and administrative details | Same as locations |
| [V1PERSONS](docs/fields/persons.md) | NER person mentions with name normalization and filtering | [NER extra and English model](docs/installation.md#english-models) |
| [V2ENHANCEDPERSONS](docs/fields/enhanced-persons.md) | Person mentions with offsets | Same as persons |
| [V1ORGANIZATIONS](docs/fields/organizations.md) | NER organization mentions with authored name filtering | [NER extra and English model](docs/installation.md#english-models) |
| [V2ENHANCEDORGANIZATIONS](docs/fields/enhanced-organizations.md) | Organization mentions with offsets | Same as organizations |
| [V1.5TONE](docs/fields/tone.md) | Dictionary-based tone, polarity, activity, self-reference and word counts | [Build tone resources](docs/cli/build.md) |
| [V2.1ENHANCEDDATES](docs/fields/enhanced-dates.md) | English calendar/date patterns with offsets | Core only |
| [V2GCAM](docs/fields/gcam.md) | Matches across configured affect dictionaries | [Build GCAM resources](docs/cli/build.md#gcam-profiles-and-expansion) |
| [V2.1SHARINGIMAGE](docs/fields/sharing-image.md) | Formats the supplied sharing-image URL | Supplied metadata |
| [V2.1RELATEDIMAGES](docs/fields/related-images.md) | Formats supplied related-image URLs | Supplied metadata |
| [V2.1SOCIALIMAGEEMBEDS](docs/fields/social-image-embeds.md) | Formats supplied social-image embed URLs | Supplied metadata |
| [V2.1SOCIALVIDEOEMBEDS](docs/fields/social-video-embeds.md) | Formats supplied social-video embed URLs | Supplied metadata |
| [V2.1QUOTATIONS](docs/fields/quotations.md) | Quoted-span detection with offsets and lengths | Core only |
| [V2.1ALLNAMES](docs/fields/all-names.md) | Broader NER name labels with authored filtering and offsets | [NER extra and English model](docs/installation.md#english-models) |
| [V2.1AMOUNTS](docs/fields/amounts.md) | Number, currency and unit patterns with offsets | Core only |
| [V2.1TRANSLATIONINFO](docs/fields/translation-info.md) | Formats language/engine provenance from explicit translation or metadata | [Detection and translation setup](docs/installation.md#non-english-articles) for automatic provenance |
| [V2EXTRASXML](docs/fields/extras-xml.md) | Escapes and serializes supplied extra metadata as XML | Supplied metadata |

Language detection can also be used independently of GKG generation. See [detect and translate an unknown language](docs/api-usage.md#language-detection-and-translation) and [CUDA/CuPy setup](docs/installation.md#gpu-inference).

## Contributing

Use the GitHub issue forms to report bugs, extraction differences or feature requests. [Contributing](CONTRIBUTING.md) describes local checks, pull requests and evaluation on data separate from rule development. Please follow the [code of conduct](CODE_OF_CONDUCT.md). Report vulnerabilities privately as described in the [security policy](SECURITY.md).

## Benchmark

Use `gdelt-regkg-cli benchmark` to compare native and reconstructed GKG fields
and write Markdown and CSV metric tables. The [benchmark guide](docs/cli/benchmark.md)
covers installation, input files and directories, field selection and metrics.

## Disclaimer

This is an independent implementation, unaffiliated with and not endorsed by the GDELT Project. It produces approximate GKG fields, not guaranteed copies of GDELT's outputs. Results depend on article text, translation, models and dictionaries; validate them for your intended analysis. Differences from native GKG can also reflect different input bodies.

The code and original rules use the [MIT license](LICENSE) and are provided without warranty. MIT does not grant rights to external dictionaries, models, article bodies or generated profiles derived from them; their [source terms](docs/cli/build.md#third-party-terms) still apply.
