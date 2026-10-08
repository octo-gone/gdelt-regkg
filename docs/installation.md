# Installation

`gdelt-regkg` generates GDELT GKG records from prepared English article text. This guide explains how to install the package, build the local resources it needs, and run a first extraction.

**Contents**

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick start (basic English setup)](#quick-start-basic-english-setup)
- [Configuring resources and models](#configuring-resources-and-models)
- [Advanced setup](#advanced-setup)
- [Complete pipeline example](#complete-pipeline-example)
- [Benchmarking](#benchmarking)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Reference](#reference)

## Overview

### What the library needs

The library analyzes **prepared English article bodies**. Which resources you need depends on the output fields you want:

| Output | Requires |
| --- | --- |
| Tone, themes, GCAM | Dictionaries (built locally) |
| Locations | Geographic reference records (a *gazetteer*) and an English NER model |
| Persons, organizations, places, broad names | An English NER model |
| Dates, amounts, quotations | Nothing beyond the package |

Two things are outside the scope of normal extraction:

- **Translation.** Non-English bodies must be translated into English first (see [Non-English articles](#non-english-articles)).
- **Retrieval.** The library does not fetch article bodies. You supply the text and metadata.

### Offline operation and licensing

External dictionaries, geographic records and the GCAM codebook are downloaded and converted **locally**, because their terms differ from the software license. The package itself provides extraction code, schemas, authored count/name rules and reproducible build recipes.

Extraction is fully offline: it never downloads missing dictionaries or models. Downloads happen only during setup, when you explicitly request them.

### Choose a setup

| Setup | Requirements | Result |
| --- | --- | --- |
| [Basic English](#quick-start-basic-english-setup) | Small English NER model and standard dictionaries | All text fields; 809 of 2,888 GCAM dimensions (28.01%) |
| [Best supported](#best-supported-setup) | Large NER model; optional Roget/Lexicoder dictionaries; translation backend for non-English bodies | Documented large-model configuration; up to 1,855 of 2,888 GCAM dimensions (64.23%) |
| [Benchmarking](#benchmarking) | Saved article bodies and matching original GKG archives; retrieval dependencies for collecting new samples | Agreement measurements against native GKG fields |
| [Development](#development) | Source inputs and separate development/validation samples | Custom rules and resource rebuilding |

## Prerequisites

- **Python 3.12 or newer.**
- **pip.** The examples use `python -m pip`; other package managers work too.
- **Internet access during setup only** (package, model and resource downloads).
- **A virtual environment (recommended).** Install everything into one environment and use it for all later commands:

  ```shell
  python -m venv .venv
  source .venv/bin/activate        # Windows: .venv\Scripts\activate
  ```

## Quick start (basic English setup)

This setup uses the small spaCy English model and the standard dictionaries.

### 1. Install the package and the NER model

Install both in the same Python environment:

```shell
python -m pip install gdelt-regkg
python -m spacy download en_core_web_sm
```

The second command installs spaCy's compatible small English model. The measured configuration uses the 3.8.0 models with spaCy 3.8. Model weights are installed separately because PyPI does not accept direct URL dependencies in package extras. English extraction needs no PyTorch or translation weights.

### 2. Build the resources

Choose a directory for the generated profiles (here, `local-resources`). The following command downloads the recorded source files, verifies their SHA-256 hashes, and builds the dictionaries used for tone, themes, GCAM and geographic resolution:

```shell
gdelt-regkg-build-resources --sources-dir downloads/resources --download-sources --output local-resources
```

> **Before you run this:** review the [third-party terms](#third-party-terms). Downloaded dictionaries keep their own licenses.

The build also downloads reference GKG archives to create the gazetteer; see [Geographic reference files](#geographic-reference-files) for their purpose and limitations.

**Directory layout after setup**

| Directory / file | Contents | Needed during extraction |
| --- | --- | --- |
| `downloads/resources/` | Original dictionaries, WordNet archives, annotations and reference GKG ZIPs | No; keep them for reproducible rebuilding |
| `local-resources/lexicons/` | Compiled tone, theme, count, name, geographic and GCAM profiles | Yes |
| `local-resources/gcam/` | Compiled native GCAM codebook | Only for construction and benchmark coverage statistics |
| `local-resources/schemas/` | Editor-validation schemas | Optional |
| `local-resources/defaults.json` | Selected profile revision for each field | Yes |

**What gets built**

- Tone v1–v3, themes v1–v3, counts v1–v3, name rules v1 and GCAM v1–v3.
- The 17,177-record geographic profile.
- `defaults.json` selects the measured revisions.

Dates, amounts and quotations need no additional dictionaries. Locations share the NER step with persons, organizations and all names, then resolve each span against the geographic reference.

### 3. Generate a GKG record

Save the following as `extract_article.py`. It analyzes one English body and writes a complete GKG row.

```python
from gdelt_regkg import SpacyNER, generate_gkg, write_gkg

resources_dir = "local-resources"
ner = SpacyNER.from_model("en_core_web_sm", resources_dir=resources_dir)
record = generate_gkg(
    "Volunteers rescued 12 people in Paris, France.",
    identifier="https://example.org/story",
    batch_time="20250101120000",
    sequence=1,
    resources_dir=resources_dir,
    ner=ner,
    sharing_image="",
    related_images=[],
    social_image_embeds=[],
    social_video_embeds=[],
    extras={},
    strict=True,
)
with open("article.gkg.csv", "w", encoding="utf-8", newline="") as stream:
    write_gkg([record], stream)
```

Run it in the environment where you installed the library:

```shell
python extract_article.py
```

### 4. Check the result

`article.gkg.csv` contains one headerless, tab-delimited record with all 27 GKG columns. The `.csv` extension follows GDELT naming conventions.

When processing many articles, load the NER model and resource profiles once and reuse them.

## Configuring resources and models

- **Resource location.** The default is `local-resources/` relative to the working directory. Library loaders accept `resources_dir=`; the command-line extraction and benchmark tools use `--resources-dir`.
- **Explicit objects win.** Lexicon, rule and gazetteer objects passed directly override directory defaults.
- **No environment variables.** There is no environment-based resource configuration.
- **Caching.** Load models and profiles once and reuse them. If you edit cached files in place, reload your custom objects or restart the process.
- **Missing resources** raise `ResourceUnavailableError` with setup instructions.

See the [API arguments](usage.md#resource-and-model-arguments) for details.

## Advanced setup

### Best supported setup

Keep the basic resources and install a larger English NER model.

```shell
python -m spacy download en_core_web_lg   # large model (documented configuration)
python -m spacy download en_core_web_md   # medium model (alternative)
```

Weights are installed into the active Python environment; no manual file placement is needed. NER models run on CPU by default, and English extraction needs no PyTorch.

Select the model explicitly. Installing a larger model does not change the default small model:

```python
ner = SpacyNER.from_model("en_core_web_lg", resources_dir="local-resources")
```

A larger model does not improve every field. On the reserved English sample, person F1 is 0.6701 with the large model, but organization F1 is slightly higher with the small one (0.4402 versus 0.4277). See [Version 0.7.0](../CHANGELOG.md#seasonal-benchmark).

### Broader GCAM coverage

Adding two optional dictionaries expands GCAM coverage from 809 to 1,855 of 2,888 dimensions (28.01% to 64.23%). Dimension coverage is independent of extraction accuracy.

| Filename | Obtain from | Contribution |
| --- | --- | --- |
| `Roget.zip` | [Roget download](https://provalisresearch.com/Download/Roget.zip), [dictionary information](https://www.kovcomp.co.uk/wordstat/Roget.html) | 1,042 native Roget categories |
| `LSDaug2015.zip` | [Lexicoder publisher](https://www.snsoroka.com/data-lexicoder/) | Four native Lexicoder categories; obtain authorization for the intended use |

> **Licensing:** review [Lexicoder's agreement](https://www.snsoroka.com/s/LSDagreement.pdf) before downloading it. If its terms do not fit your use, omit Lexicoder; Roget alone reaches 1,851 of 2,888 dimensions (64.09%).

**Option A: download automatically.** Downloads occur only when you pass the flags, and checksums are verified. WordNet 3.1 is already present from the basic setup.

```shell
gdelt-regkg-expand-gcam --resources-dir local-resources --sources-dir downloads/resources --download-roget --download-lexicoder --wordnet-31 downloads/resources/wn3.1.dict.tar.gz --output local-resources/gcam-full.json
```

To add Roget only, omit `--download-lexicoder`. Existing ZIPs are checksum-checked and reused.

**Option B: use files you already have.** Here the original ZIPs are stored under `downloads/resources/`:

```shell
gdelt-regkg-expand-gcam --resources-dir local-resources --roget-source downloads/resources/Roget.zip --wordnet-31 downloads/resources/wn3.1.dict.tar.gz --lexicoder-source downloads/resources/LSDaug2015.zip --output local-resources/gcam-full.json
```

Omit `--lexicoder-source` if you are not using Lexicoder.

**Use the expanded profile** by loading it and passing it to the generator. The standard profile stays selected unless you override it:

```python
from gdelt_regkg import GCAMLexicon

gcam = GCAMLexicon.from_json("local-resources/gcam-full.json")
# then: generate_gkg(..., gcam_lexicon=gcam)
```

**Accepted source formats**

| Source | Accepted input |
| --- | --- |
| Roget | ZIP or extracted directory |
| WordNet | TAR or extracted dictionaries |
| Lexicoder | ZIP, a directory containing `LSD2015.lc3` and `LSD2015_NEG.lc3`, or four-category JSON |
| VADER | An installed VADER library can supply its vocabulary file to `--vader-source`; it does not become a runtime dependency |

Compiled GCAM and gazetteer loaders accept JSON or gzip profiles. Original source archives are not needed during extraction, which never downloads these files.

### Non-English articles

Detect the language and translate to English **before** extraction. The library's local translation backend, M2M100 418M, needs PyTorch and model weights.

#### Install PyTorch

Choose the PyTorch build for your hardware **before** running a translation example. The default library installation does not install or replace PyTorch; if a compatible build is already installed, keep it.

```shell
# GPU (CUDA 13.0; requires a compatible NVIDIA GPU and driver)
python -m pip install "torch>=2.13" --index-url https://download.pytorch.org/whl/cu130

# CPU only
python -m pip install "torch>=2.13" --index-url https://download.pytorch.org/whl/cpu
```

See the [PyTorch installation guide](https://pytorch.org/get-started/locally/) for other platforms.

#### About the `cpu`, `cu128` and `cu130` extras

These extras declare a PyTorch requirement, but they do not choose the build: with `pip`, the **index URL** decides between CPU and CUDA wheels.

| Extra | Notes |
| --- | --- |
| `cpu`, `cu130` | Also require patched setuptools. Preferred. |
| `cu128` | Older option for compatible environments. Its latest PyTorch wheel is 2.11.0 and it requires setuptools below 82, so it cannot include either the PyTorch 2.13.0 JIT fix or the setuptools 83.0.0 packaging fix. |

See the [translation API](fields/translation-info.md#local-translation).

#### Model weights

- Weights are stored in the Hugging Face cache, normally `~/.cache/huggingface/hub`.
- Set `allow_download=False` once the weights are downloaded.
- To use another location, pass a complete local snapshot directory as `model=`.
- Use `device="cpu"` with the CPU PyTorch build.

A working end-to-end example is in the [complete pipeline](#complete-pipeline-example).

### Geographic reference files

#### How the default gazetteer works

The reference GKG ZIPs build a **gazetteer**: a lookup of place names, country and administrative codes, coordinates and GDELT feature IDs. The builder reads the enhanced location cells. It does not retrieve articles or train the NER model. These setup downloads are separate from the archives you would use to benchmark extraction.

The recorded recipe uses 20 files from **2015–2019** to reproduce the geographic profile evaluated in the research. Their age is not a requirement of GKG processing. The profile contains only places found in those files, so it can miss newer place names, administrative changes and less-covered regions. Newer and more varied reference files can expand it, but change the measured configuration.

> **The default lookup is a limited reference profile, not a comprehensive worldwide gazetteer.**
>
> - NER can recognize other places, but a name with no matching lookup entry produces an `unknown-place` diagnostic and is omitted from both GKG location columns. Its geography is also unavailable to counts.
> - Raw recognized spans remain available through `NERResult.locations`.
> - There is no automatic geocoding fallback.
> - For broad coverage, supply a more comprehensive compatible gazetteer. Adding sampled GKG files alone cannot guarantee coverage of all places.

#### Build a custom gazetteer

1. Download selected GKG ZIPs from [GDELT](http://data.gdeltproject.org/gdeltv2/masterfilelist.txt). Keep them separate from held-out benchmark articles.
2. Build a profile (multiple archive paths are accepted):

   ```shell
   gdelt-regkg-build-gazetteer reference/recent.gkg.csv.zip --output local-resources/locations-custom.json.gz
   ```

3. Pass the resulting lookup explicitly:

   ```python
   from gdelt_regkg import Gazetteer, SpacyNER, generate_gkg

   places = Gazetteer.from_json("local-resources/locations-custom.json.gz")
   ner = SpacyNER.from_model("en_core_web_sm")
   record = generate_gkg(
       "Volunteers rescued 12 people in Paris, France.",
       identifier="https://example.org/story",
       batch_time="20250101120000",
       sequence=1,
       ner=ner,
       resources_dir="local-resources",
       gazetteer=places,
       sharing_image="",
       related_images=[],
       social_image_embeds=[],
       social_video_embeds=[],
       extras={},
       strict=True,
   )
   ```

### Partial builds and manual downloads

**Build only the profiles you need.** Tone, themes, counts and names need General Inquirer and CrisisLex, with no GCAM or geographic downloads:

```shell
gdelt-regkg-build-resources --fields tone themes counts ner --sources-dir downloads/resources --download-sources --output local-resources
```

This subset cannot produce default geographic or GCAM fields until their resources are added. Authored counts, name rules, dates, amounts and quotations work without external dictionaries. Standalone analyzers accept explicitly loaded profiles.

**Download source files manually.** Save the exact filenames listed in [Resource source files](#resource-source-files) into `downloads/resources/`, then run the build without the download flag:

```shell
gdelt-regkg-build-resources --sources-dir downloads/resources --output local-resources
```

- Rename manually downloaded WordNet archives to the filenames shown in the table.
- Files whose hashes differ from the recorded ones are rejected, to preserve the recorded configuration.
- To use files stored elsewhere, pass explicit arguments such as `--tone-source`, `--crisislex-source`, `--wordnet-31` and `--gazetteer-archives`. Run `gdelt-regkg-build-resources --help` for the full list.
- Downloads of GDELT archives and the codebook use HTTP.

## Complete pipeline example

This example combines language detection, optional translation, English NER and the broader GCAM profile. It assumes you have built the [full GCAM profile](#broader-gcam-coverage).

Save it as `extract_articles.py`, and replace the example bodies, URLs, titles and timestamps with your prepared article text and real metadata.

Notes on behavior:

- All enhanced offsets refer to the **English body that was analyzed**.
- Supplied titles keep their original language.
- Detection uncertainty or translation failure raises an error. The source body is never silently processed as English.

```python
from pathlib import Path

from gdelt_regkg import (
    CachedTranslator,
    GCAMLexicon,
    LinguaDetector,
    M2M100Translator,
    SpacyNER,
    detect_language,
    generate_gkg,
    translate_text,
    write_gkg,
)

output = Path("output")
output.mkdir(parents=True, exist_ok=True)

# Pass the same resource directory to the model and row generator.
resources_dir = Path("local-resources")
ner = SpacyNER.from_model("en_core_web_lg", resources_dir=resources_dir)
gcam = GCAMLexicon.from_json("local-resources/gcam-full.json")
detector = LinguaDetector()
translator = None  # Load the translation model only if an article needs it.

articles = [
    {
        "url": "https://example.org/noticia",
        "published_at": "20261001090023",
        "title": "Ayuda para las familias afectadas",
        "body": (
            "El gobierno de España anunció nuevas medidas para ayudar a las "
            "familias afectadas por las inundaciones. Las autoridades enviaron "
            "doce camiones con alimentos y agua potable a las ciudades dañadas. "
            "Los servicios de emergencia continúan buscando a las personas desaparecidas."
        ),
    },
    {
        "url": "https://example.org/story",
        "published_at": "20261001090512",
        "title": "Flood relief reaches residents",
        "body": (
            "The French government sent 12 trucks carrying food and drinking "
            "water to residents affected by flooding. Emergency services are "
            "searching for missing people and providing shelter for families."
        ),
    },
]

try:
    with (output / "articles.gkg.csv").open("w", encoding="utf-8", newline="") as stream:
        for sequence, article in enumerate(articles, start=1):
            body = article["body"]
            detection = detect_language(body, detector=detector)
            print(article["url"], detection.language)
            source_language = translation_engine = None

            if detection.language != "eng":
                if translator is None:
                    backend = M2M100Translator.from_model(
                        model="facebook/m2m100_418M",
                        revision="55c2e61bbf05dfb8d7abccdc3fae6fc8512fd636",  # Evaluated weights.
                        device="cuda",  # Use "cpu" with the CPU PyTorch build.
                        allow_download=True,  # First run; set False after downloading.
                        batch_size=4,
                        num_beams=4,
                    )
                    translator = CachedTranslator(backend, output / "translations.sqlite")

                prepared = translate_text(
                    body,
                    language=detection.language,
                    translator=translator,
                    language_detector=detector,
                    language_check="all",
                )
                body = prepared.text
                source_language = prepared.source_language
                translation_engine = prepared.engine

            # NER runs on this English body; all enhanced offsets refer to it.
            (output / f"analyzed-body-{sequence}.txt").write_text(body, encoding="utf-8")
            record = generate_gkg(
                body,
                identifier=article["url"],
                published_at=article["published_at"],
                batch_time="20261001091500",  # Shared GKG batch timestamp, in UTC.
                sequence=sequence,
                ner=ner,
                resources_dir=resources_dir,
                gcam_lexicon=gcam,
                source_language=source_language,
                translation_engine=translation_engine,
                sharing_image="",  # Supply collected media URLs when available.
                related_images=[],
                social_image_embeds=[],
                social_video_embeds=[],
                extras={"PAGE_TITLE": article["title"]},
                strict=True,
            )
            write_gkg([record], stream)
finally:
    if translator is not None:
        translator.close()
```

Run it in the installed environment:

```shell
python extract_articles.py
```

**Outputs:** headerless GKG TSV (`output/articles.gkg.csv`), the analyzed English bodies, and a translation cache when translation was needed.

**Adapting the example for basic English extraction:** use `en_core_web_sm`, remove the `GCAMLexicon` load and the `gcam_lexicon=` argument, and omit the translation code. The standard profile is selected through `resources_dir=`.

## Benchmarking

Benchmarking measures agreement with GDELT's native fields. Use the same dictionaries and model as for extraction.

### Requirements

- **Retrieval dependencies**, only if you collect full text from publisher URLs:

  ```shell
  python -m pip install "gdelt-regkg[benchmark]"
  ```

- **PyTorch and translation weights**, only if you collect non-English articles ([setup](#non-english-articles)).
- **Inputs:** a JSONL corpus (analyzed text, URL, status and original record ID) and original GKG ZIP archives containing those exact ID/URL pairs. The collection tools produce the required corpus format.

Benchmarks on an already saved corpus need neither retrieval nor translation weights.

### Benchmark a saved corpus

```shell
gdelt-regkg-benchmark-fields --resources-dir local-resources --corpus benchmark/retained-english.jsonl --archives benchmark/original.gkg.csv.zip --ner-model en_core_web_lg --gcam-lexicon local-resources/gcam-full.json --bootstrap-samples 1000 --output benchmark/fields-report.json
gdelt-regkg-benchmark-extraction --resources-dir local-resources --corpus benchmark/retained-english.jsonl --archives benchmark/original.gkg.csv.zip --ner-model en_core_web_lg --sample-size 1000000 --per-source 1000000 --output benchmark/extraction-report
```

Replace the paths with your files, and list all matching archives after `--archives`.

| Command | Evaluates |
| --- | --- |
| `gdelt-regkg-benchmark-fields` | Locations, dates, amounts, all names, quotations and GCAM, without retrieval or fitting |
| `gdelt-regkg-benchmark-extraction` | Persons, organizations, counts, themes and tone |

Useful options:

- `--fields-only` skips GCAM; `--gcam-only` skips NER.
- `--include-translated` accepts saved translated English bodies without translating them.
- High sampling limits (as above) keep the whole available corpus instead of requesting new articles.

### Collect new samples

1. **Write a sampling plan** and save it as `sample-plan.json`. Use separate dates for development and benchmarking:

   ```json
   {
     "seed": 1729,
     "utc_windows": ["001500", "084500", "163000"],
     "english_per_window": 90,
     "translated_per_window": 10,
     "per_source_per_day": 2,
     "development": {"days": ["20240110", "20240710"]},
     "benchmark": {"days": ["20250211", "20250811"]}
   }
   ```

2. **Collect development articles first**, then exclude their URLs when collecting the reserved benchmark:

   ```shell
   gdelt-regkg-benchmark-samples --resources-dir local-resources --plan sample-plan.json --split development --cohort english --output samples/development
   gdelt-regkg-benchmark-samples --resources-dir local-resources --plan sample-plan.json --split benchmark --cohort english --exclude-manifest samples/development/manifest.json --exclude-corpus samples/development/results.jsonl --output samples/benchmark
   ```

3. **Handle translated articles separately.** Use `--cohort translated` to collect source-language bodies, then translate them and save their analyzed English text before field benchmarking.

The example plan samples winter and summer dates at several UTC times. These windows describe *collection* times, not publication times; sampling only around midnight can underrepresent topics and regions. See the [collection arguments](../scripts/README.md#seasonal-sample-collection).

### Good practice

- Keep development, validation and benchmark data separate, and do not tune against the benchmark.
- Add any earlier corpora to the exclusion arguments, and check body hashes for duplicate articles published under different URLs.
- Publisher bodies retrieved today can differ from GDELT's original text and lower F1 even when extraction is correct on the retrieved body. Report retrieval failures, translation differences and input lengths alongside agreement.

Further reading: [Changelog](../CHANGELOG.md) and [current metrics](README.md#agreement-with-gdelt).

## Development

You can build and evaluate custom profiles with the installed library. Keep source inputs, generated profiles and development data separate from the reserved benchmark. For changes to the library itself and its test suite, see [Contributing](../CONTRIBUTING.md#local-checks).

**Build authored rules only.** This builds the authored theme, count and name rules in a separate directory, without downloading CrisisLex:

```shell
gdelt-regkg-build-resources --fields themes counts ner --authored-themes-only --output local-resources/authored
```

Select the result with `resources_dir="local-resources/authored"`. Note:

- Theme metrics differ from the complete profile, and other fields still need resources or explicit objects.
- Some learned phrases and organization coefficients reflect development-corpus publisher wording, so other domains need separate evaluation.
- `NameRules()` bypasses the learned organization filter.

See [custom rules](usage.md#custom-resources).

**Use other dictionaries.** The recorded tone and theme replay recipes require their original source editions. For other dictionaries, use the standalone importers or pass explicit `ToneLexicon`, `ThemeLexicon`, `CountRules`, `NameRules`, `Gazetteer` and `GCAMLexicon` objects. Obtain geographic development and reference archives separately from held-out articles.

Always evaluate changed profiles on a fresh reserved sample: broader coverage does not guarantee more accurate counts.

## Troubleshooting

| Symptom | Likely cause and fix |
| --- | --- |
| `ResourceUnavailableError` | Resources were not built, or `resources_dir=` / `--resources-dir` points to the wrong directory. Run the [resource build](#2-build-the-resources) and check the path. |
| A place is missing from the GKG location columns (`unknown-place` diagnostic) | The place is not in the gazetteer. Use a [more comprehensive gazetteer](#build-a-custom-gazetteer). Raw spans remain in `NERResult.locations`. |
| Source file rejected during build | Its hash differs from the recorded one. Download the exact edition listed in [Resource source files](#resource-source-files). |
| Language-detection or translation error | Expected behavior: non-English bodies are never processed as English. Check the language, the [translation setup](#non-english-articles), and the PyTorch build. |
| Edited a resource file but output is unchanged | Profiles are cached. Reload custom objects or restart the process. |

## Reference

### Resource source files

The build downloads these files automatically with `--download-sources`. For manual downloads, use the exact filenames below.

| Filename | Obtain from | Purpose |
| --- | --- | --- |
| `inqtabs.txt` | [General Inquirer basic TSV](https://inquirer.sites.fas.harvard.edu/inqtabs.txt) | Tone and General Inquirer GCAM categories |
| `CrisisLexRec.txt` | [CrisisLexRec](https://raw.githubusercontent.com/sajao/CrisisLex/master/data/CrisisLexLexicon/CrisisLexRec.txt) | Crisis-related theme phrases |
| `vader_lexicon.txt` | `vaderSentiment/vader_lexicon.txt` inside the [vaderSentiment 3.3.2 wheel](https://pypi.org/project/vaderSentiment/3.3.2/#files) | VADER GCAM scores; setup extracts this member without installing the library |
| `GCAM-MASTER-CODEBOOK.TXT` | [GDELT master codebook](http://data.gdeltproject.org/documentation/GCAM-MASTER-CODEBOOK.TXT) | Native category IDs and coverage denominator |
| `wn3.1.dict.tar.gz` | [WordNet 3.1](https://wordnetcode.princeton.edu/wn3.1.dict.tar.gz) | Lexical categories and morphology |
| `wn2.0.tar.gz` | [WordNet 2.0](https://wordnetcode.princeton.edu/2.0/WordNet-2.0.tar.gz) | Domains synset mapping |
| `wn1.6.tar.gz` | [WordNet 1.6](https://wordnetcode.princeton.edu/1.6/wn16.unix.tar.gz) | Affect synset mapping |
| `wndomains-mirror.zip` | [Domains/Affect mirror](https://codeload.github.com/larsmans/wordnet-domains-sentiwords/zip/refs/heads/master), [publisher](https://wndomains.fbk.eu/download.html) | Domains 3.2 and Affect 1.1 annotations |
| Twenty reference `*.gkg.csv.zip` archives | Exact HTTP URLs in [recipes.json](../src/gdelt_regkg/resources/recipes.json) | GKG place names, codes, coordinates and feature IDs; see [Geographic reference files](#geographic-reference-files) |

### Third-party terms

MIT applies to this project's code and original rules. Downloaded dictionaries, models, article bodies and source-derived profiles retain their own terms. When distributing generated profiles, obtain permission where required and retain the upstream notices that apply to those files.

| Source | Terms and attribution |
| --- | --- |
| General Inquirer | Philip J. Stone and contributors; Harvard IV-4 and Lasswell dictionaries. Academic research is permitted; commercial use, including modified categories, requires permission. [Publisher terms](https://inquirer.sites.fas.harvard.edu/spreadsheet_guide.htm) |
| CrisisLexRec | Alexandra Olteanu and Carlos Castillo; MIT. [Source and license](https://github.com/sajao/CrisisLex) |
| VADER | C. J. Hutto and Eric Gilbert; MIT. [Source and license](https://github.com/cjhutto/vaderSentiment) |
| Princeton WordNet | Princeton University; retain its license and attribution. [License](https://wordnet.princeton.edu/license-and-commercial-use) |
| WordNet Domains/Affect | Fondazione Bruno Kessler; CC BY 3.0. [Publisher terms](https://wndomains.fbk.eu/download.html) |
| Roget conversion | Converted 1911 dictionary; redistribution terms for the conversion are not established. [Source information](https://www.kovcomp.co.uk/wordstat/Roget.html) |
| Lexicoder | Lori Young and Stuart Soroka / McGill University; noncommercial academic use with transfer/adaptation restrictions. A download does not establish permission for every conversion. [Agreement](https://www.snsoroka.com/s/LSDagreement.pdf) |
| GDELT | Archives and codebook retain source terms. [Data/documentation](https://www.gdeltproject.org/data.html) |

Profiles retain source hashes and mappings for reproducibility. An importer provides a technical conversion interface, not additional source rights.