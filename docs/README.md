# Documentation

`gdelt-regkg` reconstructs GDELT [Global Knowledge Graph (GKG)](get-started/concepts-and-glossary.md#gkg) records from prepared article text and supplied metadata. Generate complete 27-column records or analyze individual fields from Python. The library approximates GDELT's processing for text-derived fields and formats caller-supplied metadata according to the GKG format.

## What the library does

Use the library to process your own news datasets, fill gaps in available records or analyze texts using different NLP methods. Supply plain-text article bodies and metadata, then select dictionaries and models for the fields you need. The library supports English extraction and optional translation, with native-language [Global Content Analysis Measures (GCAM)](get-started/concepts-and-glossary.md#gcam-and-dimensions) dictionaries for applicable source languages.

The implementation is independent of the GDELT Project, so constructed values can differ from similar GDELT outputs. Read [Results](evaluation/results.md) and [Limitations and intended use](evaluation/limitations-and-intended-use.md) before treating them as interchangeable.

## Try a field

After installing the core package with `python -m pip install gdelt-regkg`, run:

```python
from gdelt_regkg.fields.counts import analyze_counts

text = "12 people were killed."
result = analyze_counts(text)
print(result.to_gkg())
```

```text
CRISISLEX_T03_DEAD#12#people#0######;KILL#12#people#0######;
```

This example uses packaged rules and needs no downloaded model or dictionary. [Quickstart](get-started/quickstart.md) also shows complete record generation and export.

## Generate records from your articles

Start with [Installation and setup](get-started/installation-and-setup.md), then follow [Quickstart](get-started/quickstart.md) to setup basic pipeline. Check [Generate records](guides/records.md) guide, it explains metadata, precomputed recognition results, overrides and export. Use [GKG field reference](reference/fields/README.md) to inspect the 27 columns.

For non-English bodies, [Translation](guides/translation.md) quide covers language detection and translation. [Concepts and glossary](get-started/concepts-and-glossary.md) can help with keywords, abbreviations, metrics and other concepts used throughout documentation.

## Choose dictionaries and execution settings

[Build resources](guides/resources.md) guide explains resource preparation and profile selection. [Build GCAM resources](guides/gcam-resources.md) covers presets, individual dictionary imports and a complete expanded setup. [Build gazetteers](guides/gazetteers.md) covers default and custom geographic references. [Dictionaries](reference/dictionaries.md) describes the inventory and source terms, and [Dictionary imports](guides/dictionary-imports.md) covers specialized conversions.

Use [GPU setup](guides/gpu-setup.md) for backend installation and device selection, [Performance](guides/performance.md) for batching and persistent caches, and [Troubleshooting](guides/troubleshooting.md) for dependency, model and resource errors.

## Understand or reproduce the published results

[Results](evaluation/results.md) identifies the evaluated configurations, article subsets and measured agreement. [Methodology](evaluation/methodology.md) defines metrics, matching and sampling. [Benchmarking](guides/benchmarking.md) provides commands for comparing native and reconstructed records. [Tone refinement](guides/tone-refinement.md) covers fitting candidate dictionaries with separate development and evaluation articles.

## Citing the software

Cite the release used in your work. The citation for version 2.1.2 is:

```bibtex
@misc{klimin2026gdeltregkg,
  author = {Klimin, Nikita A.},
  title = {{gdelt-regkg}},
  publisher = {Zenodo},
  year = {2026},
  month = oct,
  howpublished = {Computer software},
  version = {2.1.2},
  note = {Version 2.1.2},
  doi = {10.5281/zenodo.23314745}
}
```

For another release, use the metadata from its Zenodo record. Machine-readable citation metadata is also available in [`CITATION.cff`](https://github.com/octo-gone/gdelt-regkg/blob/master/CITATION.cff). Cite the [dictionaries](reference/dictionaries.md) and [preprocessing tools](reference/dictionaries.md#preprocessing-citations) used in your analysis separately.

## Reference and development

- [CLI](reference/cli.md) documents commands, arguments and defaults.
- [Migration](get-started/migration.md) explains upgrades to the current API.
- [Development setup](development/setup.md) covers dependencies, local checks, tests and extraction evaluation.
- [Project structure](development/project-structure.md) describes the source modules and repository layout.
- [Build the documentation](development/documentation.md) covers previews, checks and publishing.
- [Contributing ↗](https://github.com/octo-gone/gdelt-regkg/blob/master/CONTRIBUTING.md) covers issues, pull requests, external inputs and GitHub Pages setup.
- [Changelog ↗](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md) records releases and historical experiments.
