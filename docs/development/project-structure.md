# Project structure

The library source is in [`src/gdelt_regkg/`](https://github.com/octo-gone/gdelt-regkg/tree/master/src/gdelt_regkg). Field modules analyze individual GKG fields, and the pipeline combines their results with supplied metadata to produce complete records. Paths in this table are relative to the package directory.

| Path | Responsibility |
| --- | --- |
| `__init__.py` | Exposes the record-generation API, resource configuration and public exceptions. |
| `fields/` | Implements field analyzers, rule loaders, NER, language detection and translation. Import individual analyzers from their field modules. |
| `pipeline.py` | Coordinates analysis, assembles records and provides serialization and output functions. |
| `record.py` | Defines `GKGRecord` and the ordered 27-column GKG contract. |
| `profiles.py` | Defines `Resources`, which selects explicit objects or loads configured defaults when needed. |
| `utils.py` | Resolves local and packaged resource paths and loads resource data. |
| `wire.py` | Parses and serializes count and theme cells using GKG separators. |
| `builders/` | Converts external dictionaries and geographic references into local resource formats. |
| `cli/` | Implements `gdelt-regkg-cli`, including builds, benchmarks and input validation. |
| `benchmark/` | Prepares corpora, compares reconstructed fields with archived GKG values and generates metrics and reports. |
| `scripts/` | Contains tone dictionary refinement, exposed through `gdelt-regkg-cli refine-tone`. |
| `resources/` | Contains authored rules, schemas, build recipes and default revisions. See the [resource overview](https://github.com/octo-gone/gdelt-regkg/blob/master/src/gdelt_regkg/resources/README.md). |

Supporting directories at the repository root:

| Path | Contents |
| --- | --- |
| `tests/` | Automated tests, shared helpers and small fixtures. |
| `docs/` | Setup, task guides, API/CLI and field references, evaluation results and migration instructions. |
| `.github/` | CI and release workflows, maintained scripts, issue forms and the pull request template. |

