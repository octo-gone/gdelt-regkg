# Installation

Requires Python 3.12 or newer. The core installation has no third-party runtime dependencies:

```shell
python -m pip install gdelt-regkg
```

Dates, amounts, quotations and authored counts work without NLP backends. Tone, themes and GCAM need prepared dictionaries. Install the features you use:

| Extra | Capability |
| --- | --- |
| `build` | Dictionary build dependencies: pypdf, pypdfium2, Pillow, pytesseract and Jieba; French OCR also needs the Tesseract engine installed separately |
| `ner` | spaCy adapters; install an English model separately |
| `translate` | Transformers and SentencePiece for M2M100 translation; install PyTorch separately |
| `lang` | Lingua language detection and label verification; no PyTorch required |
| `benchmark` | Article retrieval and statistical benchmark dependencies |
| `all` | All feature extras above; install PyTorch, CuPy and model weights separately as needed |

> [!IMPORTANT]
> Feature extras, including `all`, do not install PyTorch, CuPy or model weights. Install PyTorch separately for M2M100 translation and CuPy for GPU NER, then obtain the models required by your workflow.

Missing feature dependencies raise `OptionalDependencyError` naming the extra. Missing models and dictionaries produce separate model/resource errors. For French imagery PDF conversion, follow the [Tesseract installation instructions](guides/dictionary-imports.md#french-imagery-pdf-conversion).

## Basic English setup

```shell
python -m pip install "gdelt-regkg[ner]"
python -m spacy download en_core_web_sm
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
```

Downloads occur only during explicit setup. Extraction uses local resources and model weights. Select another root through `Resources(resources_dir=path)` or CLI `--resources-dir`.

> [!WARNING]
> Review external [source terms](reference/dictionaries.md#third-party-terms) before downloading dictionaries or models. Select sources whose terms permit your intended use.

## TL;DR: expanded coverage and GPU

Use GCAM v5 with LIWC and MPQA for the broadest currently verified dictionary inventory, and `en_core_web_lg` for the large English NER model used in the [published evaluation](evaluation/results.md#study-configuration).

Prerequisites:

- Python 3.12+ on Windows or Linux, with an NVIDIA driver compatible with CUDA 12.8.
- [Tesseract](guides/dictionary-imports.md#french-imagery-pdf-conversion) installed and available on `PATH`.
- An authorized **English LIWC 2007** dictionary saved as `downloads/resources/LIWC2007_English.dic`; newer editions are not interchangeable.

The commands download the other required sources, including the optional GPL-3.0 MPQA mirror. Review their [source terms](reference/dictionaries.md#third-party-terms) first.

```shell
python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
python -m pip install "gdelt-regkg[all]" "cupy-cuda12x[ctk]"
python -m spacy download en_core_web_lg
tesseract --version
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
gdelt-regkg-cli build gcam --use v5 --gcam-add liwc --source liwc=downloads/resources/LIWC2007_English.dic --download-mpqa --sources-dir downloads/resources --download-sources --output local-resources
python -c "import torch, cupy; print('PyTorch CUDA:', torch.cuda.is_available()); print('CuPy devices:', cupy.cuda.runtime.getDeviceCount()); print('CuPy computation:', int(cupy.arange(4).sum()))"
```

The GPU check should report `True`, at least one CuPy device and a sum of `6`. The second build writes `lexicons/gcam.custom.json.gz` and selects it in `local-resources/defaults.json`. With complete source dictionaries, the inventory contains **2,673 of 2,888 dimensions**: **2,404 source-backed** and **269 approximations**. This includes native-language dimensions; each analysis scores only applicable languages. Coverage does not establish extraction accuracy.

Select the GPU and large model in your application before loading the recognizer:

```python
import torch
import spacy

from gdelt_regkg import Resources
from gdelt_regkg.fields.ner import SpacyNER

spacy.require_gpu(0)
resources = Resources(
    resources_dir="local-resources",
    recognizer=SpacyNER.from_model("en_core_web_lg", resources_dir="local-resources"),
)
```

Importing `torch` first registers its CUDA DLL directories on Windows. Pass `resources` to [`generate_gkg`](guides/records.md#generate-a-gkg-record); device selection applies to the current Python process. For benchmark generation, use `--resources-dir local-resources --ner-model en_core_web_lg --device cuda --gpu-id 0`.

For translation, download the default M2M100 weights once on GPU:

```shell
python -c "from gdelt_regkg.fields.translation import M2M100Translator; M2M100Translator.from_model(device='cuda:0', allow_download=True)"
```

Use `device="cuda:0", allow_download=False` when loading the translator afterwards. See [translation](guides/translation.md) for the complete pipeline, or [GPU inference](#gpu-inference) for other CUDA installations and troubleshooting.

## English models

Use `SpacyNER.from_model("en_core_web_sm")` or install and select `en_core_web_lg` for the larger model. `resources_dir=` on the factory selects name rules; a supplied pipeline retains its own policy. Models are installed separately from the package.

## Non-English articles

Language detection alone needs only the `lang` extra:

```shell
python -m pip install "gdelt-regkg[lang]"
```

Install PyTorch separately for M2M100 translation. Choose one CPU or CUDA build for your environment. For CPU translation:

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

Translation requires M2M100 weights. Load with `allow_download=True` once to explicitly permit downloading; afterwards use `allow_download=False` or a local snapshot directory. See [translation](guides/translation.md) for inference, language labels and record provenance, and [performance](guides/performance.md#gpu-inference) for device selection. Preserve the analyzed English body because enhanced offsets index it.

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

For an environment that also uses PyTorch, import `torch` before CuPy on Windows so its bundled DLL directories are registered. CUDA 12 component wheels can provide usable libraries without a single toolkit root, so this warning can occur even when the check succeeds. Do not set `CUDA_PATH` to a made-up directory or hide all warnings.

If computation fails and you use a system CUDA Toolkit, point `CUDA_PATH` at its **actual installed root**. Replace the example path below with your installed toolkit directory:

```bash
export CUDA_PATH="/usr/local/cuda-12.8"
export PATH="$CUDA_PATH/bin:$PATH"
python -c "import cupy; print(int(cupy.arange(4).sum()))"
```

See [NVIDIA's Windows toolkit instructions](https://docs.nvidia.com/cuda/cuda-installation-guide-microsoft-windows/index.html) and [CuPy CUDA discovery](https://docs.cupy.dev/en/stable/install.html#working-with-custom-cuda-installation). A CPU-only environment can omit CuPy entirely. Selecting CPU does not prevent Thinc from probing an already installed CuPy.

## Benchmark and development

```shell
python -m pip install "gdelt-regkg[benchmark]"
```

Benchmarking specifically does not require NER models or dictionaries. However, some fields generation requires additional resources. Benchamrking CLI uses SQLite workspaces, checkpoints and model batching; see [benchmark](guides/benchmarking.md).

For development dependencies and integration-test resources, follow [Contributing](https://github.com/octo-gone/gdelt-regkg/blob/master/CONTRIBUTING.md#local-checks).

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Missing feature dependency | Install the extra named by `OptionalDependencyError` in the same environment. |
| Missing PyTorch or CuPy | Follow the separate CPU/CUDA backend commands above. |
| CuPy CUDA path warning | Run the computation check above; check toolkit discovery if it fails. |
| `ResourceUnavailableError` | Build the selected profiles or supply explicit resources. |
| NER/translation model unavailable | Install/download the selected model explicitly. |
| SQLite workspace already in use | Use another benchmark workspace or finish its current owner. |

[Quickstart](quickstart.md) · [CLI reference](reference/cli.md) · [Field reference](reference/fields/README.md)
