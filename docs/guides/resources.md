# Prepare and select resources

Build external dictionaries and geographic references once, then select the resulting local profiles from Python or the CLI. Extraction uses prepared resources and does not download source files.

## Resource arguments

The `build` subcommand uses positional targets and repeatable named source inputs.

```shell
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
gdelt-regkg-cli build counts ner --output local-resources
gdelt-regkg-cli build themes --authored-themes-only --output local-resources
gdelt-regkg-cli build tone --source general-inquirer=downloads/resources/inqtabs.txt --output local-resources
```

Use `gdelt-regkg-cli build --help` for all build options. From a checkout, use
`uv run gdelt-regkg-cli build ...` or `python -m gdelt_regkg build ...` in an
environment where the package is installed.

Choose the targets explicitly, or use `all`; output defaults to `local-resources/`.
The resolver selects inputs required by the targets, including GCAM's theme
dependencies. Explicit `--source NAME=PATH` inputs take precedence over files discovered in
`--sources-dir`; discovered files are checked against the recorded recipe.
Downloads require `--download-sources`. Counts and name rules need no external
sources; `--authored-themes-only` also removes the CrisisLex requirement for themes
and their use within GCAM. Use `--gazetteer-archives` for explicit location-reference
inputs.

Each selected target produces exactly one profile. The default `--use best`
selects the current supported recipe, and partial builds preserve unrelated
`defaults.json` selections. Previous files are available when you build another
recipe into the same directory; only the newly built profile becomes selected.

Build progress appears immediately on stderr: source checks and downloads, each
target and GCAM component, and output preparation and publication. The final
`Built ...` summary is written to stdout.

Builds also compare recorded output hashes from `recipes.json` with the compiled
JSON, independently of `--suffix` or filename overrides. A mismatch prints a
warning and the build continues; custom inputs or options may legitimately differ.
Matching hashes appear in progress output. Custom recipes without a recorded hash
are not compared. Hashes cover parsed JSON, including metadata and array order,
and do not depend on indentation, object key order, or gzip compression.

## Recipes and filenames

`--use` determines the contents. `--suffix` changes only the filename label,
preserving the resource stem and `.json` or `.json.gz` extension. For example,
`build tone --use v1 --suffix experiment` writes `lexicons/tone.experiment.json`
using the v1 recipe. Labeling a current build `v1` does not turn it into the v1 recipe.

| Target | Default recipe | Other recipes |
| --- | --- | --- |
| `tone` | `v3` | `v1`, `v2` |
| `themes` | `v3` | `v1`, `v2`, `authored` |
| `counts` | `v3` | `v1`, `v2` |
| `ner` | `v1` | — |
| `locations` | `v1` | — |
| `gcam` | `v3` | `v1`, `v2`, `v4`, `v5`, `full` (alias for `v5`) |

Rebuild the historical profiles explicitly (the source directory must contain
the recorded input files; add `--download-sources` to fetch missing inputs):

```shell
gdelt-regkg-cli build tone themes counts gcam --use v1 --suffix v1 --sources-dir downloads/resources
gdelt-regkg-cli build tone themes counts gcam --use v2 --suffix v2 --sources-dir downloads/resources
gdelt-regkg-cli build tone themes counts gcam --use v3 --suffix v3 --sources-dir downloads/resources
```

Or request one resource and one recipe:

```shell
gdelt-regkg-cli build counts --use v1 --suffix baseline
gdelt-regkg-cli build tone --suffix experiment --sources-dir downloads/resources
gdelt-regkg-cli build themes --use authored --suffix custom
```

Tone v1 imports General Inquirer; v2 and v3 replay the recorded edits in order.
Theme v1 restores the original candidates and CrisisLex; v2 adds the seed rules;
v3 applies the evaluated revision. Count recipes select the corresponding authored
rule file. Earlier stages may be needed to compute a recipe, but only the requested
result is written. `--use` applies to every target in that invocation; incompatible
target/recipe combinations are rejected before downloading.

Extraction and benchmark commands select prepared profiles with `--resources-dir` (default `local-resources`); explicit per-file overrides take precedence. Build commands select raw files with `--sources-dir` or individual source flags and write to `--output`.

## GCAM profiles and expansion

| Recipe | Dictionaries |
| --- | --- |
| `v1` | General Inquirer subset |
| `v2` | Adds VADER |
| `v3` | Adds General Inquirer categories, WordNet and themes; default |
| `v4` | Adds Roget and Lexicoder |
| `v5` | 2,597 compiled dimensions: 2,328 source-backed and 269 approximations |
| `full` | Alias for `v5` |

```shell
gdelt-regkg-cli build gcam --use full --sources-dir downloads/resources --download-sources --output local-resources
```

The selected profile is written to `lexicons/gcam.v5.json.gz` and selected in `defaults.json`. Its inventory covers 2,296 English and 301 non-English dimensions, including 268 authored theme approximations and one French imagery approximation. These rules preserve existing theme matches and context guards; they do not recover GDELT's production vocabulary. Source metadata and the coverage report identify the approximations separately, including one French imagery dimension. `full` aliases this broadest preset and does not imply complete coverage. Versioned recipes write `gcam.v1.json`, `gcam.v2.json`, or `gcam.vN.json.gz` for `v3` and later. Use a version number to keep the recipe fixed.

