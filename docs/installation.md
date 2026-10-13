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

## CUDA and compute backends

NER uses spaCy/CuPy; local translation uses PyTorch. Install the backend for each
task you need. English extraction does not require PyTorch. CUDA inference
requires a compatible NVIDIA GPU and driver; installing an extra does not select
the device in Python.

| Compute option | NER extra (spaCy/CuPy) | Translation extra (PyTorch) |
| --- | --- | --- |
| CPU | No extra | `cpu` |
| CUDA 12.8 | `ner-cu128` | `cu128` |
| CUDA 13.0 | `ner-cu130` | `cu130` |

NER extras include CuPy and the matching CUDA runtime, but not an English model.
Install the model as described in [English models](#english-models).

### From a source checkout with uv

Choose the command for your workload. uv selects the configured PyTorch index
for `cpu`, `cu128` and `cu130`:

```shell
# GPU NER only, CUDA 13.0
uv sync --inexact --extra ner-cu130

# GPU translation only, CUDA 13.0
uv sync --inexact --extra cu130

# Both backends on GPU, CUDA 13.0
uv sync --inexact --extra ner-cu130 --extra cu130

# Both backends on GPU, CUDA 12.8
uv sync --inexact --extra ner-cu128 --extra cu128

# CPU translation; NER uses CPU by default
uv sync --inexact --extra cpu
```

Add `--extra benchmark` for benchmarking or `--group dev` for development.
`--inexact` preserves separately installed packages, including English models.

### With pip

Install the NER extra for your CUDA version:

```shell
python -m pip install "gdelt-regkg[ner-cu130]"
# CUDA 12.8 alternative:
python -m pip install "gdelt-regkg[ner-cu128]"
```

For translation, install PyTorch from the appropriate index first. With pip,
the `cpu`, `cu128` and `cu130` extras declare requirements; they do not select
the PyTorch wheel index. Keep an existing compatible PyTorch installation.

```shell
# GPU translation, CUDA 13.0
python -m pip install "torch>=2.13" --index-url https://download.pytorch.org/whl/cu130
python -m pip install "gdelt-regkg[cu130]"

# CPU translation alternative
python -m pip install "torch>=2.13" --index-url https://download.pytorch.org/whl/cpu
python -m pip install "gdelt-regkg[cpu]"
```

For both GPU backends, install the NER extra as well as the selected PyTorch
build and translation extra. Prefer `cpu` or `cu130` for translation: these
require patched setuptools and PyTorch 2.13 or newer. The CUDA 12.8 option uses
the older PyTorch wheel line, which requires setuptools below 82 and lacks the
PyTorch 2.13 JIT and setuptools 83 packaging fixes.

### Combining and switching backends

Install only one NER GPU extra and one PyTorch extra. Match the CUDA versions
when both backends use GPU; CPU PyTorch can be combined with either NER GPU extra.

When switching CUDA versions with `--inexact`, uninstall the old CuPy wheel
before syncing the new extra. For CUDA 12 to CUDA 13, run
`uv pip uninstall cupy-cuda12x` first; for the reverse, uninstall `cupy-cuda13x`.
The two wheels provide the same Python package and must not be installed together.

Select devices using the [NER and translation API examples](api-usage.md#gpu-inference)
or the [benchmark command](cli/benchmark.md#model-device-and-batching).
See [spaCy GPU configuration](https://spacy.io/api/top-level#require_gpu),
[CuPy installation](https://docs.cupy.dev/en/stable/install.html) and
[PyTorch installation](https://pytorch.org/get-started/locally/) for platform requirements.

## Non-English articles

Detect the language and translate to English **before** extraction. The local
translation backend, M2M100 418M, needs a [PyTorch backend](#cuda-and-compute-backends)
and model weights.

- Weights are stored in the Hugging Face cache, normally `~/.cache/huggingface/hub`.
- Set `allow_download=True` for the first load, then `False` for offline use.
- To use another location, pass a complete local snapshot directory as `model=`.
- Use `device="cpu"` with the CPU PyTorch build.

See the [translation API](fields/translation-info.md#local-translation) and the
[complete pipeline example](api-usage.md#complete-pipeline-example).

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
