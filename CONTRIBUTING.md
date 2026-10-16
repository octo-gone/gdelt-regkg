# Contributing

Contributions can improve extraction, resource importers, benchmarks, documentation or installation. Use the GitHub issue forms to report a bug, propose a feature or describe a difference from native GKG output. Discuss changes to public APIs, default profiles or dependencies before implementing them.

## Pull requests

Describe the problem, resulting behavior and validation. Include a small reproducible example and appropriate regression checks for behavior changes. Update affected field examples and setup instructions. Preserve the 27-column order, GKG cell separators and offsets into the analyzed English body.

For extraction changes, report the model, resource revisions and relevant precision, recall, F1 or error metrics. Select rules on development data and reserve separate articles for evaluation. Do not tune on the published held-out benchmark or repeatedly use it to select changes; evaluate new candidates on a fresh reserved sample.

Commit code, original rules, schemas and reproducible build recipes. Keep downloaded dictionaries, source-derived profiles, model weights, article corpora, credentials and generated outputs out of the repository and distributions. Small test fixtures must be authored or permitted for redistribution; identify the source and terms of any contributed third-party material.

If you have a missing dictionary, lexicon or matching rules, contact the [maintainer privately](https://github.com/octo-gone) through a contact method listed on their profile to arrange a transfer. Share files only when their terms permit it, and include the source, edition, citation and license or permission statement. Keep these materials in `downloads/` or `local-resources/`; do not commit them to any branch or fork, include them in a pull request, or attach them to a public issue. Private sharing does not authorize redistribution; the materials remain external to the repository and package.

Contributions to this project's code and original rules are submitted under its [MIT license](LICENSE). External inputs retain their own terms. Follow the [code of conduct](CODE_OF_CONDUCT.md) and keep reviews focused on the change.

Report vulnerabilities privately using [the security policy](SECURITY.md).

## Project structure

The library source is in [`src/gdelt_regkg/`](src/gdelt_regkg). Field modules
analyze individual GKG fields; the pipeline combines their results with supplied
metadata to produce complete records. Paths in the following table are relative
to this package directory.

| Path | Responsibility |
| --- | --- |
| `__init__.py` | Exposes the record-generation API, resource configuration and public exceptions. |
| `fields/` | Implements field analyzers and rule loaders, named entity recognition (NER), language detection and translation. Import individual analyzers from their corresponding field modules. |
| `pipeline.py` | Coordinates field analysis, assembles records and provides record serialization and output functions. |
| `record.py` | Defines `GKGRecord` and the ordered 27-column GKG contract. |
| `profiles.py` | Defines `Resources`, which selects explicit resource objects or loads the configured defaults when needed. |
| `utils.py` | Resolves local and packaged resource paths and loads resource data. |
| `wire.py` | Parses and serializes count and theme cells using GKG separators. |
| `builders/` | Converts external dictionaries and geographic references into local resource formats. |
| `cli/` | Implements `gdelt-regkg-cli`, including resource builds, benchmarks and command input validation. |
| `benchmark/` | Prepares evaluation corpora, compares reconstructed fields with archived GKG values and generates metrics and reports. |
| `scripts/` | Contains tone dictionary refinement, exposed through `gdelt-regkg-cli refine-tone`. |
| `resources/` | Contains authored rules, JSON schemas, build recipes and default resource revisions. See the [resource overview](src/gdelt_regkg/resources/README.md). |

Supporting directories at the repository root:

| Path | Contents |
| --- | --- |
| [`tests/`](tests) | Automated tests, shared test helpers and small fixtures. |
| [`docs/`](docs/README.md) | Installation, quickstart, task guides, API/CLI and field references, evaluation results and migration instructions. |
| [`.github/`](.github) | CI and release workflows, release scripts, issue forms and the pull request template. |

External source files belong in `downloads/`, generated runtime dictionaries and
geographic references default to `local-resources/`. These directories are local
to the checkout and excluded from version control. See [Build resources](docs/guides/resources.md)
for profile builds and selection; specialized conversion procedures are in [Dictionary imports](docs/guides/dictionary-imports.md).

## Local checks

Prepare the dictionaries and small English model using [Installation and setup](docs/installation.md#basic-english-setup). From a development checkout, install tools with `uv sync --inexact --group dev --all-extras`. For local M2M100 translation, install PyTorch separately using the [CPU/CUDA instructions](docs/installation.md#non-english-articles). For GPU NER, follow the separate [CuPy setup](docs/installation.md#gpu-inference). The full suite requires the standard dictionaries and geographic reference; source-replay checks also use the original downloaded files.

```shell
uv run --no-sync pre-commit install
uv run --no-sync python .github/scripts/check_docs.py
uv run --no-sync python -m unittest discover -s tests
uv run --no-sync pre-commit run --all-files
```

For work without external dictionaries, run the resource-routing checks separately:

```shell
uv run --no-sync python -m unittest discover -s tests -p test_local_resources.py
```

CI prepares standard resources, builds the distributions and runs the tests against the installed wheel. It does not download optional dictionaries, lexicons or translation weights.

The pylint and mypy hooks use the project's installed development environment and check the complete package and maintained scripts. They do not require dictionaries, model weights or PyTorch. You can run them separately with `uv run --no-sync python -m pylint src/gdelt_regkg .github/scripts` and `uv run --no-sync python -m mypy`. Mypy checks function bodies and existing annotations; complete annotations for every helper are not required. Pylint checks correctness and limits functions to 10 arguments, 30 locals, 15 branches, 80 statements and five nested blocks; documentation and formatting are handled separately.
