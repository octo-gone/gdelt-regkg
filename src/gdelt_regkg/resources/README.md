# Packaged resource inputs

This directory contains authored rules, JSON schemas, build recipes, default revision names and source/replay checksums. External dictionaries, geographic references and the GCAM codebook are built into a separate directory. Third-party dictionary vocabularies are not shipped here.

See [Installation and setup](../../../docs/get-started/installation-and-setup.md) for dependencies and models and [Build resources](../../../docs/guides/resources.md) for shared builds and resource selection. [Build GCAM resources](../../../docs/guides/gcam-resources.md) covers dictionary presets and customization, [Build gazetteers](../../../docs/guides/gazetteers.md) covers geographic references, and [Dictionary imports](../../../docs/guides/dictionary-imports.md) provides specialized conversion procedures. [Dictionaries](../../../docs/reference/dictionaries.md) records sources, terms and citations.

Select a runtime resource root with `resources_dir=` in Python or `--resources-dir` in the CLI. The default is `local-resources/` under the working directory; explicit resource objects override directory selections.
