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

## Understand or reproduce the Results

The agreement study, [*Agreement Between Reconstructed and Native GDELT GKG Records: A Field-Level Baseline*](https://arxiv.org/abs/2610.35358), evaluates reconstructed fields against native GKG records. See [Citing the agreement study](#citing-the-agreement-study) for its citation.

[Results](evaluation/results.md) summarizes the paper and compares it with the earlier [development benchmark](evaluation/development-benchmarks.md). [Methodology](evaluation/methodology.md) distinguishes the study design from the benchmark tools' reporting behavior. [Benchmarking](guides/benchmarking.md) provides commands for comparing native and reconstructed records. [Tone refinement](guides/tone-refinement.md) covers fitting candidate dictionaries with separate development and evaluation articles.

## Future work

1. Add a Moses statistical translation adapter to `Translator`.
2. Implement CLD2 in `LanguageDetector`.
3. Extend GCAM dictionary profiles with language-specific tokenization, morphological normalization, contextual exclusions, and other dictionary-specific preprocessing.

> [!NOTE]
> GDELT's [2015 Translingual architecture](https://blog.gdeltproject.org/gdelt-translingual-translating-the-planet/) used CLD2, Moses statistical machine translation, and dictionary-based translation ranking. The [2021 Translingual 2.0 architecture](https://blog.gdeltproject.org/experiments-with-machine-translation-improving-translation-speed-and-hardware-efficiency/) introduced hybrid neural–statistical translation. Exact configurations for archived records are undocumented.

## Citing the software

Cite the release used in your work. The citation for version 2.1.3 is:

```bibtex
@misc{klimin2026gdeltregkg,
  author = {Klimin, Nikita A.},
  title = {{gdelt-regkg}},
  publisher = {Zenodo},
  year = {2026},
  month = oct,
  howpublished = {Computer software},
  version = {2.1.3},
  note = {Version 2.1.3},
  doi = {10.5281/zenodo.23314745}
}
```

For another release, use the metadata from its Zenodo record. Machine-readable citation metadata is also available in [`CITATION.cff`](https://github.com/octo-gone/gdelt-regkg/blob/master/CITATION.cff). Cite the [dictionaries](reference/dictionaries.md) and [preprocessing tools](reference/dictionaries.md#preprocessing-citations) used in your analysis separately.

## Citing the agreement study

When discussing the field-level agreement evaluation, cite Nikita A. Klimin (2026), [*Agreement Between Reconstructed and Native GDELT GKG Records: A Field-Level Baseline*](https://arxiv.org/abs/2610.35358):

```bibtex
@misc{klimin2026agreement,
  author = {Klimin, Nikita A.},
  title = {Agreement Between Reconstructed and Native {GDELT} {GKG} Records: A Field-Level Baseline},
  year = {2026},
  eprint = {2610.35358},
  archivePrefix = {arXiv},
  primaryClass = {cs.CL},
  doi = {10.48550/arXiv.2610.35358},
  url = {https://arxiv.org/abs/2610.35358}
}
```

The paper evaluates 193,550 English articles from 2020–2025 and 2,500 articles in five other languages. [Results](evaluation/results.md) summarizes its findings; the larger, earlier English corpus is documented under [Development benchmark](evaluation/development-benchmarks.md). Use the paper's stated samples and metrics when citing its findings. Cite the [software release](#citing-the-software) as well when using the package.

## Reference and development

- [CLI](reference/cli.md) documents commands, arguments and defaults.
- [Migration](get-started/migration.md) explains upgrades to the current API.
- [Development setup](development/setup.md) covers dependencies, local checks, tests and extraction evaluation.
- [Project structure](development/project-structure.md) describes the source modules and repository layout.
- [Build the documentation](development/documentation.md) covers previews, checks and publishing.
- [Contributing ↗](https://github.com/octo-gone/gdelt-regkg/blob/master/CONTRIBUTING.md) covers issues, pull requests, external inputs and GitHub Pages setup.
- [Changelog ↗](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md) records releases and historical experiments.
