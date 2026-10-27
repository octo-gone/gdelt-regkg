# gdelt-regkg

[![CI](https://github.com/octo-gone/gdelt-regkg/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/octo-gone/gdelt-regkg/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/gdelt-regkg)](https://pypi.org/project/gdelt-regkg/)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://pypi.org/project/gdelt-regkg/)
[![License](https://img.shields.io/github/license/octo-gone/gdelt-regkg)](https://github.com/octo-gone/gdelt-regkg/blob/master/LICENSE)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23314745-blue)](https://doi.org/10.5281/zenodo.23314745)
[![arXiv](https://img.shields.io/badge/arXiv-2610.35358-b31b1b)](https://arxiv.org/abs/2610.35358)

Reconstruct GDELT GKG records from prepared article text and supplied metadata. Generate complete 27-column records or analyze individual fields from Python.

**[Documentation](https://octo-gone.github.io/gdelt-regkg/)** · [Installation and setup](https://octo-gone.github.io/gdelt-regkg/get-started/installation-and-setup/) · [Quickstart](https://octo-gone.github.io/gdelt-regkg/get-started/quickstart/) · [GKG field reference](https://octo-gone.github.io/gdelt-regkg/reference/fields/)

You can use `gdelt-regkg` to:

- Process your own news datasets into GKG-compatible records.
- Extract individual fields, such as themes, tone, entities or event counts, for analysis.
- Reconstruct gaps in GKG coverage from available article bodies and metadata.
- Analyze multilingual articles.
- Evaluate custom dictionaries and extraction profiles.
- Compare reconstructed fields with archived GKG output using the benchmark tools.

> [!NOTE]
> Text-derived values **approximate** GDELT's processing and **can differ** from native GKG output. Metadata and media fields format caller-supplied values. See the [GDELT Global Knowledge Graph Codebook](https://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf) for the native format and [Results](https://octo-gone.github.io/gdelt-regkg/evaluation/results/) for measured reconstruction quality.

## Installation

Requires Python 3.12 or newer. For English record generation:

```shell
python -m pip install "gdelt-regkg[ner]"
python -m spacy download en_core_web_sm
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
```

See [Installation and setup](https://octo-gone.github.io/gdelt-regkg/get-started/installation-and-setup/) for optional dependencies, translation and CPU/CUDA setup. External dictionaries and models are prepared locally and retain their own [source terms](https://octo-gone.github.io/gdelt-regkg/reference/dictionaries/#third-party-terms).

> [!TIP]
> To analyze a wider range of emotional, psychological and topical language, follow [Build GCAM resources](https://octo-gone.github.io/gdelt-regkg/guides/gcam-resources/#complete-expanded-example). The guide explains the available word lists, where to obtain them and how to prepare them for the library. Some lists require a license. For faster entity extraction or translation on a compatible NVIDIA GPU, follow [GPU setup](https://octo-gone.github.io/gdelt-regkg/guides/gpu-setup/). More categories do not guarantee closer agreement with GDELT. See [Results](https://octo-gone.github.io/gdelt-regkg/evaluation/results/).

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

See [Quickstart](https://octo-gone.github.io/gdelt-regkg/get-started/quickstart/) for standalone field extraction and [Generate records](https://octo-gone.github.io/gdelt-regkg/guides/records/) for metadata, overrides and export behavior.

## Documentation

| Topic | Documentation |
| --- | --- |
| Start here | [Home](https://octo-gone.github.io/gdelt-regkg/) and [Quickstart](https://octo-gone.github.io/gdelt-regkg/get-started/quickstart/) |
| Field formats and limitations | [GKG field reference](https://octo-gone.github.io/gdelt-regkg/reference/fields/) |
| Dictionaries and configuration | [Build resources](https://octo-gone.github.io/gdelt-regkg/guides/resources/) |
| Dictionary presets and custom inventories | [Build GCAM resources](https://octo-gone.github.io/gdelt-regkg/guides/gcam-resources/) |
| Geographic reference lookups | [Build gazetteers](https://octo-gone.github.io/gdelt-regkg/guides/gazetteers/) |
| Non-English articles | [Translation](https://octo-gone.github.io/gdelt-regkg/guides/translation/) |
| Command-line tools | [CLI](https://octo-gone.github.io/gdelt-regkg/reference/cli/) and [Benchmarking](https://octo-gone.github.io/gdelt-regkg/guides/benchmarking/) |
| Accuracy and interpretation | [Results](https://octo-gone.github.io/gdelt-regkg/evaluation/results/) and [Methodology](https://octo-gone.github.io/gdelt-regkg/evaluation/methodology/) |
| Upgrading | [Migration](https://octo-gone.github.io/gdelt-regkg/get-started/migration/) and [changelog](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md) |

## Citation

If you use this package in research, cite the [software release on Zenodo](https://doi.org/10.5281/zenodo.23314745). See [Citing the software](https://octo-gone.github.io/gdelt-regkg/#citing-the-software) for BibTeX and [`CITATION.cff`](https://github.com/octo-gone/gdelt-regkg/blob/master/CITATION.cff) for machine-readable metadata. Cite the [dictionary resources](https://octo-gone.github.io/gdelt-regkg/reference/dictionaries/) used in your analysis separately.

For the field-level agreement evaluation, cite Nikita A. Klimin (2026), [*Agreement Between Reconstructed and Native GDELT GKG Records: A Field-Level Baseline*](https://arxiv.org/abs/2610.35358). See [Citing the agreement study](https://octo-gone.github.io/gdelt-regkg/#citing-the-agreement-study) for BibTeX.

## Contributing

See [Development setup](https://octo-gone.github.io/gdelt-regkg/development/setup/) for local checks and evaluation requirements, and [Project structure](https://octo-gone.github.io/gdelt-regkg/development/project-structure/) for the source layout. [Contributing](https://github.com/octo-gone/gdelt-regkg/blob/master/CONTRIBUTING.md) covers issue reports, pull requests and external inputs. Follow the [code of conduct](https://github.com/octo-gone/gdelt-regkg/blob/master/CODE_OF_CONDUCT.md); report vulnerabilities through the [security policy](https://github.com/octo-gone/gdelt-regkg/blob/master/SECURITY.md).

Implementation tasks are listed under [Future work](https://octo-gone.github.io/gdelt-regkg/#future-work).

## License and disclaimer

This is an independent implementation, unaffiliated with and not endorsed by the GDELT Project. Reconstructed fields are approximate; results depend on article text, translation, models and dictionaries. Validate them for your intended analysis.

The code and original rules use the [MIT license](https://github.com/octo-gone/gdelt-regkg/blob/master/LICENSE) and are provided without warranty. External dictionaries, models, article bodies and derived profiles retain their [source terms](https://octo-gone.github.io/gdelt-regkg/reference/dictionaries/#third-party-terms).
