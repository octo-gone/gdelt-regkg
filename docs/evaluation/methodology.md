# Methodology

Agreement with archived [Global Knowledge Graph (GKG)](../get-started/concepts-and-glossary.md#gkg) output depends on the reconstruction and the available input text. [Results](results.md) identifies the paper's evaluated population and configuration. The earlier [development benchmark](development-benchmarks.md) has its own sample and resource inventory. [Benchmarking](../guides/benchmarking.md) explains how to evaluate your own inputs.

The sections below describe **benchmark-tool reporting behavior** and metric definitions. See the [arXiv v1 paper](https://arxiv.org/html/2610.35358v1) for the study methodology.

## Field metrics

The [F1 score](../get-started/concepts-and-glossary.md#f1-scores) combines precision and recall against archived GKG output. Higher is better. [Mean absolute error (MAE)](../get-started/concepts-and-glossary.md#mae) is the average absolute difference between paired values. Lower is better. [Lin's concordance correlation coefficient (CCC)](../get-started/concepts-and-glossary.md#ccc) measures paired-value agreement, with one denoting perfect concordance. [Global Content Analysis Measures (GCAM)](../get-started/concepts-and-glossary.md#gcam-and-dimensions) coverage measures supported vocabulary, independently of agreement on its values. Publisher revisions and body extraction differences contribute to disagreement alongside dictionary and extraction differences.

### Report populations and undefined scores

Metadata fields each receive one validity row. F1 calculations always include precision and recall. Coverage rows carry evaluated-document, reference-support and prediction-support counts. Tone components and GCAM families use separate rows for numeric errors and associated diagnostics. Correlations are undefined when either sequence is constant. CCC is undefined for fewer than two pairs or a zero denominator; different constant sequences yield CCC = 0.

Label-macro rows average over the union of observed reference and prediction labels. Per-label precision or recall with zero support contributes zero to that macro average. An entirely empty label population has undefined macro scores. Validity rows concern the evaluated matched-document population. Alignment and input audits account separately for unmatched or structurally unreadable rows.

## GCAM metrics

Presence requires a positive lexical count; a weighted score alone does not establish presence. Read micro F1 alongside label-macro F1, mean article F1, [Jaccard similarity](../get-started/concepts-and-glossary.md#jaccard-similarity) and dictionary-specific rows. Pooled micro-F1 sums matches, false positives and false negatives across articles before calculating the score. Frequent categories dominate micro-F1. Label-macro gives every observed category equal weight. Both-empty articles are excluded from mean article F1/Jaccard and counted separately. Exact set agreement includes them.

If a native weighted score lacks a companion count, that article/category count comparison is excluded on both sides. Reconstructed-only counts outside those exclusions can still contribute false positives.

| Presence scope | What it evaluates |
| --- | --- |
| **Presence** | All observed reference/prediction categories in the evaluated language streams, including categories the declared profile does not implement. This combines coverage gaps and matching errors. |
| **Supported presence** | Applicable dimensions implemented by the selected lexicon, including approximations. This measures agreement within that inventory. |

Dictionary exclusions apply to both scopes. For example, if the reference contains categories A, B and C, the profile implements A and B, and the prediction correctly finds A and B, presence recall is 2/3 while supported recall is 1. Both rows coincide for a dictionary whose observed categories are fully implemented. Their overall GCAM rows can differ because the reference also contains missing dictionaries or dimensions. Count-error rows use supported dimensions. Unimplemented counts are not assumed to be known zeros.

Count rows include MAE, [root mean square error (RMSE)](../get-started/concepts-and-glossary.md#rmse), [weighted absolute percentage error (WAPE)](../get-started/concepts-and-glossary.md#wape), [bias](../get-started/concepts-and-glossary.md#bias), exact agreement, agreement within one occurrence and mean per-dimension CCC. **Active supported counts** include only article/category pairs where either count is positive, so absent/absent pairs cannot dilute their errors. WAPE divides total absolute error by total reference occurrences and is undefined when that total is zero. It can exceed 100%. Density errors use each side's own word count and require both positive denominators. Weighted scores have separate availability precision/recall/F1, paired score errors, means and [Bland–Altman limits of agreement](../get-started/concepts-and-glossary.md#limits-of-agreement). Sign agreement alone is weak evidence for scores whose scale is always positive.

## Matching and field calculations

Exact comparisons are always reported. Their primary definitions preserve document-level identity sets for themes, names, places, dates, amounts and quotations. Count quantities and objects retain repeated tuples as multisets. Text normalization applies Unicode NFKC, case folding, apostrophe normalization and whitespace collapse. Punctuation is retained. Theme codes match exactly. Enhanced fields have separate content-occurrence, exact-offset and tolerant-offset rows. Matches are one-to-one, maximizing the number of valid pairs before minimizing offset distance.

### Invalid fields

Malformed native fields are excluded only from that field's evaluated population. Malformed categorical predictions are audited and scored as empty predictions. Their reference observations count as false negatives. Numeric-score errors use valid paired values, with missing/invalid coverage reported separately. Both-empty documents do not increase F1. Extra XML uses canonical structure comparison and rejects entity declarations. Translation-information scores compare recorded source languages and translation engines; they do not measure translation quality.
