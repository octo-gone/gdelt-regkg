# Packaged resource inputs

This directory contains authored rules, JSON schemas, build recipes, default revision names and source/replay checksums. External dictionaries, geographic references and the GCAM codebook are built into a separate directory. Third-party dictionary vocabularies are not shipped here.

See [installation](../../../docs/installation.md) for dependencies and models, [resource preparation](../../../docs/guides/resources.md) for builds and resource selection, and [dictionary imports](../../../docs/guides/dictionary-imports.md) for specialized conversion procedures. The [dictionary reference](../../../docs/reference/dictionaries.md) records sources, terms and citations.

Select a runtime resource root with `resources_dir=` in Python or `--resources-dir` in the CLI. The default is `local-resources/` under the working directory; explicit resource objects override directory selections.
