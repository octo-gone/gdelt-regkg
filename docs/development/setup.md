# Development setup

Use Python 3.12 or newer and [uv](https://docs.astral.sh/uv/). Run the commands below from the repository root on Windows, Linux or macOS.

For documentation-only changes, use the [documentation workflow](documentation.md). For code changes, install the development tools and feature dependencies:

```shell
uv sync --inexact --group dev --extra build --extra ner --extra lang --extra benchmark
uv run --no-sync pre-commit install
```

`--inexact` preserves other tools and optional dependencies already installed in the environment. Installing dependencies does not prepare external dictionaries or model weights.

For translation work, add `--extra translate` to the `uv sync` command and install PyTorch using [Translation](../guides/translation.md#setup). For CUDA recognition or translation, follow [GPU setup](../guides/gpu-setup.md). These backends are separate from the standard development setup.

## Local checks

After the development setup, run formatting, linting and documentation checks:

```shell
uv run --no-sync pre-commit run --all-files
uv run --no-sync python .github/scripts/check_docs.py
```

The hooks format Python with isort and Ruff, check correctness with pylint and mypy, and validate repository metadata. Review any formatting changes before committing. The configuration is in [`.pre-commit-config.yaml`](https://github.com/octo-gone/gdelt-regkg/blob/master/.pre-commit-config.yaml) and [`pyproject.toml`](https://github.com/octo-gone/gdelt-regkg/blob/master/pyproject.toml).

Pylint and mypy check the complete package and maintained scripts using the installed development environment. They do not require dictionaries, model weights or PyTorch. To run them separately:

```shell
uv run --no-sync python -m pylint src/gdelt_regkg .github/scripts
uv run --no-sync python -m mypy
```

Mypy checks existing annotations and function bodies, including untyped functions.

Run the tests relevant to your change. For example, the resource-routing tests use small local fixtures and require no external dictionaries:

```shell
uv run --no-sync python -m unittest discover -s tests -p test_local_resources.py
```

Resource builder and importer checks in `test_build_recipes.py` and `test_gcam_imports.py` also use local fixtures. The complete suite needs the resources described below.

## Full test suite

Prepare the recorded small English named entity recognition (NER) model and resource profiles. Tests cover historical profiles as well as the standard configuration, so build v1 and v2 before the default build. Review the [dictionary licenses](../reference/dictionaries.md#dictionary-licenses) and [source terms](../reference/dictionaries.md#third-party-terms) for every selected source before downloading.

These commands follow the model and resource setup in [CI](https://github.com/octo-gone/gdelt-regkg/blob/master/.github/workflows/ci.yml):

```shell
uv pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
uv run --no-sync gdelt-regkg-cli build tone themes counts gcam --use v1 --sources-dir downloads/resources --download-sources --output local-resources
uv run --no-sync gdelt-regkg-cli build tone themes counts gcam --use v2 --sources-dir downloads/resources --download-sources --output local-resources
uv run --no-sync gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
uv run --no-sync python -m unittest discover -s tests
```

Keep the original inputs in `downloads/resources/` for source-replay checks. The final build selects the standard profiles in `local-resources/defaults.json` and preserves the historical files. See [Build resources](../guides/resources.md) for input verification, partial builds and resource selection.

CI also builds the wheel and source distribution, validates them, installs the wheel and runs the tests against it. A separate GCAM v5 build checks multilingual coverage using an authored French imagery CSV fixture, so that check needs no Tesseract installation. CI does not prepare the optional dictionaries or translation model weights. See the [CI workflow](https://github.com/octo-gone/gdelt-regkg/blob/master/.github/workflows/ci.yml) for the exact package and coverage checks.

## Evaluate extraction changes

Preserve the 27-column order, GKG cell separators and offsets into the analyzed English body. Update affected field examples and setup instructions when behavior changes.

Report the model, resource revisions and relevant precision, recall, [F1 scores](../get-started/concepts-and-glossary.md#f1-scores) or error metrics. Select rules on development data and evaluate them on separate articles. Do not tune on the published held-out benchmark or repeatedly use it to select changes. Evaluate new candidates on a fresh reserved sample. See [Methodology](../evaluation/methodology.md) for the published evaluation design and [Contributing](https://github.com/octo-gone/gdelt-regkg/blob/master/CONTRIBUTING.md#external-inputs) for requirements on sharing external inputs.

