# Documentation

The library implements all 27 GKG columns from prepared article text and supplied metadata. Start with [Installation and setup](installation.md) for installation, dictionaries, models and a complete pipeline, or [API usage](usage.md) for individual functions. External vocabularies are prepared locally; the recorded builds preserve the metrics below. [Version 0.19.0](../CHANGELOG.md#0190-locally-built-resources).

Each field page includes runnable Python and the resulting encoded GKG cell. The [row example](../README.md#generate-and-save-a-row) combines the fields into a complete tab-delimited GKG entry, including count geography.

## Agreement with GDELT

Scores below use the recorded local profiles and the large English NER model, where applicable. The English benchmark contains 2,626 articles from 1,808 sources, reserved separately from the data used to select extraction rules. [Version 0.7.0](../CHANGELOG.md#seasonal-benchmark), [Version 0.18.0](../CHANGELOG.md#0180-remaining-field-benchmarks).

F1 measures matching outputs against GDELT; higher is better. MAE measures average absolute error; lower is better.

**Usability / 10** is an indicative guide for English GKG reconstruction. Set ratings use F1 ÷ 10, rounded with a minimum of 1; counts and amounts include objects, and themes include unsupported labels. Tone uses 10 × correlation to rate trends; GCAM uses dimension coverage ÷ 10, not category accuracy. Thus ratings describe different aspects of usefulness, rather than a common accuracy measure.

Scores of 1–3 suggest limited agreement or coverage, 4–6 moderate, and 7–10 stronger. Metadata and translation provenance remain unrated without a comparable benchmark. Enhanced-field ratings exclude offsets.

### English articles

| Field | Implementation | Current agreement\* | Usability / 10 | Version |
| --- | --- | --- | --- | --- |
| [Record ID](fields/record-id.md), [batch date](fields/date.md), [document ID](fields/document-identifier.md) | Supplied timestamps, sequence and identifier | Metadata formatting | — | — |
| [Source collection](fields/source-collection.md), [source name](fields/source-name.md) | Supplied collection; source label or hostname | Metadata formatting | — | — |
| [Counts](fields/counts.md) · [enhanced](fields/enhanced-counts.md) | Quantity/trigger rules; 37 labels | F1 **31.26%** for label/quantity; **17.57%** including object | **2** | [0.7.0](../CHANGELOG.md#seasonal-benchmark) |
| [Themes](fields/themes.md) · [enhanced](fields/enhanced-themes.md) | Phrase/context rules; 519 labels | F1 **62.38%** across all native labels; **70.87%** within supported labels | **6** | [0.7.0](../CHANGELOG.md#seasonal-benchmark) |
| [Locations](fields/locations.md) · [enhanced](fields/enhanced-locations.md) | NER plus offline geographic resolution | Feature-identity F1 **66.57%** | **7** | [0.18.0](../CHANGELOG.md#0180-remaining-field-benchmarks) |
| [Persons](fields/persons.md) · [enhanced](fields/enhanced-persons.md) | spaCy NER and name normalization | Name F1 **67.01%** | **7** | [0.7.0](../CHANGELOG.md#seasonal-benchmark) |
| [Organizations](fields/organizations.md) · [enhanced](fields/enhanced-organizations.md) | spaCy NER, normalization and name filter | Name F1 **42.77%** | **4** | [0.7.0](../CHANGELOG.md#seasonal-benchmark) |
| [Tone](fields/tone.md) | Dictionary scoring with tone v3 | MAE **1.720 points**; correlation **0.814**; **41.62%** within ±1 point | **8** for trends | [0.7.0](../CHANGELOG.md#seasonal-benchmark) |
| [Date mentions](fields/enhanced-dates.md) | Explicit English calendar expressions | Date F1 **44.37%**, recall **82.01%** | **4** | [0.18.0](../CHANGELOG.md#0180-remaining-field-benchmarks) |
| [GCAM](fields/gcam.md) | English category counts and VADER scores | **809 of 2,888 dimensions (28.01%)** in the standard local profile; **1,855 of 2,888 (64.23%)** with optional dictionaries | Coverage **3** standard / **6** full | [0.9.0](../CHANGELOG.md#090-vader-and-weighted-gcam), [0.11.0–0.17.0](../CHANGELOG.md#0110-general-inquirer-expansion) |
| [Sharing image](fields/sharing-image.md), [related images](fields/related-images.md), [social images](fields/social-image-embeds.md), [social videos](fields/social-video-embeds.md) | Supplied media URLs | Metadata formatting | — | — |
| [Quotations](fields/quotations.md) | Quoted spans and reporting-verb rules | Content F1 **8.11%**; including verb **4.80%** | **1** | [0.18.0](../CHANGELOG.md#0180-remaining-field-benchmarks) |
| [All names](fields/all-names.md) | Broad entities and proper-noun spans | Surface-name F1 **24.50%** | **2** | [0.18.0](../CHANGELOG.md#0180-remaining-field-benchmarks) |
| [Amounts](fields/amounts.md) | Numeric/textual values with bounded objects | Value/object F1 **20.44%**; value alone **40.96%** | **2** | [0.18.0](../CHANGELOG.md#0180-remaining-field-benchmarks) |
| [Translation information](fields/translation-info.md) | Language detection, optional M2M100 translation and provenance | Translated-text scores below | — | [0.7.0](../CHANGELOG.md#seasonal-benchmark) |
| [Extra XML](fields/extras-xml.md) | Custom extension data; titles, authors and publication times are common examples | XML formatting | — | — |

\* We downloaded GKG records and retrieved full text from the publishers' article URLs to compare our outputs with GDELT's stored fields. **We do not have the exact body GDELT processed at the time. Different article bodies can lower F1 even when our extractor is correct on the retrieved text.** Changed pages, HTML-to-text extraction and translation differences all contribute. These scores combine input differences with extraction errors.

Limitations:

- Counts sometimes miss quantities and attach incorrect objects.
- Dates produce extra matches; all names, amounts and quotations have low precision against native GDELT outputs.
- The geographic lookup contains only places observed in 20 reference archives from 2015–2019. Other recognized names remain unresolved and are omitted from GKG geography; see [coverage limits](fields/locations.md#limits).
- Two malformed native location cells are excluded from location scores only; other fields use all 2,626 articles.
- Enhanced offsets have not been benchmarked.

## GCAM

The standard local profile uses General Inquirer, WordNet, theme categories and VADER; Roget and Lexicoder are optional imports. The **28.01% / 64.23% dimension coverage** above counts supported categories out of all 2,888 categories, giving each category equal weight.

Summing GDELT's category counts across the English benchmark, **61.92%** of those counts belong to categories supported by the standard profile, or **77.81%** by the full profile. Frequent categories contribute more to this total than rare ones, so these shares are higher than dimension coverage. They describe how much native counting activity falls within our supported categories, not how accurately we reproduce it. [Versions 0.11.0–0.17.0](../CHANGELOG.md#0110-general-inquirer-expansion).

Results below use the full optional profile on the English benchmark. Presence F1 measures whether a category occurs. Count WAPE is total absolute count error divided by total native counts; lower is better. VADER measures agreement on mean sentiment scores.

| Subset (supported / native dimensions) | Metric | Value | Version |
| --- | --- | --- | --- |
| General Inquirer (217 / 228) | Presence F1 / count WAPE | 93.55% / 37.80% | [0.11.0](../CHANGELOG.md#0110-general-inquirer-expansion) |
| Roget, optional (1,042 / 1,042) | Presence F1 / count WAPE | 83.35% / 67.22% | [0.12.0](../CHANGELOG.md#0120-roget-categories) |
| WordNet Affect (280 / 280) | Presence F1 / count WAPE | 32.86% / 92.28% | [0.14.0](../CHANGELOG.md#0140-wordnet-affect) |
| WordNet Domains (168 / 168) | Presence F1 / count WAPE | 82.17% / 59.92% | [0.15.0](../CHANGELOG.md#0150-wordnet-domains) |
| WordNet lexical categories (44 / 44) | Presence F1 / count WAPE | 96.55% / 72.97% | [0.13.0](../CHANGELOG.md#0130-wordnet-lexical-categories) |
| GCAM themes (99 / 368) | Presence F1 / count WAPE | 70.70% / 64.84% | [0.16.0](../CHANGELOG.md#0160-gcam-theme-counts) |
| Lexicoder, optional (4 / 4) | Presence F1 / count WAPE | 97.46% / 40.09% | [0.10.0](../CHANGELOG.md#0100-lexicoder-import) |
| VADER (1 / 1) | MAE / correlation / sign agreement | 0.2102 / 0.8979 / 92.75% | [0.9.0](../CHANGELOG.md#090-vader-and-weighted-gcam) |

## Choosing a configuration

- Build the recorded local dictionaries and `en_core_web_lg` for the strongest measured person agreement. If organizations are the priority, `en_core_web_sm` has name F1 **44.02%**. [Version 0.7.0](../CHANGELOG.md#seasonal-benchmark).
- Add Roget and Lexicoder when broader GCAM coverage is needed; follow the [download and setup guide](installation.md#best-supported-setup). Their vocabularies are supplied separately.
- Translate non-English bodies before extraction and retain the analyzed English text for offsets. The [full pipeline example](installation.md#complete-pipeline-example) handles detection, CUDA translation and extraction.

On 317 translated articles across 40 source languages, M2M100 with the large NER model gives theme F1 **44.46%**, tone MAE **2.646 points**, person F1 **7.15%** and organization F1 **2.94%**. Translation and entity extraction still differ substantially from native GDELT processing. [Version 0.7.0](../CHANGELOG.md#seasonal-benchmark).

[Resource builders and benchmarks](../scripts/README.md) · [Detailed research reports](reports/README.md)
