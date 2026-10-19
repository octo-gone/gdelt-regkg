# Dictionary imports

Use these procedures for source files that need conversion or optional dictionaries outside the default build. Follow [Build GCAM resources](gcam-resources.md#provide-source-files) to select components and supply raw files, or [Build resources](resources.md) for shared build mechanics. Review [source terms](../reference/dictionaries.md#third-party-terms) before obtaining or redistributing inputs.

## GCAM source formats

| Dictionary | Input |
| --- | --- |
| LIWC | Compatible English LIWC 2007 `.dic` |
| MPQA Subjectivity | TFF clues file, ZIP/TGZ or extracted directory |
| ML-SENTICON | English `senticon.en.xml` or sixteen-score-column CSV |
| Native ML-SENTICON | Catalan, Spanish and Galician publisher XMLs<br>cumulative layers |
| Translated RID | Publisher CAT/EXC ZIPs<br>Hungarian Windows-1250, other available editions Windows-1252 |
| Spanish ANEW | Original `Redondo-BRM-2007.zip` with the 1,034-word TXT table |
| Multilingual Hedonometer | Complete publisher labMT JSON lists, including an acquired Chinese list without scoring |
| French imagery | Original PDF with optional OCR, generated class-midpoint CSV, or verified `word,ImageryValence` CSV on the native 10–70 scale |
| Portuguese emotion | Original `word,Emotion,ProSocial` CSV on the native 10–70 scales |
| ANEW | Automatically converted report, or CSV with a word column and nine rating columns |
| Historical count dictionaries | CAT or explicit category JSON |
| Moral Foundations | LIWC-style `.dic` with category definitions and vocabulary, or category JSON |
| Lexicoder topics | ZIP or English `policy_agendas_english.lcd` |
| Loughran–McDonald | Master CSV with sentiment columns |
| Central-bank sentiment | XLSX dictionary appendix or category JSON |
| VADER | Vocabulary text file |

### Category dictionaries and exclusions

Category JSON uses `{"categories": {"NATIVE_KEY": ["word", "stem*", "phrase"]}}`, where each key is a native count key or exact category name for the selected dictionary. Unknown categories fail with a mapping error. This interchange format supplies vocabulary to supported category importers. It does not create an arbitrary dictionary selector or replace the compiled-profile schema.

CAT sources use tab-indented category paths and unit-weight vocabulary entries such as `WORD* (1)`. Supply exactly one CAT file in the selected source. If the dictionary includes EXC exclusions, pass a ZIP or extracted directory containing both files. Passing a CAT file alone does not read a neighboring EXC file. EXC files contain one exclusion pattern per line.

LIWC-style DIC sources contain two sections introduced by `%` lines. The first maps numeric category IDs to category names. The second maps a vocabulary term to one or more of those IDs. Mapping to GCAM uses category names. Moral Foundations uses this format, while the LIWC importer requires the compatible 62-category English 2007 inventory.

### Other vocabulary formats

VADER input is UTF-8 text with a term and numeric mean valence separated by a tab. Additional publisher columns are accepted after these fields. Terms must be single whitespace tokens. See the [small authored example](gcam-resources.md#build-only-selected-dictionaries) for a complete build without unrelated sources.

Lexicoder sentiment accepts a ZIP or directory containing `LSD2015.lc3` and `LSD2015_NEG.lc3`. Its JSON alternative maps exactly four keys, `negative`, `positive`, `neg_negative` and `neg_positive`, to arrays of patterns. This format differs from category JSON's `categories` wrapper.

Loughran–McDonald CSV requires `Word`, `Litigious`, `Strong_Modal`, `Weak_Modal`, `Negative`, `Positive` and `Uncertainty` columns. Category cells contain integers. Positive values include a word in that category, while zero or negative values do not. Negative years mark words removed from an edition. Arbitrary word/category CSV layouts must be converted to the selected importer's format before building.

### Rating tables

ANEW CSV requires `word` and these mean-rating columns:

```text
Valence (Pleasure) (All), Arousal (All), Dominance (All)
Valence (Pleasure) (Men), Arousal (Men), Dominance (Men)
Valence (Pleasure) (Women), Arousal (Women), Dominance (Women)
```

ML-SENTICON CSV requires `word` and `LevelNPositive`/`LevelNNegative` for each level from 1 through 8. Preserve signed scores. Empty cells indicate unavailable ratings.

Acquisition links and licenses are in [Dictionaries](../reference/dictionaries.md) and [GCAM license table](../reference/dictionaries.md#dictionary-licenses).

## French imagery PDF conversion

The publisher makes Hogenraad and Orianne's [French imagery paper](https://psychologicabelgica.com/articles/10.5334/pb.672) publicly available under CC BY 4.0, but provides no ratings CSV with the article. Extracting its appendix is one way to prepare a machine-readable dictionary when the original rating file is unavailable. The library provides this PDF-to-CSV route, as it does for [ANEW](#anew-report-conversion). An independently obtained, compatible rating CSV can also be imported directly.

French imagery is included in the `v5` preset as an approximate dimension because the published appendix supplies rating intervals rather than exact word-level means. PDF conversion assigns class midpoints on a scale of 10–70. These are approximate scores, not recovered GDELT word ratings.

Install the Python image extraction and OCR dependencies:

```shell
python -m pip install "gdelt-regkg[build]"
```

The `build` extra includes pypdf, pypdfium2, Pillow, pytesseract and Jieba. pypdf extracts the English ANEW tables. Pypdfium2 renders French imagery's scanned pages. French OCR recognizes individual text lines with local Tesseract on the CPU. It requires no GPU or Transformers model. A prepared CSV or corrected appendix transcription avoids OCR.

Install the Tesseract engine separately. Pip installs only the Python wrapper. Follow the [Tesseract installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html). On Windows, use the [UB Mannheim distribution linked by Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and add the installation directory to `PATH`. If it is outside `PATH`, set the executable path before building:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

On Debian/Ubuntu:

```shell
sudo apt install tesseract-ocr
```

On macOS with Homebrew:

```shell
brew install tesseract
```

Check `tesseract --version`. During PDF conversion, the builder downloads and checksum-verifies the higher-accuracy [tessdata_best French language data](https://github.com/tesseract-ocr/tessdata_best) into `downloads/resources/models/tesseract`. This Apache-2.0 model data is stored outside the package and reused on subsequent runs. The builder never downloads or installs Tesseract executables. It reports page and line progress, limits each page to 120 seconds and each line to 15 seconds, and converts the recognized text automatically when structural checks pass. OCR-derived scores are marked `unreviewed-ocr`. Successful conversion does not certify every spelling.

For a new setup, build v5 directly from the recorded sources, including automatic French imagery PDF conversion:

```shell
gdelt-regkg-cli build gcam --use full --sources-dir downloads/resources --download-sources --output local-resources
```

The first run downloads the paper and recognition data. Subsequent runs reuse these files. No transcription or prepared CSV is required. A local PDF can be selected with `--source french-imagery=paper.pdf`.

To run the converter separately and save its CSV, OCR text and audit:

```shell
python -m gdelt_regkg.builders.french_imagery --output downloads/resources/french-imagery.csv
```

The converter saves `.ocr.txt` and `.audit.json` beside its CSV. Malformed entries, missing classes and large count discrepancies fail conversion. Smaller count discrepancies are warned about and recorded. The audit records skipped phrases and conflicting senses. No plural expansion or stemming is invented.

During a PDF build, the OCR draft is saved next to the source PDF as `<paper>.ocr.txt`, including when validation fails. If structural validation fails, use the standalone converter with `--pdf` and `--reviewed-text`, then pass its CSV through `--source french-imagery=...`.

**Import an existing CSV without OCR.** Supply a generated or manually prepared UTF-8 CSV with `word,ImageryValence` columns, using the native 10–70 scale:

```shell
gdelt-regkg-cli build gcam --use full --source french-imagery=my-imagery.csv --sources-dir downloads/resources --download-sources --output local-resources
```

This path loads neither PDF rendering nor OCR backends. This six-row example shows one published word from each class with its interval midpoint. Use the complete dataset for analysis.

```csv
word,ImageryValence,approximation,class,lower,upper,review_status
cause,19.5,class-midpoint,I,15,24,example
accord,29.5,class-midpoint,II,25,34,example
action,39.5,class-midpoint,III,35,44,example
amour,49.5,class-midpoint,IV,45,54,example
abeille,59.5,class-midpoint,V,55,64,example
eau,67.5,class-midpoint,VI,65,70,example
```

These rows adapt Hogenraad and Orianne's [published appendix](https://psychologicabelgica.com/articles/10.5334/pb.672), CC BY 4.0, by multiplying intervals by ten and taking their midpoints.

Keep `approximation=class-midpoint` whenever scores come from rating bands. `class`, `lower` and `upper` document those bands. `review_status` describes the supplied file, and `source_pdf_sha256` can retain its source checksum. Preserve these columns in converted files and keep the conversion audit alongside them. Exact word-level ratings may use the two-column format only when independently verified. Transcription review does not turn class midpoints into exact ratings.

**Import reviewed appendix text without OCR.** Keep all six `Classe I` through `Classe VI` headings or `[I]` through `[VI]` markers, then convert the transcription:

```shell
python -m gdelt_regkg.builders.french_imagery --pdf paper.pdf --reviewed-text imagery-reviewed.txt --output my-imagery.csv
```

Use the resulting CSV with the import command above. This path checks the paper's checksum and class structure and requires no OCR dependencies. PDF builds retain their conversion audit in source metadata. CSV builds retain approximation, review status and source PDF checksum columns.

The coverage report lists `38.1` under `approximate_dimensions`. `compiled_dimensions` includes it while `supported_dimensions` excludes it. An independently verified rating CSV without the approximation column retains the ordinary exact-data import behavior. Review status records the supplied conversion path, not independent verification of every entry.

## ANEW report conversion

[Global Content Analysis Measures (GCAM)](../get-started/concepts-and-glossary.md#gcam-and-dimensions) v5 downloads the original ANEW technical report and converts its all-, male- and female-participant tables to `anew.csv`. Install the optional PDF dependency before building:

```shell
python -m pip install "gdelt-regkg[build]"
gdelt-regkg-cli build gcam --use v5 --sources-dir downloads/resources --download-sources --output local-resources
```

The converter also runs separately:

```shell
python -m gdelt_regkg.builders.anew --output downloads/resources/anew.csv
python -m gdelt_regkg.builders.anew --pdf reference/anew.pdf --output downloads/resources/anew.csv
```

Automatic extraction uses an installed Poppler/Xpdf `pdftotext`, or `pypdf` from the `build` extra when that executable is absent. The standalone script accepts `--backend pypdf` or `--backend pdftotext` to select one explicitly. No external PDF executable is required with `pypdf`. Ordinary extraction and builds using a prepared CSV need neither backend.

The converter verifies the report checksum, joins the three tables by word number, validates all 1,034 records and verifies the resulting CSV checksum. It retains nine means. Standard deviations and word frequencies are not GCAM score columns. The table-conversion approach is described by [begin_anew](https://github.com/sbma44/begin_anew). The package provides its own converter. See [ANEW license notes](../reference/dictionaries.md#dictionary-19) before redistributing the ratings.

## Optional LIWC and MPQA imports

Supply an authorized English LIWC 2007 dictionary to add its 62 GCAM categories:

```shell
gdelt-regkg-cli build gcam --use v5 --gcam-add liwc --source liwc=/path/to/LIWC2007_English.dic --sources-dir downloads/resources --download-sources --output local-resources
```

MPQA is an optional GPL-3.0 import with 14 dimensions. `--download-mpqa` adds it and explicitly permits downloading the checksum-verified third-party mirror. Use that mirror at your discretion. The default v5 preset does not download MPQA.

```shell
gdelt-regkg-cli build gcam --use v5 --download-mpqa --sources-dir downloads/resources --download-sources --output local-resources
```

Alternatively, add `--gcam-add subjectivity --source subjectivity=/path/to/mpqasubj.zip` to use your own archive or clues file. `--download-sources` alone does not authorize a fresh MPQA mirror download. Neither LIWC nor MPQA is bundled with the package.
