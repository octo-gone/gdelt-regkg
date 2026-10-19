
# GPU setup

GPU acceleration is configured separately for named entity recognition (NER) and translation. spaCy uses CuPy for CUDA inference. M2M100 uses PyTorch. Installing a CUDA-enabled PyTorch build alone does not enable GPU NER.

The library supports Windows, Linux and macOS. The CUDA instructions on this page apply to Windows and Linux with a compatible NVIDIA GPU and driver. GPU backends and installation commands depend on the operating system. CPU execution needs no CuPy or NVIDIA driver.

## Prerequisites

Complete [Installation and setup](../get-started/installation-and-setup.md) for the resources and English model needed by your application. Choose CUDA versions supported by your NVIDIA driver and backend wheels. Use the [PyTorch installation selector](https://pytorch.org/get-started/locally/) and [CuPy installation reference](https://docs.cupy.dev/en/stable/install.html) to check backend requirements.

## Translation backend

For CUDA 12.8 translation, install PyTorch and the translation extras:

```shell
python -m pip install torch --index-url https://download.pytorch.org/whl/cu128
python -m pip install "gdelt-regkg[translate,lang]"
```

For CUDA 13.0, use `https://download.pytorch.org/whl/cu130` instead. If a compatible PyTorch build is installed, install only the feature extras. CuPy is not required for translation.

Verify the backend:

```python
import torch

print(torch.__version__)
print(torch.version.cuda)
print(torch.cuda.is_available())
```

The final line should report `True` for CUDA execution. Download M2M100 weights using the procedure in [Translation](translation.md#download-model-weights), then load the translator with `device="cuda:0", allow_download=False`.

## NER backend and device selection

spaCy NER uses CuPy for CUDA inference. Install `ner`, an English model and CuPy wheel matching your supported CUDA major version. For CUDA 12 on Windows or Linux:

```shell
python -m pip install "gdelt-regkg[ner]" "cupy-cuda12x[ctk]"
python -m spacy download en_core_web_sm
```

For CUDA 13, substitute `"cupy-cuda13x[ctk]"`. The `[ctk]` option installs CUDA component wheels. A compatible NVIDIA driver is still required. With an existing system CUDA Toolkit, the bare `cupy-cuda12x` or `cupy-cuda13x` wheel can use that toolkit instead. See [CuPy installation](https://docs.cupy.dev/en/stable/install.html) for driver and toolkit requirements. Install only one CuPy variant in an environment, including avoiding the source `cupy` package alongside a CUDA wheel. PyTorch is only needed here if you also translate or use a model that requires it.

Select the device **before loading the spaCy model**, then supply the recognizer to generation:

```python
import spacy

from gdelt_regkg import Resources
from gdelt_regkg.fields.ner import SpacyNER

spacy.require_gpu(0)
recognizer = SpacyNER.from_model("en_core_web_sm", resources_dir="local-resources")
resources = Resources(resources_dir="local-resources", recognizer=recognizer)
mentions = recognizer.analyze("Flooding affected London.")
print(mentions)
```

Use `spacy.require_cpu()` before model loading to select CPU explicitly. See [spaCy device selection](https://spacy.io/api/top-level#require_gpu). For benchmark device flags and fallback behavior, see [Benchmark generation](#benchmark-generation).

If your Windows environment also uses PyTorch, import `torch` before spaCy or CuPy to register PyTorch's bundled CUDA DLL directories. PyTorch is not a dependency of the standard spaCy model. The GPU selection applies to the current Python process. Pass the configured `resources` to `generate_gkg` as shown in [Generate records](records.md#generate-a-gkg-record).

For the large English model, install and select `en_core_web_lg` in place of `en_core_web_sm`. [Build GCAM resources](gcam-resources.md#complete-expanded-example) prepares the dictionaries independently of device selection.

## Benchmark generation

Use `--resources-dir local-resources --ner-model en_core_web_lg --device cuda --gpu-id 0` when generating benchmark records with the large model on GPU. `--device cpu` is the default. `cuda` requires successful initialization and computation. `auto` attempts CUDA and reports a CPU fallback when unavailable. The selected device is recorded in `run.md`.

GPU acceleration applies to NER. Dictionary matching, count rules, geographic resolution and metric calculations run on CPU. CPU and GPU model predictions can differ, so their checkpoints are kept separate. See [Benchmarking](benchmarking.md#checkpoints-and-memory) for batches, checkpoints and the compiled-kernel cache.

## CUDA path warning

spaCy imports Thinc, which probes an installed CuPy even when the requested inference device is CPU. This can emit `CUDA path could not be detected. Set CUDA_PATH environment variable if CuPy fails to load.` The warning concerns toolkit discovery. It does not by itself mean GPU computation failed. First check the actual computation:

```python
import cupy

print(cupy.cuda.runtime.getDeviceCount())
print(int(cupy.arange(4).sum()))  # 6 verifies allocation, compilation and computation.
```

CUDA 12 component wheels can provide usable libraries without a single toolkit root, so this warning can occur even when the check succeeds. Do not set `CUDA_PATH` to a made-up directory or hide all warnings.

If computation fails and you use a system CUDA Toolkit, point `CUDA_PATH` at its **actual installed root**. Replace the example path below with your installed toolkit directory:

```bash
export CUDA_PATH="/usr/local/cuda-12.8"
export PATH="$CUDA_PATH/bin:$PATH"
python -c "import cupy; print(int(cupy.arange(4).sum()))"
```

See [NVIDIA's Windows toolkit instructions](https://docs.nvidia.com/cuda/cuda-installation-guide-microsoft-windows/index.html) and [CuPy CUDA discovery](https://docs.cupy.dev/en/stable/install.html#working-with-custom-cuda-installation). A CPU-only environment can omit CuPy entirely. Selecting CPU does not prevent Thinc from probing an already installed CuPy.
