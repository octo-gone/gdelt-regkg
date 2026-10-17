# Agreement with GDELT

Published results compare reconstructed fields with archived GKG output. These measurements describe the stated models, profiles and retained article samples. See [methodology](methodology.md) for definitions and interpretation.

## Study configuration

The latest study compares archived GKG outputs with reconstruction on **265,413 retained English articles from 2018–2025**, covering **10,531 sources**. It uses the recorded tone/count/theme profiles, expanded GCAM dictionaries and spaCy `en_core_web_lg` with the `gdelt-full-names` policy.

### English articles

The **full corpus** is the primary result. The **restricted subset** contains **54,609 articles** from 2020–2025 with exact normalized titles and local/native word-count ratios between 0.90 and 1.10. Here, local denotes our reconstruction and native denotes the archived GKG output; word counts come from their respective tone fields. Similar lengths do not establish identical text, and subset composition also changes; the restricted results do not isolate an extraction-only error rate.

| Field | Implementation | Full corpus | Restricted subset |
| --- | --- | --- | --- |
| [Record ID](../reference/fields/record-id.md), [batch date](../reference/fields/date.md), [document ID](../reference/fields/document-identifier.md) | Supplied timestamps, sequence and identifier | Metadata formatting | Not scored |
| [Source collection](../reference/fields/source-collection.md), [source name](../reference/fields/source-name.md) | Supplied collection; source label or hostname | Metadata formatting | Not scored |
| [Counts](../reference/fields/counts.md) · [enhanced](../reference/fields/enhanced-counts.md) | Quantity/trigger rules; 37 labels | F1 **0.2888** for label/quantity; **0.1639** including object; **0.0652** including geography | F1 **0.3210** for label/quantity; **0.1823** including object; **0.0688** including geography |
| [Themes](../reference/fields/themes.md) · [enhanced](../reference/fields/enhanced-themes.md) | Phrase/context rules; 519 labels | F1 **0.6144** across all native labels; **0.6965** within supported labels | F1 **0.6720** across all native labels; **0.7667** within supported labels |
| [Locations](../reference/fields/locations.md) · [enhanced](../reference/fields/enhanced-locations.md) | NER plus offline geographic resolution | Feature-identity F1 **0.6489** | Feature-identity F1 **0.7253** |
| [Persons](../reference/fields/persons.md) · [enhanced](../reference/fields/enhanced-persons.md) | spaCy NER and name normalization | Name F1 **0.6456** | Name F1 **0.7483** |
| [Organizations](../reference/fields/organizations.md) · [enhanced](../reference/fields/enhanced-organizations.md) | spaCy NER, normalization and name filter | Name F1 **0.4149** | Name F1 **0.4833** |
| [Tone](../reference/fields/tone.md) | Dictionary scoring with tone v3 | MAE **1.795 points**; CCC **0.746** | MAE **1.475 points**; CCC **0.830** |
| [Date mentions](../reference/fields/enhanced-dates.md) | Explicit English calendar expressions | Date F1 **0.4286** | Date F1 **0.5066** |
| [GCAM](../reference/fields/gcam.md) | English category counts and VADER lexical means | **809 / 2,888 dimensions (28.01%)** standard; **1,855 / 2,888 (64.23%)** v4 | Same supported vocabulary; family metrics below |
| [Sharing image](../reference/fields/sharing-image.md), [related images](../reference/fields/related-images.md), [social images](../reference/fields/social-image-embeds.md), [social videos](../reference/fields/social-video-embeds.md) | Supplied media URLs | Metadata formatting | Not scored |
| [Quotations](../reference/fields/quotations.md) | Quoted spans and reporting-verb rules | Content F1 **0.0671**; including verb **0.0377** | Content F1 **0.0843**; including verb **0.0464** |
| [All names](../reference/fields/all-names.md) | Broad entities and proper-noun spans | Surface-name F1 **0.2301** | Surface-name F1 **0.2828** |
| [Amounts](../reference/fields/amounts.md) | Numeric/textual values with bounded objects | Value/object F1 **0.1973**; value alone **0.4054** | Value/object F1 **0.2455**; value alone **0.4912** |
| [Translation information](../reference/fields/translation-info.md) | Language detection, optional translation and provenance | Not evaluated in the English study | Not scored |
| [Extra XML](../reference/fields/extras-xml.md) | Supplied extension metadata | XML formatting | Not scored |

Location identity scores use **265,340** valid full-corpus pairs and **54,593** restricted pairs. Other non-GCAM field scores use the listed article counts. All F1 values pool matches across articles; they are not averages of per-article F1. Enhanced offsets have not been benchmarked.

Full-corpus source-cluster bootstrap 95% intervals are **1.767–1.828** for tone MAE, **0.6371–0.6545** for person F1, **0.4092–0.4204** for organization F1 and **0.6410–0.6565** for location F1, using 2,000 draws. The intervals are conditional on observed acquisition.

