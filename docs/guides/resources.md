# Build resources

The library provides prepared build recipes for dictionaries, matching rules and geographic references. Choose a recipe and build its profiles from downloaded or supplied source data. Extraction uses the compiled local profiles and does not download source files.

Use this guide for shared build commands and resource selection. [Build GCAM resources](gcam-resources.md) covers dictionary presets, custom inventories and raw source formats. [Build gazetteers](gazetteers.md) covers geographic reference inputs and custom lookups.

## Select build targets

The `build` subcommand accepts one or more positional targets. Use `all` to build every target, or name only the resources you need:

| Target | Resource |
| --- | --- |
| `tone` | Tone scoring dictionaries |
| `themes` | Theme vocabulary and matching rules |
| `counts` | Authored quantity and event rules |
| `ner` | Name normalization and filtering rules, separate from the recognition model |
| `locations` | A geographic lookup built from reference archives |
| `gcam` | Global Content Analysis Measures dictionaries and lexical scores |

Each selected target produces one profile. A partial build updates that target's selection in `defaults.json` and preserves other selections and previously built files.

Before obtaining source files, review the [dictionary licenses](../reference/dictionaries.md#dictionary-licenses) and [third-party terms](../reference/dictionaries.md#third-party-terms) for every selected dictionary, including those in presets. Sources can have different use and redistribution terms. Download availability does not establish permission for a particular use. Choose source data whose terms fit your analysis.

### Resource arguments

```shell
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
```

Build tone, theme, count and name profiles with `tone themes counts ner`. This selection uses General Inquirer for tone and CrisisLex for themes:

```shell
gdelt-regkg-cli build tone themes counts ner --sources-dir downloads/resources --download-sources --output local-resources
```

Build count and name rules without external sources:

```shell
gdelt-regkg-cli build counts ner --output local-resources
```

Run `gdelt-regkg-cli build --help` for all options. From an installed development checkout, use `uv run gdelt-regkg-cli build ...` or `python -m gdelt_regkg build ...`. Models are installed separately using [Installation and setup](../get-started/installation-and-setup.md).

## Provide source files

Build inputs and compiled outputs have separate directories:

| Argument | Purpose |
| --- | --- |
| `--sources-dir PATH` | Find source files using the recipe's recorded filenames. Explicit downloads are saved here. |
| `--source NAME=PATH` | Supply a particular source file or supported source directory. Repeat for multiple inputs. |
| `--download-sources` | Permit downloads of the recorded inputs required by the selected targets. Requires `--sources-dir`. |
| `--output PATH` | Write compiled profiles and their selections. Defaults to `local-resources/`. |

The resolver selects required inputs from the chosen targets and recipes, including dependencies. An explicit `--source NAME=PATH` takes precedence over discovery in `--sources-dir`. Providing a source path supplies data for a selected build component. It does not select an additional target or dictionary.

For example, supply General Inquirer directly when building tone:

```shell
gdelt-regkg-cli build tone --source general-inquirer=reference/inqtabs.txt --output local-resources
```

Names accepted by `--source` are listed in `build --help`. Raw formats depend on the importer. Follow [Build GCAM resources](gcam-resources.md#provide-source-files) for ZIP, CAT, CSV and other dictionary inputs, or [Build gazetteers](gazetteers.md#build-from-selected-archives) for geographic archives.

### Partial builds and manual downloads

Download source files yourself when a source requires manual acquisition or when preparing an offline environment. Use the filenames in [Resource source files](../reference/dictionaries.md#resource-source-files) and run without a download flag:

```shell
gdelt-regkg-cli build all --sources-dir downloads/resources --output local-resources
```

Raw source files discovered in `--sources-dir` are checked against their recorded hashes unless the recipe marks them as manual inputs. A source checksum mismatch stops the build before compilation. Downloaded sources are also checked before installation. Explicit `--source` inputs allow a custom source edition or location without requiring the recorded hash, while the importer still validates the format. Manual sources follow their importer and edition requirements.

These input checks differ from [compiled-output validation](#inspect-build-outputs): a compiled profile with a different output hash produces a warning, and the build continues. Custom source data or options can produce different compiled contents and coverage.

For WordNet, use the recipe's recorded archive filename when relying on directory discovery. Pass differently named archives or supported extracted directories explicitly. Downloads of the GDELT codebook and geographic archives use their recorded HTTP URLs.

## Recipes and filenames

`--use` selects recipe contents. The default `best` selects the configured default recipe for each target. It does not mean the largest dictionary inventory.

| Target | Default recipe | Other recipes |
| --- | --- | --- |
| `tone` | `v3` | `v1`, `v2` |
| `themes` | `v3` | `v1`, `v2`, `authored` |
| `counts` | `v3` | `v1`, `v2` |
| `ner` | `v1` | — |
| `locations` | `v1` | Custom reference archives are selected separately. |
| `gcam` | `v3` | See the preset table in [Build GCAM resources](gcam-resources.md#choose-a-preset). |

Reproduce earlier tone, theme and count profiles explicitly. These examples require the recorded source files in `downloads/resources/`. Add `--download-sources` to obtain missing inputs:

```shell
gdelt-regkg-cli build tone themes counts --use v1 --sources-dir downloads/resources --output local-resources
gdelt-regkg-cli build tone themes counts --use v2 --sources-dir downloads/resources --output local-resources
gdelt-regkg-cli build tone themes counts --use v3 --sources-dir downloads/resources --output local-resources
```

Tone v1 imports General Inquirer. V2 and v3 replay the recorded edits in order. Theme v1 restores the original candidates and CrisisLex. V2 adds seed rules and v3 applies the evaluated revision. Count recipes select the corresponding authored rule file. Earlier stages can be needed to compute a recipe, but only the requested result is written.

`--use` applies to every target in an invocation. Incompatible target/recipe combinations are rejected before downloading. Build a GCAM-specific preset with the `gcam` target rather than applying that version to `all`.

### Label output files

`--suffix` changes the filename label without changing recipe contents. For example:

```shell
gdelt-regkg-cli build counts --use v1 --suffix experiment --output local-resources
gdelt-regkg-cli build tone --suffix experiment --sources-dir downloads/resources --output local-resources
```

The first command writes `lexicons/counts.experiment.json` from the v1 recipe. The second labels the default tone recipe as `tone.experiment.json`. A label of `v1` would not make the second command use the v1 recipe.

GCAM and gazetteers also accept complete JSON/gzip basenames through `--gcam-filename` and `--gazetteer-filename`. Choose either a complete filename or a suffix. See their build guides for examples.

## Custom profiles

### Build authored rules

Build authored theme, count and name rules without downloading CrisisLex:

```shell
gdelt-regkg-cli build themes counts ner --authored-themes-only --output local-resources/authored
```

For themes alone, use `gdelt-regkg-cli build themes --use authored --output local-resources/authored`. Select this directory with `resources_dir="local-resources/authored"`.

These rules have a different vocabulary from the complete theme profile. Other fields need their resources or explicit objects. Some learned phrases and organization coefficients reflect development-corpus publisher wording, so evaluate them for other domains. `NameRules()` bypasses the learned organization filter. `--authored-themes-only` also removes the CrisisLex requirement when themes are used within GCAM.

### Supply custom configurations

The tone and theme replay recipes require their original source editions. For custom configurations, load compatible `ToneLexicon`, `ThemeLexicon`, `CountRules` or `NameRules` objects explicitly. [Resource selection](#resource-selection) shows how to combine them.

For dictionaries selected individually or imported from your own files, follow [Build GCAM resources](gcam-resources.md#customize-a-preset). For different geographic references, follow [Build gazetteers](gazetteers.md#build-from-selected-archives).

Keep source inputs, generated profiles and development data separate from held-out benchmark articles. Evaluate changed profiles on a fresh reserved sample. Broader vocabulary or geographic coverage does not guarantee closer agreement. For changes to the library and its test suite, see [Development setup](../development/setup.md#local-checks).

## Inspect build outputs

Build progress is written to stderr, including source resolution, compilation and publication. The final `Built ...` summary is written to stdout. Each target's output is selected in `defaults.json` after its files are published.

Recorded output hashes from `recipes.json` are compared with compiled JSON independently of filename labels. A mismatch prints a warning and the build continues, since custom inputs or options can produce different outputs. Matching hashes appear in progress output. Custom recipes without a recorded hash are not compared. Hashes cover parsed JSON, including metadata and array order, without depending on indentation, object-key order or gzip compression.

### Output layout

| Directory / file | Contents | Needed during extraction |
| --- | --- | --- |
| `downloads/resources/` | Original dictionaries, WordNet inputs, annotations and reference GKG ZIPs | No. Keep them for reproducible rebuilding. |
| `local-resources/lexicons/` | Compiled field profiles, including GCAM dictionaries and geographic lookups | Yes, for the selected fields. |
| `local-resources/gcam/` | Codebook and coverage reports when included in the build | For construction and benchmark coverage statistics. |
| `local-resources/schemas/` | Editor-validation schemas | Optional. |
| `local-resources/defaults.json` | Selected profile filename for each resource | Yes, when using directory defaults. |

## Resource selection

Extraction and benchmark generation select prepared profiles with `--resources-dir`, which defaults to `local-resources`. In Python, use `Resources(resources_dir="local-resources")`. Paths are relative to the working directory unless absolute paths are supplied.

For custom rule files, prepare `counts.json` and `themes.json` using the packaged [JSON schemas](https://github.com/octo-gone/gdelt-regkg/tree/master/src/gdelt_regkg/resources/schemas), then load them explicitly:

```python
from gdelt_regkg import Resources
from gdelt_regkg.fields.rule_inputs import load_count_rules, load_theme_lexicon

custom = Resources(
    resources_dir="local-resources",
    count_rules=load_count_rules("counts.json"),
    theme_lexicon=load_theme_lexicon("themes.json"),
)
```

Explicit objects override directory defaults. Resources load only when required. Authored counts and name rules have packaged fallbacks. Schema IDs and recipes identify resource formats and revisions.

Compiled default profiles are cached by resolved path. Reload explicit objects or restart after editing a cached profile in place. Caller-supplied recognizers retain their own name rules and model settings. See [Performance](performance.md) for reuse and caching.
