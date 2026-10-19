# Installation and setup

The library supports Windows, Linux and macOS and requires Python 3.12 or newer. The core installation has no third-party runtime dependencies:

```shell
python -m pip install gdelt-regkg
```

Dates, amounts, quotations and authored counts work without natural language processing (NLP) backends. Tone, themes and [Global Content Analysis Measures (GCAM)](concepts-and-glossary.md#gcam-and-dimensions) need prepared dictionaries. Install the features you use:

## Optional dependencies

| Extra | Capability |
| --- | --- |
| `build` | Dictionary builders using pypdf, pypdfium2, Pillow, pytesseract and Jieba. |
| `ner` | spaCy adapters for NER. Install an English model separately. |
| `translate` | Transformers and SentencePiece for M2M100 translation. Install PyTorch separately. |
| `lang` | Lingua language detection and label verification, with no PyTorch requirement. |
| `benchmark` | Article retrieval and statistical benchmark dependencies. |
| `all` | All feature extras listed above. |

> [!IMPORTANT]
> Feature extras, including `all`, do not install PyTorch, CuPy or model weights. Translation uses PyTorch. GPU NER uses CuPy. Install the backend and models required by your workflow using [Translation](../guides/translation.md#setup) or [GPU setup](../guides/gpu-setup.md).

Missing feature dependencies raise `OptionalDependencyError` naming the extra. Missing models and dictionaries produce separate model or resource errors. See [Troubleshooting](../guides/troubleshooting.md) for diagnosis. French imagery PDF conversion also needs [Tesseract](../guides/dictionary-imports.md#french-imagery-pdf-conversion), install it separately.

## Basic English setup

Install the English recognizer and small model, then build the standard dictionaries and geographic reference:

```shell
python -m pip install "gdelt-regkg[ner]"
python -m spacy download en_core_web_sm
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
```

Downloads occur only during explicit setup. Extraction uses local resources and model weights. Select another resource directory through `Resources(resources_dir=path)` or the command-line interface (CLI) option `--resources-dir`.

> [!WARNING]
> Review external [source terms](../reference/dictionaries.md#third-party-terms) before downloading dictionaries or models. Select sources whose terms permit your intended use.

Run [Quickstart](quickstart.md) to extract an individual field and write a complete [Global Knowledge Graph (GKG)](concepts-and-glossary.md#gkg) record. [Build resources](../guides/resources.md) explains profiles, source selection and custom builds.

## English models

Use `SpacyNER.from_model("en_core_web_sm")` for the small English model. To use the large model from the published English evaluation, install it explicitly:

```shell
python -m spacy download en_core_web_lg
```

Select it with `SpacyNER.from_model("en_core_web_lg", resources_dir="local-resources")`. The factory's `resources_dir=` selects name rules. A supplied spaCy pipeline retains its own policy. Models are installed separately from the package.

For GPU execution, complete [GPU setup](../guides/gpu-setup.md) and select the device before loading the model.

## Choose the next step

- [Build GCAM resources](../guides/gcam-resources.md) covers presets, custom dictionaries and a complete expanded example with its dimension coverage.
- [Build gazetteers](../guides/gazetteers.md) covers default and custom geographic reference lookups. They are required for settigns geographic-related fields.
- [Translation](../guides/translation.md#setup) covers language detection, M2M100 model setup and non-English articles.
- [GPU setup](../guides/gpu-setup.md) covers CUDA backends, device selection and computation checks.
- [Troubleshooting](../guides/troubleshooting.md) covers missing dependencies, models, resources and workspace conflicts.

## Benchmark and development

```shell
python -m pip install "gdelt-regkg[benchmark]"
```

Comparing existing records does not require NER models or extraction dictionaries. Generating reconstructed records requires the resources used by each field. The benchmarking CLI uses SQLite workspaces, checkpoints and model batching. Follow [Benchmarking](../guides/benchmarking.md) for the complete workflow.

For development dependencies and integration-test resources, follow [Development setup](../development/setup.md).
