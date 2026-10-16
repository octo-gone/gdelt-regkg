# Documentation

`gdelt-regkg` reconstructs GDELT GKG records from prepared article text and supplied metadata. Library **approximates** GDELT processing for text-derived fields, metadata fields are supplied by the caller and format according to GDELT.

## Get started

1. [Install the library](installation.md), optional dependencies and models.
2. [Run the quickstart](quickstart.md) to extract a field and write a complete record.
3. [Prepare and select resources](guides/resources.md) for your own articles.

For an expanded setup, use the [TL;DR commands](installation.md#tldr-expanded-coverage-and-gpu) for GCAM v5 with LIWC and MPQA, the large English model and NVIDIA GPU inference.

## Guides

| Task | Guide |
| --- | --- |
| Generate records, supply metadata and export TSV | [Records](guides/records.md) |
| Build dictionaries and select or customize profiles | [Resources](guides/resources.md) |
| Convert specialized source files and add optional dictionaries | [Dictionary imports](guides/dictionary-imports.md) |
| Detect languages, translate bodies and retain provenance | [Translation](guides/translation.md) |
| Batch inference, reuse models and manage persistent caches | [Performance](guides/performance.md) |
| Compare native and reconstructed records | [Benchmarking](guides/benchmarking.md) |
| Fit and evaluate candidate tone dictionaries | [Tone refinement](guides/tone-refinement.md) |

## Reference

| Reference | Contents |
| --- | --- |
| [Python API](reference/python-api.md) | Public interfaces, options, result types and exceptions |
| [CLI](reference/cli.md) | Commands, arguments, defaults and output conventions |
| [GKG fields](reference/fields/README.md) | All 27 columns in wire order, with encodings, examples and limitations |
| [Dictionaries](reference/dictionaries.md) | GCAM inventory, acquisition links, source terms and citations |

## Evaluation and development

- [Published results](evaluation/results.md) describe measured agreement and the evaluated configurations.
- [Evaluation methodology](evaluation/methodology.md) explains metrics, sampling and interpretation.
- [Migration](migration.md) covers upgrading to the current API.
- [Contributing](../CONTRIBUTING.md) describes architecture, development checks and contribution requirements.
- [Changelog](../CHANGELOG.md) records releases and historical experiments.
