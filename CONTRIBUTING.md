# Contributing

Use the [issue forms](https://github.com/octo-gone/gdelt-regkg/issues/new/choose) to report a bug, propose a feature, improve extraction, resource importers, benchmarks, documentation, installation or describe a difference from native Global Knowledge Graph (GKG) output. Discuss changes to public APIs, default profiles or dependencies before implementing them.

Follow the [code of conduct](CODE_OF_CONDUCT.md). Report vulnerabilities privately using the [security policy](SECURITY.md).

## Development documentation

- [Development setup and checks](docs/development/setup.md) covers dependencies, tests and extraction evaluation.
- [Project structure](docs/development/project-structure.md) describes the source modules and repository layout.
- [Build the documentation](docs/development/documentation.md) covers previews, validation and site configuration.

## External inputs

Commit code, original rules, schemas and reproducible build recipes. Keep downloaded dictionaries, source-derived profiles, model weights, article corpora, credentials and generated outputs out of the repository and distributions. Small test fixtures must be authored or permitted for redistribution. Identify the source and terms of any contributed third-party material.

Store external source files in `downloads/` and generated profiles in `local-resources/`. Both directories are excluded from version control. Use [Build GCAM resources](docs/guides/gcam-resources.md) for dictionary presets and custom inventories, [Build gazetteers](docs/guides/gazetteers.md) for geographic references, and [Dictionary imports](docs/guides/dictionary-imports.md) for raw formats and conversion procedures.

If you have a missing dictionary, lexicon or matching rules, contact the [maintainer privately](https://github.com/octo-gone) through a contact method listed on their profile to arrange a transfer. Share files only when their terms permit it, and include the source, edition, citation and license or permission statement. Private sharing does not authorize redistribution.

Keep these materials in `downloads/` or `local-resources/`. Do not commit them to any branch or fork, do not include them in a pull request, or attach them to a public issue. The materials are external to the repository and package.

## Pull requests

Use the [pull request template](.github/pull_request_template.md) to describe:

- The problem and resulting behavior, with a related issue or small reproducible example where useful.
- The checks run and their results, including appropriate regression checks for behavior changes.
- Updates to documentation, examples and setup instructions, and any third-party inputs or terms introduced by the change.

For extraction changes, include the model and profile configuration and identify the separate development and evaluation data used.

Contributions to this project's code and original rules are submitted under its [MIT license](LICENSE). External inputs retain their own terms. Keep reviews focused on the change.
