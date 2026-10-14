# Contributing

Contributions can improve extraction, resource importers, benchmarks, documentation or installation. Use the GitHub issue forms to report a bug, propose a feature or describe a difference from native GKG output. Discuss changes to public APIs, default profiles or dependencies before implementing them.

## Project structure

The `src/gdelt_regkg/fields/` package contains structured field analyzers,
NER, language detection, translation and independent rule loaders. Import analyzers
from their owning field modules. `pipeline.py` composes fields into records;
`record.py` defines the column contract, `profiles.py` composes resources, and
`utils.py` and `wire.py` handle resource lookup and serialization. Resource converters
live in `src/gdelt_regkg/builders/`, command handling in `src/gdelt_regkg/cli/`, field
evaluation in `src/gdelt_regkg/benchmark/`, and tone dictionary refinement in
`src/gdelt_regkg/scripts/` behind `gdelt-regkg-cli refine-tone`.
Documentation starts at [docs/README.md](docs/README.md), with separate installation,
API usage and CLI guides.

## Local checks

Prepare the dictionaries and small English model using [Installation and setup](docs/installation.md#basic-english-setup). From a development checkout, install tools with `uv sync --inexact --group dev --all-extras`. Install PyTorch and, for GPU NER, CuPy separately using the [CPU/CUDA instructions](docs/installation.md#non-english-articles). The full suite requires the standard dictionaries and geographic reference; source-replay checks also use the original downloaded files.

```shell
uv run --no-sync pre-commit install
uv run --no-sync python -m unittest discover -s tests
uv run --no-sync pre-commit run --all-files
```

For work without external dictionaries, run the resource-routing checks separately:

```shell
uv run --no-sync python -m unittest discover -s tests -p test_local_resources.py
```

CI prepares standard resources, builds the distributions and runs the tests against the installed wheel. It does not download optional Lexicoder/Roget profiles or translation weights.

The pylint and mypy hooks use the project's installed development environment and check the complete package and maintained scripts. They do not require dictionaries, model weights or PyTorch. You can run them separately with `uv run --no-sync python -m pylint src/gdelt_regkg .github/scripts` and `uv run --no-sync python -m mypy`. Mypy checks function bodies and existing annotations; complete annotations for every helper are not required. Pylint checks correctness and limits functions to 10 arguments, 30 locals, 15 branches, 80 statements and five nested blocks; documentation and formatting are handled separately.

## Pull requests

Describe the problem, resulting behavior and validation. Include a small reproducible example and appropriate regression checks for behavior changes. Update affected field examples and setup instructions. Preserve the 27-column order, GKG cell separators and offsets into the analyzed English body.

For extraction changes, report the model, resource revisions and relevant precision, recall, F1 or error metrics. Select rules on development data and reserve separate articles for evaluation. Do not tune on the published held-out benchmark or repeatedly use it to select changes; evaluate new candidates on a fresh reserved sample.

Commit code, original rules, schemas and reproducible build recipes. Keep downloaded dictionaries, source-derived profiles, model weights, article corpora, credentials and generated outputs out of the repository and distributions. Small test fixtures must be authored or permitted for redistribution; identify the source and terms of any contributed third-party material.

Contributions to this project's code and original rules are submitted under its [MIT license](LICENSE). External inputs retain their own terms. Follow the [code of conduct](CODE_OF_CONDUCT.md) and keep reviews focused on the change.

Report vulnerabilities privately using [the security policy](SECURITY.md).
