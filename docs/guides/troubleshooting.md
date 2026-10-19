# Troubleshooting

Check dependencies, model weights and resource profiles in the Python environment running the application. They are separate inputs: installing a feature extra does not download its models or compile its dictionaries.

## Missing optional dependency

`OptionalDependencyError` names the required extra. Install it in the same environment as the library, for example:

```shell
python -m pip install "gdelt-regkg[ner]"
```

Check the [optional dependencies](../get-started/installation-and-setup.md#optional-dependencies) for each feature. Translation also needs PyTorch, and CUDA named entity recognition (NER) needs CuPy. Use [Translation](translation.md#setup) or [GPU setup](gpu-setup.md) for backend installation and verification.

## Missing English model

The `ner` extra installs the spaCy adapter. Install the model selected by your application:

```shell
python -m spacy download en_core_web_sm
```

Use `en_core_web_lg` instead if your configuration selects the large model. Run the download in the application's Python environment. See [English models](../get-started/installation-and-setup.md#english-models) for model and name-policy selection.

## Missing translation weights

M2M100 model weights require an explicit download. Follow [Download model weights](translation.md#download-model-weights), then use `allow_download=False` or a local snapshot directory during extraction. A missing local model is distinct from a missing PyTorch or Transformers installation.

## Missing resource profile

For `ResourceUnavailableError`, check the selected `resources_dir`, the compiled files and the profiles selected in `defaults.json`. Relative resource paths are resolved from the application's working directory. Build the selected profiles or pass explicit resource objects:

```shell
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
```

See [Build resources](resources.md#resource-selection) for directory selection and explicit overrides. Original downloaded source files are needed for builds, not for extraction from compiled profiles.

## CUDA initialization or path warning

Run the actual computation checks in [GPU setup](gpu-setup.md#cuda-path-warning). A toolkit-discovery warning can occur even when computation succeeds. On Windows, an environment that also uses PyTorch may need `torch` imported before spaCy or CuPy to register its DLL directories.

Check your driver and installed CuPy variant before changing `CUDA_PATH`. Point it only at a real toolkit root when using a system toolkit. The GPU guide includes the diagnostic commands and platform references.

## Benchmark workspace already in use

The benchmark owns an exclusive workspace lock. Finish the process using that workspace or select another workspace for a concurrent writer. A shared translation-cache database has different ownership rules. See [Performance](performance.md#connection-and-workspace-ownership) for connection lifetime and [Benchmarking](benchmarking.md#checkpoints-and-memory) for checkpoint handling.

## Incomplete record

Strict generation raises `IncompleteGKGError` when required fields are unavailable. Supply the missing inputs, models or resources. An unavailable field (`None`) differs from an available field with no matches (an empty string). Empty media lists and `extras={}` explicitly declare available empty metadata. See [Generate records](records.md#generate-a-gkg-record) for strict generation and export behavior.