### Add dictionaries

For a complete setup with v5, LIWC, MPQA and GPU NER, use the [TL;DR installation commands](../installation.md#tldr-expanded-coverage-and-gpu).

`--gcam-add` adds or replaces dictionaries using component names from the [dictionary reference](../reference/dictionaries.md). A baseline requires only the sources for the additions:

```shell
gdelt-regkg-cli build gcam --gcam-baseline local-resources/lexicons/gcam.v5.json.gz --gcam-add liwc subjectivity --source liwc=reference/LIWC2007.dic --source subjectivity=reference/subjclueslen1-HLTEMNLP05.tff --sources-dir downloads/resources --output local-resources/custom
```

Customized builds write `gcam.custom.json.gz`. `--suffix` changes its label; `--gcam-filename` chooses a complete JSON/gzip basename. Use one naming option per build. Builds with a codebook also write `gcam/coverage.LABEL.json`, listing compiled and missing dimensions by dictionary and language, acquired source components, and deferred languages. Runtime analysis selects only applicable languages.

`--source NAME=PATH` supplies a local source edition. `--source wordnet-annotations=PATH` supplies shared Affect, Domains and SentiWords inputs. For separate files, use `--source wordnet-affect=PATH`, `wordnet-domains=PATH` or `sentiwords=PATH`. Affect matching can be configured with `--affect-propagate-hierarchy` and `--affect-nouns-only`.

## Custom gazetteer

```shell
gdelt-regkg-cli build locations --gazetteer-archives reference/first.gkg.csv.zip reference/second.gkg.csv.zip --gazetteer-name my-places --suffix custom --output local-resources
```

Use `--gazetteer-name` to name the profile and `--suffix` to label its filename.
`--gazetteer-filename` accepts a complete basename when you need JSON instead of
gzip. Complete GCAM and gazetteer filenames accept `.json` or `.json.gz`; use
either a complete filename or a suffix.

## Output layout

| Directory / file | Contents | Needed during extraction |
| --- | --- | --- |
| `downloads/resources/` | Original dictionaries, WordNet archives, annotations and reference GKG ZIPs | No; keep them for reproducible rebuilding |
| `local-resources/lexicons/` | Compiled tone, theme, count, name, geographic and GCAM profiles | Yes |
| `local-resources/gcam/` | Compiled native GCAM codebook and build coverage reports | Only for construction and benchmark coverage statistics |
| `local-resources/schemas/` | Editor-validation schemas | Optional |
| `local-resources/defaults.json` | Selected profile revision for each field | Yes |

## Broader GCAM coverage

`--use v4` adds two optional dictionaries and expands GCAM coverage from 809 to 1,855 of 2,888 dimensions (28.01% to 64.23%). Dimension coverage is independent of extraction accuracy.

| Filename | Obtain from | Contribution |
| --- | --- | --- |
| `Roget.zip` | [Roget download](https://provalisresearch.com/Download/Roget.zip), [dictionary information](https://www.kovcomp.co.uk/wordstat/Roget.html) | 1,042 native Roget categories |
| `LSDaug2015.zip` | [Lexicoder publisher](https://www.snsoroka.com/data-lexicoder/) | Four native Lexicoder categories; obtain authorization for the intended use |

> [!WARNING]
> Review [Lexicoder's agreement](https://www.snsoroka.com/s/LSDagreement.pdf) before downloading it. If its terms do not fit your use, omit Lexicoder; Roget alone reaches 1,851 of 2,888 dimensions (64.09%).

**Accepted source formats**

| Source | Accepted input |
| --- | --- |
| Roget | ZIP or extracted directory |
| WordNet | TAR or extracted dictionaries |
| Lexicoder | ZIP, a directory containing `LSD2015.lc3` and `LSD2015_NEG.lc3`, or four-category JSON |
| VADER | Supply a vocabulary file with `--source vader=PATH`; the VADER library does not become a runtime dependency |

Compiled GCAM and gazetteer loaders accept JSON or gzip profiles. Original source archives are not needed during extraction, which never downloads these files.

See [GCAM profiles and expansion](#gcam-profiles-and-expansion) for full-profile and incremental build commands.

`--use full --download-sources` (or `--use v5`) builds 2,597 English and native-language dimensions, including 268 authored theme approximations and one French imagery approximation. The preset downloads English/Catalan/Spanish/Galician ML-SENTICON, Spanish ANEW, five translated RID editions and eleven non-English labMT lists. Chinese labMT is compiled; analyzing Chinese text requires the `build` extra for Jieba segmentation. See [ANEW report conversion](dictionary-imports.md#anew-report-conversion) for its optional PDF dependency, [GCAM source formats](dictionary-imports.md#gcam-source-formats) for manual inputs and the [dictionary reference](../reference/dictionaries.md) for acquisition links and licenses.

## Geographic reference files

### How the default gazetteer works

The reference GKG ZIPs build a **gazetteer**: a lookup of place names, country and administrative codes, coordinates and GDELT feature IDs. The builder reads the enhanced location cells. It does not retrieve articles or train the NER model. These setup downloads are separate from the archives you would use to benchmark extraction.

The recorded recipe uses 20 files from **2015–2019** to reproduce the geographic profile evaluated in the research. Their age is not a requirement of GKG processing. The profile contains only places found in those files, so it can miss newer place names, administrative changes and less-covered regions. Newer and more varied reference files can expand it, but change the measured configuration.

> [!NOTE]
> The default lookup is a limited reference profile, not a comprehensive worldwide gazetteer.
>
> - NER can recognize other places, but a name with no matching lookup entry produces an `unknown-place` diagnostic and is omitted from both GKG location columns. Its geography is also unavailable to counts.
> - Raw recognized spans are available through `NERResult.locations`.
> - There is no automatic geocoding fallback.
> - For broad coverage, supply a more comprehensive compatible gazetteer. Adding sampled GKG files alone cannot guarantee coverage of all places.

Use [Custom gazetteer](#custom-gazetteer) to build from selected archives. The build selects the result in `defaults.json`; Python callers can also pass a `Gazetteer` object explicitly through the [API](#resource-selection).

## Partial builds and manual downloads

**Build only the profiles you need.** Tone, themes, counts and names need General Inquirer and CrisisLex, with no GCAM or geographic downloads:

```shell
gdelt-regkg-cli build tone themes counts ner --sources-dir downloads/resources --download-sources --output local-resources
```

This subset cannot produce default geographic or GCAM fields until their resources are added. Authored counts, name rules, dates, amounts and quotations work without external dictionaries. Standalone analyzers accept explicitly loaded profiles.

**Download source files manually.** Save the exact filenames listed in [Resource source files](../reference/dictionaries.md#resource-source-files) into `downloads/resources/`, then run the build without the download flag:

```shell
gdelt-regkg-cli build all --sources-dir downloads/resources --output local-resources
```

- Rename manually downloaded WordNet archives to the filenames shown in the table.
- Files whose hashes differ from the recorded ones are rejected, to preserve the recorded configuration.
- To use files stored elsewhere, pass `--source NAME=PATH` (repeat as needed), or `--gazetteer-archives` for GKG ZIP files. Run `gdelt-regkg-cli build --help` for all options and [build examples](#resource-arguments).
- Downloads of GDELT archives and the codebook use HTTP.

## Custom profiles

You can build and evaluate custom profiles with the installed library. Keep source inputs, generated profiles and development data separate from the reserved benchmark. For changes to the library itself and its test suite, see [Contributing](https://github.com/octo-gone/gdelt-regkg/blob/master/CONTRIBUTING.md#local-checks).

**Build authored rules only.** This builds the authored theme, count and name rules in a separate directory, without downloading CrisisLex:

```shell
gdelt-regkg-cli build themes counts ner --authored-themes-only --output local-resources/authored
```

Select the result with `resources_dir="local-resources/authored"`. Note:

- Theme metrics differ from the complete profile, and other fields still need resources or explicit objects.
- Some learned phrases and organization coefficients reflect development-corpus publisher wording, so other domains need separate evaluation.
- `NameRules()` bypasses the learned organization filter.

See [resource selection](#resource-selection).

**Use other dictionaries.** The recorded tone and theme replay recipes require their original source editions. For other GCAM dictionaries, use `gdelt-regkg-cli build gcam --source NAME=PATH` with the selected profile or additions. You can also pass explicit `ToneLexicon`, `ThemeLexicon`, `CountRules`, `NameRules`, `Gazetteer` and `GCAMLexicon` objects. Obtain geographic development and reference archives separately from held-out articles.

Always evaluate changed profiles on a fresh reserved sample: broader coverage does not guarantee more accurate counts.

## Resource selection

For custom files, prepare `counts.json` and `themes.json` using the packaged [JSON schemas](https://github.com/octo-gone/gdelt-regkg/tree/master/src/gdelt_regkg/resources/schemas). Then load explicit objects:

```python
from gdelt_regkg import Resources
from gdelt_regkg.fields.rule_inputs import load_count_rules, load_theme_lexicon

custom = Resources(
    resources_dir="local-resources",
    count_rules=load_count_rules("counts.json"),
    theme_lexicon=load_theme_lexicon("themes.json"),
)
```

Explicit objects override directory defaults. Resources load only when required. The default root is `local-resources/` relative to the working directory. External dictionaries must be prepared locally; extraction does not fetch resources. Authored counts and name rules have packaged fallback. Schema IDs and build recipes identify the resource format and revision.

Compiled default profiles are cached by resolved path. Reload explicit objects or restart after editing a cached profile in place. Caller-supplied recognizers retain their own name rules and model settings.

See [dictionary sources and terms](../reference/dictionaries.md) and [specialized dictionary imports](dictionary-imports.md).
