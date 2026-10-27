# Development benchmark (2018–2025)

This page preserves the earlier development evaluation on 265,413 retained English articles and its GCAM v4 configuration. Use [Results](results.md) for the arXiv study and a comparison of the two evaluations. See [Methodology](methodology.md) for metric definitions and benchmark-tool behavior.

> [!NOTE]
> These are historical development results. Cite the paper's own samples, configurations and metrics when discussing its findings. Differences between these evaluations do not establish a change in software quality.

## Study configuration

This development benchmark compares archived GKG outputs with reconstruction on **265,413 retained English articles** from 2018–2025, covering 10,531 sources. Retention was 29.98% of attempted URLs after retrieval, language screening and other exclusions. The retained corpus does not represent all GDELT news.

Library uses the recorded tone/count/theme profiles, expanded GCAM dictionaries and spaCy `en_core_web_lg` for named entity recognition (NER) with the `gdelt-full-names` policy.

### English articles

The full corpus is the primary result. The restricted subset contains 54,609 articles from 2020–2025 with exact normalized titles and [local/native](../get-started/concepts-and-glossary.md#native-and-reconstructed) word-count ratios between 0.90 and 1.10. Word counts come from their respective tone fields. The restricted subset differs in both period and selection criteria from the full corpus. Similar lengths do not establish identical text, so these results measure agreement on the selected articles without isolating extraction error.

### How to read the results

[F1](../get-started/concepts-and-glossary.md#f1-scores) combines precision and recall, with 1 denoting perfect agreement. [Mean absolute error (MAE)](../get-started/concepts-and-glossary.md#mae) uses the quantity's original units and is lower when agreement is closer. [Lin's concordance correlation coefficient (CCC)](../get-started/concepts-and-glossary.md#ccc) has 1 as perfect concordance. See [metric definitions](../get-started/concepts-and-glossary.md#f1-scores) and [Methodology](methodology.md) for calculation and matching rules.

Location identity scores use 265,340 valid full-corpus pairs and 54,593 restricted pairs. Other non-GCAM field scores use the listed article counts. All F1 values are pooled micro-F1. Enhanced offsets have not been benchmarked.

Full-corpus source-cluster bootstrap 95% intervals are 1.767–1.828 for tone MAE, 0.6371–0.6545 for person F1, 0.4092–0.4204 for organization F1 and 0.6410–0.6565 for location F1, using 2,000 draws. The intervals are conditional on observed acquisition.

Exploratory inverse-retention weighting increases tone MAE to 1.888 with weights capped at 20 and 2.063 without capping. The weighting demonstrates sensitivity to selection.

### Field agreement

| Field | Implementation | Full corpus | Restricted subset |
| --- | --- | --- | --- |
| [Record ID](../reference/fields/record-id.md), [Batch date](../reference/fields/date.md), [Document identifier](../reference/fields/document-identifier.md) | Supplied timestamps, sequence and identifier | Metadata formatting | Not scored |
| [Source collection](../reference/fields/source-collection.md), [Source name](../reference/fields/source-name.md) | Supplied collection and a source label or hostname | Metadata formatting | Not scored |
| [Counts](../reference/fields/counts.md) · [Enhanced counts](../reference/fields/enhanced-counts.md) | Rules matching quantities and event triggers across 37 labels | F1 0.2888 for label/quantity<br>0.1639 including object<br>0.0652 including geography | F1 0.3210 for label/quantity<br>0.1823 including object<br>0.0688 including geography |
| [Themes](../reference/fields/themes.md) · [Enhanced themes](../reference/fields/enhanced-themes.md) | Phrase matching and context rules across 519 labels | F1 0.6144 across all native labels<br>0.6965 within supported labels | F1 0.6720 across all native labels<br>0.7667 within supported labels |
| [Locations](../reference/fields/locations.md) · [Enhanced locations](../reference/fields/enhanced-locations.md) | NER plus offline geographic resolution | Feature-identity F1 0.6489 | Feature-identity F1 0.7253 |
| [Persons](../reference/fields/persons.md) · [Enhanced persons](../reference/fields/enhanced-persons.md) | spaCy NER and name normalization | Name F1 0.6456 | Name F1 0.7483 |
| [Organizations](../reference/fields/organizations.md) · [Enhanced organizations](../reference/fields/enhanced-organizations.md) | spaCy NER, normalization and name filter | Name F1 0.4149 | Name F1 0.4833 |
| [Tone](../reference/fields/tone.md) | Dictionary scoring with tone v3 | MAE 1.795 points<br>CCC 0.746 | MAE 1.475 points<br>CCC 0.830 |
| [Date mentions](../reference/fields/enhanced-dates.md) | Explicit English calendar expressions | Date F1 0.4286 | Date F1 0.5066 |
| [GCAM](../reference/fields/gcam.md) | English category counts and VADER lexical means | 809 / 2,888 dimensions (28.01%) standard<br>1,855 / 2,888 (64.23%) v4 | Same supported vocabulary<br>family metrics below |
| [Sharing image](../reference/fields/sharing-image.md), [Related images](../reference/fields/related-images.md), [Social image embeds](../reference/fields/social-image-embeds.md), [Social video embeds](../reference/fields/social-video-embeds.md) | Supplied media URLs | Metadata formatting | Not scored |
| [Quotations](../reference/fields/quotations.md) | Quoted spans and reporting-verb rules | Content F1 0.0671<br>including verb 0.0377 | Content F1 0.0843<br>including verb 0.0464 |
| [All names](../reference/fields/all-names.md) | Broad entities and proper-noun spans | Surface-name F1 0.2301 | Surface-name F1 0.2828 |
| [Amounts](../reference/fields/amounts.md) | Numeric/textual values with bounded objects | Value/object F1 0.1973<br>value alone 0.4054 | Value/object F1 0.2455<br>value alone 0.4912 |
| [Translation information](../reference/fields/translation-info.md) | Language detection, optional translation and language/engine metadata | Not evaluated in the English study | Not scored |
| [Extra XML](../reference/fields/extras-xml.md) | Supplied extension metadata | XML formatting | Not scored |

See [Limitations and intended use](limitations-and-intended-use.md) for interpretation across fields.

For field agreement on translated articles, see the [seasonal translated-article evaluation](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md#translingual-agreement). Those results combine retrieval, translation and extraction differences. They do not independently measure translation quality or the accuracy of recorded language and engine values.

### Tone scale

Tone ranges from −100 to +100 points and is calculated as positive-word density minus negative-word density. The native-tone standard deviation is 3.873 points in the full corpus and 3.631 points in the restricted subset. The corresponding MAEs of 1.795 and 1.475 points are about 0.464 and 0.406 native standard deviations.

## GCAM

> [!WARNING]
> The agreement metrics below describe v4. Dimension coverage is 1,855 of 2,888 (64.23%) for the evaluated v4 profile. See [Build GCAM resources](../guides/gcam-resources.md) for the build and coverage report.

On this development corpus, the evaluated profile covers 64.23% of documented dimensions, 78.33% of native positive count occurrences and 81.02% of native document–dimension assignments. Frequent categories contribute more to occurrence coverage. These shares measure representable native activity, not correctly reconstructed counts. The older seasonal benchmark's occurrence shares are retained in the [historical changelog](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md#combined-gcam-coverage).

Presence F1, weighted absolute percentage error (WAPE) for counts and aggregate count ratios use the 265,413-article full corpus. The final column separately reports WAPE for the 54,609-article restricted subset. Presence F1 compares category occurrence. Count ratios above one indicate aggregate overcounting and below one indicate undercounting. Metrics apply to supported comparable categories.

| Family (supported / native dimensions) | Full presence F1 | Full count WAPE | Full local/native count ratio | Restricted count WAPE |
| --- | ---: | ---: | ---: | ---: |
| General Inquirer (217 / 228) | 0.9268 | 41.20% | 0.866 | 27.30% |
| Lexicoder, optional (4 / 4) | 0.9702 | 43.12% | 0.742 | 34.12% |
| Roget, optional (1,042 / 1,042) | 0.8169 | 70.73% | 1.183 | 50.78% |
| WordNet Affect (280 / 280) | 0.3187 | 93.19% | 0.259 | 88.61% |
| WordNet Domains (168 / 168) | 0.8143 | 63.09% | 0.654 | 54.46% |
| WordNet lexical categories (44 / 44) | 0.9621 | 75.87% | 1.472 | 54.35% |
| GCAM themes (99 / 368) | 0.6893 | 67.05% | 0.625 | 56.25% |

High presence F1 can coexist with biased counts: WordNet lexical categories have presence F1 0.9621 but an aggregate count ratio of 1.472. Vocabulary coverage therefore does not make local and native category counts interchangeable.

The VADER evaluation measures mean valence among matched lexical entries. It does not evaluate the complete VADER sentiment algorithm. Pairs with undefined means are excluded.

| Subset | Comparable pairs | MAE | CCC | Sign agreement |
| --- | ---: | ---: | ---: | ---: |
| Full corpus | 262,295 | 0.242 | 0.871 | 90.94% |
| Restricted subset | 54,518 | 0.139 | 0.952 | 93.92% |

## Choosing a configuration

- This development benchmark used `en_core_web_lg`, the `gdelt-full-names` policy and the recorded local profiles. See [English models](../get-started/installation-and-setup.md#english-models) and [GCAM profiles](../guides/gcam-resources.md#choose-a-preset).
- Its GCAM tables describe v4. The [paper evaluates a custom v5 profile](results.md#gcam); rebuilding a current preset does not establish agreement for that build.
- Translate non-English bodies before English extraction. The [full pipeline example](../guides/translation.md#complete-pipeline-example) handles detection, translation and extraction.

[Benchmarking](../guides/benchmarking.md) · [CLI](../reference/cli.md)
