# Results

The published agreement baseline is Nikita A. Klimin (2026), [*Agreement Between Reconstructed and Native GDELT GKG Records: A Field-Level Baseline*](https://arxiv.org/abs/2610.35358v1), arXiv v1, submitted 26 October 2026. This page summarizes that version. See [BibTeX](../README.md#citing-the-agreement-study) to cite it.

The earlier [development benchmark](development-benchmarks.md) remains available separately. Its larger corpus and GCAM v4 tables describe a different evaluation. Neither report establishes agreement for every later software release or dictionary build.

## Paper and development benchmark

| Evaluation detail | Published paper (arXiv v1) | Earlier development benchmark |
| --- | --- | --- |
| English period | 2020–2025 | 2018–2025 |
| Retained English articles | 193,550 | 265,413 |
| Publishers / source labels | 8,729 | 10,531 |
| Attempted unique URLs | 577,221 | 885,193 |
| Retention after exclusions | 33.53% | 29.98% |
| Title-and-length subset (±10%) | 54,485 | 54,609 |
| GCAM configuration | Custom v5 with LIWC and MPQA | v4 |
| Additional languages | 500 articles each in French, Spanish, German, Russian and Chinese | Earlier translated-article experiments linked separately |

The sample, time span, resource inventory and selection rules affect the scores. Similar point estimates across these reports do not measure software improvement or regression. In particular, the retention fractions combine several exclusions and cannot be interpreted as a change in retrieval success alone.

## Study configuration

The paper evaluates `gdelt-regkg` 2.1.2, spaCy `en_core_web_lg` 3.8.0, tone/themes/counts v3, names v1 and a custom GCAM v5 profile. Its primary gazetteer has 119,733 entries; a paired comparison uses 17,177 entries. Methods and resource details are in Section V of the [paper](https://arxiv.org/html/2610.35358v1).

### English articles

The full corpus is the main population. The title-and-length subset requires eligible matching normalized titles and reconstructed/native tone word-count ratios from 0.90 to 1.10. It is a selected population; similar titles and lengths do not establish identical bodies or isolate extraction error.

### Field agreement

The following values are from Tables IV–VI and Section VI-C of the [paper](https://arxiv.org/html/2610.35358v1). Categorical values are pooled micro-F1. The development column is included for comparison; its full tables and restricted-subset scores remain on the [development page](development-benchmarks.md#field-agreement).

| Metric | Paper: full English corpus | Paper: title-and-length ±10% | Development: full English corpus |
| --- | ---: | ---: | ---: |
| Tone MAE (points) | 1.787 | 1.474 | 1.795 |
| Tone CCC | 0.749 | 0.830 | 0.746 |
| Person identity F1 | 0.646 | 0.748 | 0.646 |
| Organization identity F1 | 0.417 | 0.483 | 0.415 |
| Location identity F1 | 0.654 | 0.727 | 0.649 |
| Theme F1, all labels | 0.617 | — | 0.614 |
| Theme F1, implemented labels | 0.698 | — | 0.697 |
| Count F1, label + quantity | 0.285 | — | 0.289 |
| Count F1, including object | 0.166 | — | 0.164 |
| Count F1, full tuple | 0.070 | 0.073 | 0.065 |
| Date-component F1 | 0.424 | — | 0.429 |
| Amount F1, value + object | 0.198 | — | 0.197 |
| Quotation-content F1 | 0.068 | — | 0.067 |
| All-names identity F1 | 0.231 | — | 0.230 |

A dash means this summary does not list that result. The paper also reports precision, recall, macro scores and publisher-cluster intervals. Those distinguish common-item agreement from article-, category- and publisher-level agreement. See [Methodology](methodology.md) for metric definitions.

### Tone scale

Tone uses a −100 to +100 scale. In the paper, native tone has standard deviation 3.891 points; MAE is 0.459 of that spread. The full-corpus 95% publisher-cluster interval is 1.76–1.82 for MAE and 0.736–0.759 for CCC. These intervals describe variation within the retained sample.

## GCAM

The paper evaluates a custom v5 profile with LIWC and MPQA, implementing 2,492 categories across its evaluated languages. English category-presence micro-F1 is 0.824 across the observed inventory and 0.840 within the implemented inventory. These scopes have different denominators. See Section VI-H and Appendix B of the [paper](https://arxiv.org/html/2610.35358v1) for dictionary-level presence, count and weighted-score results.

Count WAPE was 41.4% for General Inquirer, 38.2% for LIWC and 36.3% for MPQA: high presence agreement did not imply close count agreement.

The study profile contains 2,673 compiled categories: 2,492 in the evaluated languages and 181 in other languages, consistent with the [build inventory](../guides/gcam-resources.md). Record the sources, options and compiled resources when reproducing it. The historical [v4 family tables](development-benchmarks.md#gcam) apply to the development corpus.

## Languages and geographic resources

The paper adds translated-tone and original-language GCAM evaluations, reported separately in Tables VII–VIII. Translated-tone MAE ranges from 2.10 to 2.64 points; Chinese has 499 complete translations. These language samples have different inclusion rules from the English corpus.

The paired gazetteer experiment raises native-place coverage from 89.5% to 97.1%, while both full-corpus location F1 estimates round to 0.654. Inventory coverage and output agreement measure different properties. See Table VI of the [paper](https://arxiv.org/html/2610.35358v1).

## Temporal agreement

Monthly agreement does not consistently improve for newer articles. Some fields show monthly variation and calendar patterns (Section VI-F of the paper).

## Choosing a configuration

Use the paper's software and resource configuration for claims about its baseline. Use the [benchmark tools](../guides/benchmarking.md) to evaluate a current or customized build on appropriate held-out articles. [Build GCAM resources](../guides/gcam-resources.md) describes available presets; [Limitations and intended use](limitations-and-intended-use.md) explains how to interpret reconstructed records.
