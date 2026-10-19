# Build GCAM resources

Global Content Analysis Measures (GCAM) dictionaries describe emotional, psychological and topical language through category counts and lexical scores. The library provides prepared presets and importers for individual dictionaries. Build a preset, customize its inputs, extend a compiled profile, or start with an empty profile and select only the dictionaries you need.

Presets are build recipes. The vocabulary is compiled locally from downloaded or supplied source data. See [Build resources](resources.md) for shared build arguments and directory selection, and [Dictionaries](../reference/dictionaries.md) for what each dictionary measures and where to obtain it.

## Choose a preset

Review the [dictionary licenses](../reference/dictionaries.md#dictionary-licenses) and [third-party terms](../reference/dictionaries.md#third-party-terms) for every selected source, including sources within a preset. Licenses and acquisition requirements differ across dictionaries. Some require manually obtained files or permission for the intended use. Select individual dictionaries when a preset includes sources you cannot use.

| Preset | Inventory | Compiled dimensions with recorded sources | Output under `lexicons/` |
| --- | --- | ---: | --- |
| `v1` | Eight General Inquirer categories | 8 / 2,888 | `gcam.v1.json` |
| `v2` | v1 plus VADER lexical scores | 9 / 2,888 | `gcam.v2.json` |
| `v3` | Expanded General Inquirer, WordNet families, themes and VADER. Default for `best`. | 809 / 2,888 | `gcam.v3.json.gz` |
| `v4` | v3 plus Roget and Lexicoder sentiment | 1,855 / 2,888 | `gcam.v4.json.gz` |
| `v5` | v4 plus RID editions, financial and moral dictionaries, sentiment ratings, additional WordNet scores and authored approximations | 2,597 / 2,888 | `gcam.v5.json.gz` |
| `full` | Alias for v5 | Same as v5 | `gcam.v5.json.gz` |

The published GCAM agreement metrics evaluate v4. V5 expands the representable inventory to 2,296 English and 301 non-English dimensions. Its 2,597 dimensions consist of 2,328 source-backed dimensions, 268 authored theme approximations and one French imagery approximation. The [dictionary overview](../reference/dictionaries.md#dictionary-overview) lists the individual families included in v5 and the optional imports. Coverage describes the available categories, independently of extraction agreement. See [Results](../evaluation/results.md#gcam).

Install the dependencies for your selected inputs using [Installation and setup](../get-started/installation-and-setup.md#optional-dependencies). V5 includes French imagery PDF conversion, which needs the `build` extra and Tesseract, unless you provide compatible converted data. See [Dictionary imports](dictionary-imports.md#french-imagery-pdf-conversion).

For example, build the v5 preset with explicit permission to download its recorded sources:

```shell
gdelt-regkg-cli build gcam --use v5 --sources-dir downloads/resources --download-sources --output local-resources
```

Use `--use v3` for the default configuration or `--use v4` for the evaluated inventory. Build GCAM as its own target when selecting these presets. The `--use` argument applies to every target in an invocation, and other targets do not support every GCAM version. `full` does not imply complete native coverage.

## Provide source files

There are three ways to obtain inputs for the selected preset or components:

- Put recorded source files in `--sources-dir`, using the filenames in [Resource source files](../reference/dictionaries.md#resource-source-files).
- Add `--download-sources` to fetch required recorded sources where automatic acquisition is supported. Download flags require `--sources-dir`. Manual sources need their own acquisition steps.
- Supply files or supported extracted directories through repeatable `--source NAME=PATH` arguments.

Explicit source paths take precedence over directory discovery. Discovered non-manual files are checked against recorded source hashes. An explicit source can use a different edition or custom data, but must satisfy the selected importer's format and category mapping. Build metadata records source hashes, and custom inputs can differ from the recorded configuration.

Supplying `--source` provides data for a selected component. It does not enable another dictionary. Select the dictionary through a preset or `--gcam-add`. Unused source arguments are rejected. Use component names listed by `build --help`, rather than numeric GCAM dictionary IDs, for `--gcam-add`.

### Raw dictionary formats

Supported formats depend on the dictionary. A file extension alone does not identify a usable source.

| Component / source name | Accepted input and structure |
| --- | --- |
| `general-inquirer` | Basic TSV with `Entry` and the required category columns. |
| `vader` | UTF-8 vocabulary text with tab-separated terms and numeric mean valence. |
| `roget` | Original ZIP or extracted directory. Also requires WordNet 3.1 and the codebook. |
| `lexicoder` | ZIP or directory containing `LSD2015.lc3` and `LSD2015_NEG.lc3`, or four-category JSON. |
| `rid`, `rid-french`, `forest-values`, `body-boundary` | Supported CAT data in a source ZIP, extracted directory or CAT file. Supply CAT and EXC together in a ZIP or directory to import exclusions. Language editions have specific encodings. |
| `hogenraad-motive`, `time`, `temperament` | Compatible CAT data or category JSON mapped to the dictionary's native categories. |
| `moral-foundations` | A dictionary in LIWC-style `.dic` format, with category definitions and term/category mappings, or category JSON. |
| `loughran-mcdonald` | Master CSV with its word and sentiment-category columns. |
| `subjectivity` | MPQA TFF clues, ZIP, TGZ or extracted directory. |
| `liwc` | Compatible English LIWC 2007 `.dic`. Newer editions are not interchangeable. |
| `central-bank` | XLSX dictionary appendix or category JSON. |
| `anew`, `ml-senticon`, `french-imagery` | Dictionary-specific rating CSVs or their supported original formats. Each has required columns and score scales. |

For example, these argument fragments supply three different raw formats after their components are selected:

```text
--gcam-add rid --source rid=reference/RID.ZIP
--gcam-add forest-values --source forest-values=reference/forest.cat
--gcam-add loughran-mcdonald --source loughran-mcdonald=reference/master-dictionary.csv
```

Most category importers also require the native codebook, resolved through `--sources-dir`, `--download-sources` or `--source codebook=PATH`. WordNet components need their corresponding dictionary editions and annotations. `--source wordnet-annotations=PATH` supplies shared Affect, Domains and SentiWords inputs. Use `wordnet-affect`, `wordnet-domains` or `sentiwords` for separate inputs. Affect imports also accept `--affect-propagate-hierarchy` and `--affect-nouns-only`.

See [Dictionary imports](dictionary-imports.md#gcam-source-formats) for category JSON, CSV columns, original file structures and conversion procedures. Arbitrary CSV layouts and unknown dictionary selectors are not imported automatically. For an authored vocabulary, prepare compatible compiled GCAM JSON as described under [authored lexicons](#authored-lexicons).

## Customize a preset

Use `--gcam-add` to import additional dictionaries alongside the chosen preset. Supply their files with `--source`, or obtain them through supported acquisition steps. This example adds a compatible Forest Values CAT file to v3:

```shell
gdelt-regkg-cli build gcam --use v3 --gcam-add forest-values --source forest-values=reference/forest.cat --sources-dir downloads/resources --download-sources --output local-resources
```

The preset's inputs are still required. The CAT file supplies the added dictionary, and automatic acquisition resolves the other required sources. The result is `lexicons/gcam.custom.json.gz` and is selected in `defaults.json`.

To use a custom source for a dictionary already included in a preset, pass its `--source NAME=PATH` argument. No additional `--gcam-add` is needed. For example, v5 already selects `loughran-mcdonald`, so its source can be replaced with a compatible master CSV. Use `--suffix` to give that variant a distinct filename.

When importing into a compiled profile, most components replace their dictionary's dimensions and exclusions, including stale entries from the previous import. General Inquirer components merge their mapped categories and preserve the baseline categories they are designed to retain. Adding a component is not a general union of all old and new vocabulary.

## Extend a compiled profile

Use `--gcam-baseline` to start from an existing compiled JSON or gzip profile. Only the sources required by the additions are needed. The original raw files used to build the baseline are not required.

For example, after building v5, obtain the MPQA Subjectivity TFF file using [Dictionaries](../reference/dictionaries.md#dictionary-12), then add it:

```shell
gdelt-regkg-cli build gcam --gcam-baseline local-resources/lexicons/gcam.v5.json.gz --gcam-add subjectivity --source subjectivity=reference/subjclueslen1-HLTEMNLP05.tff --sources-dir downloads/resources --output local-resources
```

This example uses the codebook already acquired for the v5 build. For a baseline obtained elsewhere, supply the required codebook or permit its download. The output is `lexicons/gcam.custom.json.gz`.

Choose either `--gcam-baseline` or an explicit versioned `--use`, not both. Without a baseline, the selected preset is built before additions are applied. With a baseline, additions are applied directly to that compiled profile.

## Build only selected dictionaries

An empty compiled profile provides a starting point without preset dictionaries. Save this as `empty-gcam.json`:

```json
{"name": "custom", "dimensions": []}
```

For a small example, save the following two tab-separated lines as `vader_lexicon.txt`. This authored sample demonstrates the input format and is not the published VADER vocabulary:

```tsv
good	2.0
bad	-2.0
```

Build a profile containing only that lexical scoring component:

```shell
gdelt-regkg-cli build gcam --gcam-baseline empty-gcam.json --gcam-add vader --source vader=vader_lexicon.txt --output local-resources/selected
```

The result is `local-resources/selected/lexicons/gcam.custom.json.gz`, selected by that directory's `defaults.json`. This build needs neither General Inquirer nor a codebook. It performs no downloads. For an analysis, obtain the full vocabulary from [Dictionaries](../reference/dictionaries.md#dictionary-26) and supply its path instead.

Select other supported components through `--gcam-add` and provide their required sources and dependencies. This is also the way to construct an inventory that omits dictionaries from a preset. Runtime options such as `disabled_dictionaries`, `gcam_disabled_dictionaries` and benchmark `--gcam-disable` exclude dictionaries during analysis or scoring. They do not select the contents of a resource build. See [GCAM](../reference/fields/gcam.md#select-dictionaries) for runtime selection.

### Authored lexicons

For vocabulary that does not match an existing importer, prepare JSON following the [GCAM lexicon schema](https://github.com/octo-gone/gdelt-regkg/blob/master/src/gdelt_regkg/resources/schemas/gcam-lexicon.schema.json). Compatible compiled profiles can be loaded with `GCAMLexicon.from_json` or used as `--gcam-baseline`. They are distinct from raw category JSON accepted by particular importers. See [GCAM](../reference/fields/gcam.md#custom-lexicons) for words, patterns, weighted maps and language metadata.

## Complete expanded example

This procedure builds the other standard resources and a v5 GCAM profile with optional Linguistic Inquiry and Word Count (LIWC) 2007 and MPQA Subjectivity dictionaries. It compiles 2,673 of the 2,888 dimensions in the native codebook. It includes English and native-language dimensions. Each analysis scores only applicable languages.

### Expanded setup prerequisites

- Python 3.12 or newer and the `build` extra for dictionary conversion.
- [Tesseract](dictionary-imports.md#french-imagery-pdf-conversion) installed and available on `PATH` for French imagery conversion.
- An authorized English LIWC 2007 dictionary saved as `downloads/resources/LIWC2007_English.dic`.

The commands download the other required sources, including the optional GPL-3.0 MPQA mirror. Review the [source terms](../reference/dictionaries.md#third-party-terms) for all selected dictionaries first.

### Build the expanded profile

```shell
python -m pip install "gdelt-regkg[build]"
tesseract --version
gdelt-regkg-cli build all --sources-dir downloads/resources --download-sources --output local-resources
gdelt-regkg-cli build gcam --use v5 --gcam-add liwc --source liwc=downloads/resources/LIWC2007_English.dic --download-mpqa --sources-dir downloads/resources --download-sources --output local-resources
```

The first build prepares standard field resources. The second writes `lexicons/gcam.custom.json.gz` and selects it in `local-resources/defaults.json`. `--download-mpqa` both selects the `subjectivity` component and explicitly permits its mirror download. With a local MPQA file, use `--gcam-add liwc subjectivity` and supply both source paths instead.

GCAM building does not need an English recognition model. To also use the large English model from the published record-generation evaluation, install it separately:

```shell
python -m pip install "gdelt-regkg[ner]"
python -m spacy download en_core_web_lg
```

Device selection and dictionary selection are independent. Follow [GPU setup](gpu-setup.md) for accelerated inference and [Translation](translation.md#setup) for translation dependencies and model weights.

### Understand the coverage counts

| Configuration | Source-backed dimensions | Authored theme approximations | French imagery approximation | Total compiled dimensions |
| --- | ---: | ---: | ---: | ---: |
| v5 | 2,328 | 268 | 1 | 2,597 |
| v5 + LIWC 2007 + MPQA | 2,404 | 268 | 1 | 2,673 |

LIWC adds 62 source-backed dimensions and MPQA adds 14. Both configurations contain 269 approximations: 268 authored theme dimensions and one French imagery dimension estimated from class midpoints. A category's count and value keys count as one dimension. Complete source dictionaries are required to obtain these totals.

The published agreement metrics evaluate v4. Agreement for this expanded configuration has not been established. See [Results](../evaluation/results.md#gcam).

## Inspect and use the result

Preset outputs use the filenames in the [preset table](#choose-a-preset). Builds with `--gcam-add`, `--gcam-baseline` or Affect variant options default to `gcam.custom.json.gz`. An explicit raw-source override alone uses the selected preset's filename. Choose `--suffix LABEL` for a distinct label or `--gcam-filename NAME` for a complete `.json` or `.json.gz` basename. These two naming options are mutually exclusive.

The build selects the resulting filename in `defaults.json`. Builds that include a codebook also write `gcam/codebook.v1.json` and `gcam/coverage.LABEL.json`. The VADER-only example has no codebook and does not produce those coverage files. Coverage reports list compiled, source-backed, approximate and missing dimensions, languages and source components. They describe representable vocabulary, independently of accuracy.

To load a compiled profile explicitly:

```python
from gdelt_regkg.fields.gcam import GCAMLexicon, analyze_gcam

lexicon = GCAMLexicon.from_json("local-resources/lexicons/gcam.custom.json.gz")
result = analyze_gcam("Good good bad.", lexicon=lexicon)
print(result.to_gkg())
```

### Select resources for generation

For record generation, use the selected directory profile or pass an explicit lexicon through `Resources(gcam_lexicon=lexicon)`. After the complete setup and large-model installation above:

```python
from gdelt_regkg import Resources
from gdelt_regkg.fields.ner import SpacyNER

resources = Resources(
    resources_dir="local-resources",
    recognizer=SpacyNER.from_model("en_core_web_lg", resources_dir="local-resources"),
)
```

Pass `resources` to `generate_gkg` using [Generate records](records.md#generate-a-gkg-record). For GPU execution, select the device before loading the recognizer. Non-English GCAM dimensions need original-language text and its language alongside the prepared English body, as described in [Translation](translation.md#native-language-gcam). Chinese scoring also needs Jieba through the `build` extra.
