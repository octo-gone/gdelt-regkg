# Installation

Requires **Python 3.12 or newer**. Install the package and any selected models in
the same environment. Downloads are needed during setup; extraction uses local
resources and model weights.

```shell
python -m venv .venv
```

Activate it with `source .venv/bin/activate` on Linux/macOS or
`.venv\Scripts\Activate.ps1` in PowerShell.

## Basic English setup

```shell
python -m pip install gdelt-regkg
python -m spacy download en_core_web_sm
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
```

The build downloads the recorded dictionary and geographic sources and writes
compiled profiles to `local-resources/`. Review their [source terms](cli/build.md#third-party-terms).
Pass `resources_dir=` in Python when using a different output directory.

Install only what your selected fields require:

| Purpose | Additional setup |
| --- | --- |
| Dates, amounts and quotations | Package only |
| Authored count and name rules | `gdelt-regkg-cli build counts ner --output local-resources` |
| Tone, themes and GCAM | [Build the selected dictionaries](cli/build.md#resource-arguments) |
| Persons, organizations and broad names | English spaCy model; name rules for the default name policy |
| Locations and count geography | English spaCy model and [geographic reference](cli/build.md#geographic-reference-files) |

For a first extraction, follow [Generate a GKG record](api-usage.md#generate-a-gkg-record).
See [Build resources](cli/build.md) for partial builds, source files and custom profiles.

## English models

For the documented large-model configuration, install:

```shell
python -m spacy download en_core_web_lg
```

`en_core_web_md` is another option. Select the installed model explicitly through
`SpacyNER.from_model("en_core_web_lg", resources_dir="local-resources")` or
`benchmark --ner-model en_core_web_lg`. Installing a model does not change the
selected default. The recorded studies use spaCy 3.8.0 English model packages
with spaCy 3.8. English extraction needs no PyTorch or translation weights.

Optional dictionaries for wider GCAM coverage are described in
[GCAM profiles and expansion](cli/build.md#gcam-profiles-and-expansion).

## Non-English articles

Detect the language and translate to English **before** extraction. The library's local translation backend, M2M100 418M, needs PyTorch and model weights.

### Install PyTorch

Choose the PyTorch build for your hardware **before** running a translation example. The default library installation does not install or replace PyTorch; if a compatible build is already installed, keep it.

```shell
# GPU (CUDA 13.0; requires a compatible NVIDIA GPU and driver)
python -m pip install "torch>=2.13" --index-url https://download.pytorch.org/whl/cu130

# CPU only
python -m pip install "torch>=2.13" --index-url https://download.pytorch.org/whl/cpu
```

See the [PyTorch installation guide](https://pytorch.org/get-started/locally/) for other platforms.

### About the `cpu`, `cu128` and `cu130` extras

These extras declare a PyTorch requirement, but they do not choose the build: with `pip`, the **index URL** decides between CPU and CUDA wheels.

| Extra | Notes |
| --- | --- |
| `cpu`, `cu130` | Also require patched setuptools. Preferred. |
| `cu128` | Older option for compatible environments. Its latest PyTorch wheel is 2.11.0 and it requires setuptools below 82, so it cannot include either the PyTorch 2.13.0 JIT fix or the setuptools 83.0.0 packaging fix. |

See the [translation API](fields/translation-info.md#local-translation).

### Model weights

- Weights are stored in the Hugging Face cache, normally `~/.cache/huggingface/hub`.
- Set `allow_download=False` once the weights are downloaded.
- To use another location, pass a complete local snapshot directory as `model=`.
- Use `device="cpu"` with the CPU PyTorch build.

A working end-to-end example is in the [complete pipeline](api-usage.md#complete-pipeline-example).

## Benchmarking

Install the statistical and retrieval dependencies:

```shell
python -m pip install "gdelt-regkg[benchmark]"
```

From a checkout, use `uv sync --extra benchmark`. Comparing prepared GKG rows
does not require dictionaries or an NER model; supported-vocabulary metrics use
the selected resource profiles when available. Generating predictions from
saved bodies requires the resources and model for the requested fields.
See the [benchmark guide](cli/benchmark.md) for inputs and commands.

## Development

From a source checkout:

```shell
uv sync --inexact --group dev
```

Prepare the English model and resources above before running the full test suite.
[Contributing](../CONTRIBUTING.md#local-checks) describes tests and formatting checks.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `ResourceUnavailableError` | Build the required profiles and check `resources_dir=` or `--resources-dir`. |
| spaCy cannot load the model | Install the named model in the same environment as the package. |
| Translation cannot load or run | Check the PyTorch build, device and locally available model weights in [Non-English articles](#non-english-articles). |

[API usage](api-usage.md) · [CLI guide](cli/README.md) · [Field documentation](README.md)
