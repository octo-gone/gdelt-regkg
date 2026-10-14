# Installation

Requires Python 3.12 or newer. The core installation has no third-party runtime dependencies:

```shell
python -m pip install gdelt-regkg
```

Dates, amounts, quotations and authored counts work without NLP backends. Tone, themes and GCAM need prepared dictionaries. Install the features you use:

| Extra | Capability |
| --- | --- |
| `ner` | spaCy adapters; install an English model separately |
| `translate` | Transformers and SentencePiece for M2M100 translation; install PyTorch separately |
| `lang` | Lingua language detection and label verification; no PyTorch required |
| `benchmark` | Article retrieval and statistical benchmark dependencies |
| `all` | All feature extras above; PyTorch, CuPy and model weights remain separate |

Missing feature dependencies raise `OptionalDependencyError` naming the extra. Missing PyTorch or CuPy produces instructions for that separately installed backend. Missing models and dictionaries produce separate model/resource errors.

## Basic English setup

```shell
python -m pip install "gdelt-regkg[ner]"
python -m spacy download en_core_web_sm
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
```

Downloads occur only during explicit setup. Extraction uses local resources and model weights. Review external [source terms](cli/build.md#third-party-terms). Select another root through `Resources(resources_dir=path)` or CLI `--resources-dir`.

## English models

Use `SpacyNER.from_model("en_core_web_sm")` or install and select `en_core_web_lg` for the larger model. `resources_dir=` on the factory selects name rules; a supplied pipeline retains its own policy. Models remain external to the package.

## Non-English articles

Language detection alone needs only the `lang` extra:

```shell
python -m pip install "gdelt-regkg[lang]"
```

Local M2M100 translation requires PyTorch **installed separately** from the `translate` extra. Choose one CPU or CUDA build for your environment. For CPU translation:

```shell
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install "gdelt-regkg[translate,lang]"
```

For CUDA 12.8 translation, use this instead of the CPU installation:

```shell
python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
python -m pip install "gdelt-regkg[translate,lang]"
```

For CUDA 13.0, use `https://download.pytorch.org/whl/cu130` instead. Choose a build supported by your NVIDIA driver using the [PyTorch installation selector](https://pytorch.org/get-started/locally/). If a compatible PyTorch build is already installed, keep it and install just the feature extras. CuPy is not required for translation.

Verify the selected backend:

```python
import torch

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
```

Use `device="cpu"` for CPU inference or `device="cuda:0"` for the first CUDA device:

```python
from gdelt_regkg.fields.translation import M2M100Translator, translate_text

backend = M2M100Translator.from_model(device="cuda:0", allow_download=True)
result = translate_text(
    "Les autorités ont annoncé de nouvelles mesures pour protéger les habitants "
    "après les fortes inondations qui ont touché plusieurs villes de la région.",
    translator=backend,
)
print(result.source_language)
print(result.text)
```

```text
fra
The authorities have announced new measures to protect the inhabitants after the heavy floods that have affected several cities in the region.
```

Omitting `language=` detects it automatically using Lingua. English bodies pass through unchanged. Translation requires M2M100 weights; `allow_download=True` explicitly permits the first download. Afterwards use `allow_download=False` or a local snapshot directory. Backend model caches are separate from record generation.

Translate before generation and copy provenance with `RecordMetadata.from_translation`. Preserve the translated body because enhanced offsets index it. See [language detection and translation](api-usage.md#language-detection-and-translation) for standalone detection, explicit language labels and record generation.

## GPU inference

spaCy NER uses CuPy for CUDA inference. Install `ner`, an English model and CuPy wheel matching your supported CUDA major version. For CUDA 12:

```shell
python -m pip install "gdelt-regkg[ner]" "cupy-cuda12x[ctk]"
python -m spacy download en_core_web_sm
```

For CUDA 13, substitute `"cupy-cuda13x[ctk]"`. The `[ctk]` option installs CUDA component wheels; a compatible NVIDIA driver is still required. With an existing system CUDA Toolkit, the bare `cupy-cuda12x` or `cupy-cuda13x` wheel can use that toolkit instead. See [CuPy installation](https://docs.cupy.dev/en/stable/install.html) for driver and toolkit requirements. Install only one CuPy variant in an environment, including avoiding the source `cupy` package alongside a CUDA wheel. PyTorch is only needed here if you also translate or use a model that requires it.

Select the device **before loading the spaCy model**, then supply the recognizer to generation:

```python
import spacy

from gdelt_regkg import Resources
from gdelt_regkg.fields.ner import SpacyNER

spacy.require_gpu(0)
recognizer = SpacyNER.from_model("en_core_web_sm")
resources = Resources(resources_dir="local-resources", recognizer=recognizer)
mentions = recognizer.analyze("Flooding affected London.")
print(mentions)
```

Use `spacy.require_cpu()` before model loading to select CPU explicitly. See [spaCy device selection](https://spacy.io/api/top-level#require_gpu). The benchmark accepts `--device cpu`, `cuda` or `auto`, and `--gpu-id 0`; `cuda` fails if initialization/computation fails, while `auto` falls back to CPU.

### CUDA path warning

spaCy imports Thinc, which probes an installed CuPy even when the requested inference device is CPU. This can emit `CUDA path could not be detected. Set CUDA_PATH environment variable if CuPy fails to load.` The warning concerns toolkit discovery; it does not by itself mean GPU computation failed. First check the actual computation:

```python
import cupy

print(cupy.cuda.runtime.getDeviceCount())
print(int(cupy.arange(4).sum()))  # 6 verifies allocation, compilation and computation.
```

For an environment that also uses PyTorch, import `torch` before CuPy on Windows so its bundled DLL directories are registered. CUDA 12 component wheels can provide usable libraries without a single toolkit root, so this warning can remain even when the check succeeds. Do not set `CUDA_PATH` to a made-up directory or hide all warnings.

If computation fails and you use a system CUDA Toolkit, point `CUDA_PATH` at its **actual installed root**. Replace the example path below with your installed toolkit directory:

```bash
export CUDA_PATH="/usr/local/cuda-12.8"
export PATH="$CUDA_PATH/bin:$PATH"
python -c "import cupy; print(int(cupy.arange(4).sum()))"
```

These assignments affect only this shell and its child processes. Restart Python after changing discovery settings. See [NVIDIA's Windows toolkit instructions](https://docs.nvidia.com/cuda/cuda-installation-guide-microsoft-windows/index.html) and [CuPy CUDA discovery](https://docs.cupy.dev/en/stable/install.html#working-with-custom-cuda-installation). A CPU-only environment can omit CuPy entirely; selecting CPU does not prevent Thinc from probing an already installed CuPy.

## Benchmark and development

```shell
python -m pip install "gdelt-regkg[benchmark]"
```

Comparing prepared rows does not require NER models or dictionaries. Generating predictions requires the selected field resources. SQLite workspaces, checkpoints and model batching remain configurable; see [benchmark](cli/benchmark.md).

For local development, use `uv sync --inexact --group dev --all-extras`, install the English model and prepare the resources used by integration tests. Install PyTorch separately if testing local translation, and CuPy separately if testing GPU NER. Package-contract tests use authored resources and deterministic backends. See [Contributing](../CONTRIBUTING.md#local-checks).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing feature dependency | Install the extra named by `OptionalDependencyError` in the same environment. |
| Missing PyTorch or CuPy | Follow the separate CPU/CUDA backend commands above. |
| CuPy CUDA path warning | Run the computation check above; check toolkit discovery if it fails. |
| `ResourceUnavailableError` | Build the selected profiles or supply explicit resources. |
| NER/translation model unavailable | Install/download the selected model explicitly. |
| SQLite workspace already in use | Use another benchmark workspace or finish its current owner. |

[API usage](api-usage.md) · [CLI guide](cli/README.md) · [Field documentation](README.md)
