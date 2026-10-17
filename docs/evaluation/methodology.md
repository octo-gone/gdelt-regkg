# Evaluation methodology

Agreement with archived GKG output depends on the reconstruction and the available input text. The [published results](results.md) identify the evaluated population and configuration. The [benchmark guide](../guides/benchmarking.md) explains how to evaluate your own inputs.

## Field metrics

F1 summarizes precision and recall against archived GKG output; higher is better. MAE is average absolute error; lower is better. Lin's concordance correlation coefficient (CCC) measures paired-value agreement, with one denoting perfect concordance. GCAM coverage measures supported vocabulary, independently of agreement on its values. Publisher revisions and body extraction differences contribute to disagreement alongside dictionary and extraction differences.

### Report populations and undefined scores

Metadata fields each receive one validity row. F1 calculations always include precision and recall. Coverage rows carry evaluated-document, reference-support and prediction-support counts. Tone components and GCAM families use separate rows for numeric errors and associated diagnostics. Constant or insufficient samples have undefined correlations and concordance rather than perfect scores.

Label-macro rows average over the union of observed reference and prediction labels. Per-label precision or recall with zero support contributes zero to that macro average; an entirely empty label population has undefined macro scores. Validity rows concern the evaluated matched-document population; alignment and input audits account separately for unmatched or structurally unreadable rows.

## GCAM metrics

Presence measures whether a category occurs, regardless of its count. Read micro F1 alongside label-macro F1, mean article F1/Jaccard and dictionary-specific rows. Frequent categories dominate micro F1; label-macro gives every observed category equal weight. Both-empty articles are excluded from mean article F1/Jaccard and counted separately. Exact set agreement includes them.

| Presence scope | What it evaluates |
| --- | --- |
| **Presence** | All observed reference/prediction categories in the evaluated language streams, including categories the declared profile does not implement. This combines coverage gaps and matching errors. |
| **Supported presence** | Applicable dimensions implemented by the selected lexicon, including approximations. This measures agreement within that inventory. |

Dictionary exclusions apply to both scopes. For example, if the reference contains categories A, B and C, the profile implements A and B, and the prediction correctly finds A and B, presence recall is 2/3 while supported recall is 1. Both rows coincide for a dictionary whose observed categories are fully implemented. Their overall GCAM rows can differ because the reference also contains missing dictionaries or dimensions. Count-error rows use supported dimensions; unimplemented counts are not assumed to be known zeros.

Count rows include MAE, RMSE, WAPE, bias, exact agreement, agreement within one occurrence and mean per-dimension CCC. **Active supported counts** include only article/category pairs where either count is positive, so absent/absent pairs cannot dilute their errors. WAPE divides total absolute error by total reference occurrences and is undefined when that total is zero; it can exceed 100%. Density errors use each side's own word count and require both positive denominators. Weighted scores have separate availability precision/recall/F1, paired score errors, means and Bland–Altman limits of agreement. Sign agreement alone is weak evidence for scores whose scale is always positive.

## Sampling and interpretation

The published full-corpus results use retained English articles; the restricted subset additionally requires exact normalized titles and local/native word-count ratios between 0.90 and 1.10. Similar word counts do not establish identical bodies, and subset selection changes the population. See [results](results.md#english-articles) for exact sample sizes and exclusions.

Publisher-cluster bootstrap intervals account for shared sources in the retained sample. They do not correct retrieval bias, changed article bodies, reference errors or dictionary coverage gaps. The CLI can apply language and size filters, reproducible reservoir sampling and publisher-cluster resampling; see [GCAM agreement and sampling](../guides/benchmarking.md#gcam-agreement-and-sampling).

Select rules on development articles and reserve separate articles for evaluation. Do not tune on the published held-out benchmark. Vocabulary coverage measures representable dimensions; it does not establish agreement in detections, counts or weighted scores. Translation results combine retrieval, translation and extraction differences and do not independently measure translation quality.

## Matching and field calculations

Exact comparisons are always reported. Their primary definitions preserve document-level identity sets for themes, names, places, dates, amounts and quotations. Count quantities and objects retain repeated tuples as multisets. Text normalization applies Unicode NFKC, case folding, apostrophe normalization and whitespace collapse; punctuation is retained. Theme codes match exactly.

Enhanced fields have separate content-occurrence, exact-offset and tolerant-offset rows. Matches are one-to-one, maximizing the number of valid pairs before minimizing offset distance. `--offset-tolerance` defaults to 100 characters. Offset-error rows use content matches before the tolerance gate, so large errors are visible. Error units and tolerance settings appear in row labels or cells. Repeated identical mentions can have multiple equally optimal pairings. Their median and P90 errors can depend on the selected pairing even when match counts and mean error agree. The run report records statistical-library versions.

`--relaxed` adds separate rows for approximate quantities and objects, and fuzzy quotation spans. Its options are `--number-tolerance` (relative error, default 0.1), `--object-similarity` (default 0.6) and `--quote-similarity` (default 0.5). Relative number error divides by the larger of the absolute reference value and one. Similarity uses a character sequence ratio. Relaxed quotation matches also use the configured offset tolerance. These scores have different definitions from exact identity scores and should be compared separately.

### Invalid fields

Malformed native fields are excluded only from that field's evaluated population. Malformed categorical predictions are audited and scored as empty predictions; their reference observations count as false negatives. Numeric-score errors use valid paired values, with missing/invalid coverage reported separately. Both-empty documents do not increase F1. Extra XML uses canonical structure comparison and rejects entity declarations. Translation-information scores concern provenance, not translation quality.
