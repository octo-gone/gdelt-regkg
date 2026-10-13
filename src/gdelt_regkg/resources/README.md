# Build inputs

This package directory contains authored rules, schemas, default revision names and source/replay checksums. External dictionaries, geographic references and the GCAM codebook are built into a separate directory. No third-party dictionary notices or vocabularies are shipped here.

See [Installation](../../../docs/installation.md) for package and model setup, [Build resources](../../../docs/cli/build.md) for sources and conversion formats, and [API usage](../../../docs/api-usage.md#resource-and-model-arguments) for resource selection. Runtime directories are selected through `resources_dir=` in Python or `--resources-dir` in the CLI; the default is `local-resources/` under the working directory. Explicit resource objects override the defaults.

Versioned JSON schema identifiers remain unchanged across the package rename, so previously prepared dictionaries and custom rule files remain compatible.
