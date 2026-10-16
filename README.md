# gdelt-regkg

[![CI](https://github.com/octo-gone/gdelt-regkg/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/octo-gone/gdelt-regkg/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gdelt-regkg)](https://pypi.org/project/gdelt-regkg/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://pypi.org/project/gdelt-regkg/)
[![License](https://img.shields.io/github/license/octo-gone/gdelt-regkg)](https://github.com/octo-gone/gdelt-regkg/blob/master/LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23314745-blue)](https://doi.org/10.5281/zenodo.23314745)

Reconstruct GDELT GKG records from prepared article text and supplied metadata. Generate complete 27-column records or analyze individual fields from Python.

You can use `gdelt-regkg` to:

- Process your own news datasets into GKG-compatible records.
- Extract individual fields, such as themes, tone, entities or event counts, for analysis.
- Reconstruct gaps in GKG coverage from available article bodies and metadata.
- Analyze multilingual articles.
- Evaluate custom dictionaries and extraction profiles.
- Compare reconstructed fields with archived GKG output using the benchmark tools.

> [!NOTE]
> Text-derived values **approximate** GDELT's processing and **can differ** from native GKG output. Metadata and media fields format caller-supplied values. See the [GDELT Global Knowledge Graph Codebook](https://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf) for the native format and [published agreement results](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/evaluation/results.md) for measured reconstruction quality.

## Installation

Requires Python 3.12 or newer. For English record generation:

```shell
python -m pip install "gdelt-regkg[ner]"
python -m spacy download en_core_web_sm
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
```

See [installation](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/installation.md) for optional dependencies, translation and CPU/CUDA setup. External dictionaries and models are prepared locally and retain their own [source terms](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/reference/dictionaries.md#third-party-terms).

> [!TIP]
> For expanded GCAM coverage and GPU inference, follow the [TL;DR setup commands](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/installation.md#tldr-expanded-coverage-and-gpu): v5 plus LIWC 2007 and MPQA, `en_core_web_lg`, and CUDA with CuPy. LIWC requires an authorized dictionary supplied by you. Broader coverage does not guarantee higher accuracy; see [measured agreement](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/evaluation/results.md).

## Usage

The library supports processing fields either individually:

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

or all at once:

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
with open("articles.gkg.tsv", "w", encoding="utf-8", newline="") as stream:
    write_gkg([record], stream)
```

`articles.gkg.tsv` contains one complete, headerless GKG row. Run from the directory containing `local-resources/` prepared by `gdelt-regkg-cli build`.

See [quickstart](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/quickstart.md) for standalone field extraction and [record generation](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/guides/records.md) for metadata, overrides and export behavior.

## Documentation

| Topic | Documentation |
| --- | --- |
| Start here | [Documentation index](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/README.md) and [quickstart](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/quickstart.md) |
| Python interfaces | [API reference](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/reference/python-api.md) |
| Field formats and limitations | [All 27 GKG fields](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/reference/fields/README.md) |
| Dictionaries and configuration | [Resource guide](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/guides/resources.md) |
| Non-English articles | [Translation guide](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/guides/translation.md) |
| Command-line tools | [CLI reference](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/reference/cli.md) and [benchmark guide](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/guides/benchmarking.md) |
| Accuracy and interpretation | [Results](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/evaluation/results.md) and [methodology](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/evaluation/methodology.md) |
| Upgrading | [Migration guide](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/migration.md) and [changelog](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md) |

## Contributing

See [Contributing](https://github.com/octo-gone/gdelt-regkg/blob/master/CONTRIBUTING.md) for project architecture, local checks and evaluation requirements. Use the GitHub issue forms for bugs, features and extraction differences. Follow the [code of conduct](https://github.com/octo-gone/gdelt-regkg/blob/master/CODE_OF_CONDUCT.md); report vulnerabilities through the [security policy](https://github.com/octo-gone/gdelt-regkg/blob/master/SECURITY.md).

## License and disclaimer

This is an independent implementation, unaffiliated with and not endorsed by the GDELT Project. Reconstructed fields are approximate; results depend on article text, translation, models and dictionaries. Validate them for your intended analysis.

The code and original rules use the [MIT license](https://github.com/octo-gone/gdelt-regkg/blob/master/LICENSE) and are provided without warranty. External dictionaries, models, article bodies and derived profiles retain their [source terms](https://github.com/octo-gone/gdelt-regkg/blob/master/docs/reference/dictionaries.md#third-party-terms).