Only **29.98% of attempted URLs** were retained. Exploratory inverse-retention weighting increases tone MAE to **1.888** with weights capped at 20 and **2.063** without capping. This indicates sensitivity to selection, rather than a validated population correction; the retained corpus does not represent all GDELT news.

Remaining limitations:

- Counts often miss quantities or attach different objects and locations; amount-object and quotation agreement is low.
- Themes outside the supported vocabulary are included in the all-label score and cannot be recovered by that profile.
- The geographic lookup contains places observed in 20 reference archives from 2015–2019. Other recognized names can can be unresolved and be omitted from GKG geography; see [coverage limits](../reference/fields/locations.md#limitations).
- Metadata formatting, media inputs, translation provenance and enhanced offsets have no extraction-accuracy score in this study.

For field agreement on translated articles, see the [seasonal translated-article evaluation](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md#translingual-agreement). Those results combine retrieval, translation and extraction differences; they do not measure translation quality or provenance accuracy independently.

## GCAM

The standard local profile uses General Inquirer, WordNet-derived families, theme categories and VADER. Roget and Lexicoder are optional imports. Dimension coverage is **809 of 2,888 (28.01%)** for the standard profile and **1,855 of 2,888 (64.23%)** for the evaluated v4 profile. The v5 build compiles 2,597 dimensions, including 268 authored theme approximations; source-backed coverage is 2,328. These vocabulary counts give each dimension equal weight.

> [!WARNING]
> The agreement metrics below describe v4. The broader v5 vocabulary includes approximations; its coverage figures do not establish equivalent scores or improved extraction accuracy.

On the latest full corpus, the evaluated v4 profile covers **78.33% of native positive count occurrences** and **81.02% of native document–dimension assignments**. Frequent categories contribute more to occurrence coverage. These shares measure representable native activity, not correctly reconstructed counts. The older seasonal benchmark's occurrence shares are retained in the [historical changelog](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md#combined-gcam-coverage).

The table uses the evaluated v4 profile. Presence F1, count WAPE and aggregate count ratios use the **265,413-article full corpus**; the final column separately reports WAPE for the **54,609-article restricted subset**. Presence F1 compares category occurrence. WAPE divides total absolute count error by total native counts and is expressed as a percentage; lower is better. Count ratios above one indicate aggregate overcounting and below one indicate undercounting. Metrics apply to supported comparable categories.

| Family (supported / native dimensions) | Full presence F1 | Full count WAPE | Full local/native count ratio | Restricted count WAPE |
| --- | ---: | ---: | ---: | ---: |
| General Inquirer (217 / 228) | 0.9268 | 41.20% | 0.866 | 27.30% |
| Lexicoder, optional (4 / 4) | 0.9702 | 43.12% | 0.742 | 34.12% |
| Roget, optional (1,042 / 1,042) | 0.8169 | 70.73% | 1.183 | 50.78% |
| WordNet Affect (280 / 280) | 0.3187 | 93.19% | 0.259 | 88.61% |
| WordNet Domains (168 / 168) | 0.8143 | 63.09% | 0.654 | 54.46% |
| WordNet lexical categories (44 / 44) | 0.9621 | 75.87% | 1.472 | 54.35% |
| GCAM themes (99 / 368) | 0.6893 | 67.05% | 0.625 | 56.25% |

High presence F1 can coexist with biased counts: WordNet lexical categories have presence F1 **0.9621** but an aggregate count ratio of **1.472**. Vocabulary coverage therefore does not make local and native category counts interchangeable.

VADER is evaluated separately on mean valence among matched lexical entries, rather than the complete VADER sentiment algorithm. Pairs with undefined means are excluded.

| Subset | Comparable pairs | MAE | CCC | Sign agreement |
| --- | ---: | ---: | ---: | ---: |
| Full corpus | 262,295 | 0.242 | 0.871 | 90.94% |
| Restricted subset | 54,518 | 0.139 | 0.952 | 93.92% |

## Choosing a configuration

- To reproduce the latest English study's model and vocabulary configuration, use `en_core_web_lg`, the `gdelt-full-names` policy and the recorded local profiles. See [English models](../installation.md#english-models) and [GCAM profiles](../guides/resources.md#gcam-profiles-and-expansion).
- Use v4 to reproduce the evaluated GCAM vocabulary, or v5 for the broader English and native-language inventory. Broader coverage does not guarantee lower count error.
- Translate non-English bodies before English extraction and retain the analyzed text for offsets. The [full pipeline example](../guides/translation.md#complete-pipeline-example) handles detection, translation and extraction.

[Benchmark CLI guide](../guides/benchmarking.md) · [Resource builders and benchmarks](../reference/cli.md)
