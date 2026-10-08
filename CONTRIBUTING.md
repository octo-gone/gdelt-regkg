# Contributing

Contributions can improve extraction, resource importers, benchmarks, documentation or installation. Use the GitHub issue forms to report a bug, propose a feature or describe a difference from native GKG output. Discuss changes to public APIs, default profiles or dependencies before implementing them.

## Local checks

Prepare the dictionaries and small English model using [Installation and setup](docs/installation.md#quick-start-basic-english-setup). From a development checkout, install tools with `uv sync --inexact --group dev`. The full suite requires the standard dictionaries and geographic reference; source-replay checks also use the original downloaded files.

```shell
uv run --no-sync python -m unittest discover -s tests
uv run --no-sync pre-commit run --all-files
```

For work without external dictionaries, run the resource-routing checks separately:

```shell
uv run --no-sync python -m unittest discover -s tests -p test_local_resources.py
```

CI prepares standard resources, builds the distributions and runs the tests against the installed wheel. It does not download optional Lexicoder/Roget profiles or translation weights.

The pylint and mypy hooks use the project's installed development environment and check the complete package and maintained scripts. They do not require dictionaries, model weights or PyTorch. You can run them separately with `uv run --no-sync python -m pylint src/gdelt_regkg scripts .github/scripts` and `uv run --no-sync python -m mypy`. Mypy checks function bodies and existing annotations; complete annotations for every helper are not required. Pylint omits documentation, formatting and size/complexity warnings while retaining correctness checks.

## Pull requests

Describe the problem, resulting behavior and validation. Include a small reproducible example and appropriate regression checks for behavior changes. Update affected field examples and setup instructions. Preserve the 27-column order, GKG cell separators and offsets into the analyzed English body.

For extraction changes, report the model, resource revisions and relevant precision, recall, F1 or error metrics. Select rules on development data and reserve separate articles for evaluation. Do not tune on the published held-out benchmark or repeatedly use it to select changes; evaluate new candidates on a fresh reserved sample.

Commit code, original rules, schemas and reproducible build recipes. Keep downloaded dictionaries, source-derived profiles, model weights, article corpora, credentials and generated outputs out of the repository and distributions. Small test fixtures must be authored or permitted for redistribution; identify the source and terms of any contributed third-party material.

Contributions to this project's code and original rules are submitted under its [MIT license](LICENSE). External inputs retain their own terms. Follow the [code of conduct](CODE_OF_CONDUCT.md) and keep reviews focused on the change.

Report vulnerabilities privately using [the security policy](SECURITY.md).
