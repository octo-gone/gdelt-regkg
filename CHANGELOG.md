# Changelog

This changelog records implementation changes and the research behind each version. Versions group the iterative work; dictionary revisions such as tone v3 are separate from package versions. Each Research section includes the method, results and conclusions for that stage.

## Research method

Original archives from `http://data.gdeltproject.org/gdeltv2/` provide label inventories and reference outputs. Prepared Parquet bodies support execution checks; matched comparisons retrieve full text from the article URLs in GKG. The [GKG 2.1 codebook](https://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf) defines the output format. Published label lists identify codes but do not reveal GDELT's complete trigger dictionaries.

| Research step | Inputs and tools | What is measured |
| --- | --- | --- |
| Inventory and prioritization | Original count/theme cells and frequency CSVs | Observed vocabulary, label frequency, cumulative coverage |
| Rule construction | Authored quantity/phrase rules, CrisisLexRec terms, General Inquirer categories | Candidate rules and their sources; label frequencies do not reveal triggers |
| Prepared-body execution | Prepared rules, spaCy NER, quotation spans, optional M2M100 translation | Field population, offsets, model differences, errors and export behavior |
| Matched extraction comparison | Original records paired by URL and batch with retrieved bodies | Tone, themes, counts, entities, locations, dates, amounts, names and GCAM agreement on cached inputs |
| GCAM dictionary expansion | Published General Inquirer, Roget, WordNet and VADER resources with native codebook mappings | Dimension/occurrence coverage, category presence, count error and weighted-value agreement |
| Rule improvement | Training dates for fitting, separate development dates for selection | Freeze selected rules before scoring a new final sample; exclude known URLs and duplicate bodies |

**We do not have the exact article bodies GDELT processed.** Publisher pages may have changed, and HTML extraction or translation can produce different text. These differences can lower F1 even when an extractor is correct on the retrieved body. Scores therefore measure agreement with stored GDELT outputs, combining input differences and extraction errors; they are not human-annotated NLP accuracy. The comparison uses Trafilatura without comments, tables or prepended titles. URLs retain their original protocols, selections are fixed before fetching, and failed retrievals are recorded rather than replaced.

Training articles are used to fit rules; validation articles select among candidates. A reserved benchmark evaluates frozen choices. Once its outputs guide changes, that sample becomes development data and a new benchmark is needed. Later GCAM stages use published source mappings rather than benchmark-derived word edits. Replays of an existing benchmark are identified explicitly. Offsets require identical analyzed text and are not scored here; similar word counts are only a diagnostic.

Archive timestamps identify processing batches, not publication times. Sampling only the start of a UTC day can miss publishers in other time zones and topics covered during business hours or scheduled events. Early checks used a few batches; the seasonal comparison uses six windows across each sampled day and several months. Source caps and retrieval failures can still change the topic mix, so the samples do not represent all GDELT output.

F1 summarizes precision and recall; higher is better. MAE is average absolute error, and bias is local minus native output. Count WAPE is total absolute count error divided by total native counts, expressed as a percentage; lower is better. Correlation measures whether values vary together, not whether they match. Vocabulary coverage counts supported labels or dimensions; occurrence coverage weights them by their frequency. Neither is extraction accuracy. Tone sign comparisons treat values within ±0.5 points as neutral. `pp` means percentage points.

Resource revision numbers such as tone v3 are independent of package versions. Historical profiles can now be rebuilt locally using [Installation and setup](docs/installation.md); external vocabularies and model weights are not shipped with the current package.

## 0.1.0 Initial implementation

### Changes

- Added basic extraction and metadata formatting, spaCy NER, translation and streaming export.
- Added the first count rules and the 287-label theme profile.

### Research

#### Implementation review

The initial implementation supplied 21 of the 27 field functions, including approximate text extraction, spaCy entities, translation and metadata formatting. Streaming export, parallel workers, translation caching and checkpoint/resume were already available. Locations, date mentions, GCAM, all names and amounts still needed implementations. Execution checks established that the pipeline could produce rows, but did not establish equivalent extraction.

#### Count and theme inventory

The first inventory counted labels in original GKG archives, separately from the locally reconstructed article dataset. Counts are ranked by tuple occurrences, not by the numeric quantities inside them; themes are ranked by per-record label assignments, not by the percentage of articles. The sample mainly covers a short archive period, so [version 0.4.0](#040-tone-dictionary-refinement) checks its vocabulary across years.

##### Count labels

The implementation's 37 count labels match the observed inventory. Extending the label list was therefore less urgent than recognizing quantities, triggers, objects and repeated mentions correctly. The most frequent labels dominate the output; the top fifteen account for 95% of count tuples.

| Most frequent count labels | Share of count tuples |
| --- | ---: |
| `KILL` | 25.23% |
| `CRISISLEX_T03_DEAD` | 17.51% |
| `ARREST` | 7.89% |
| `CRISISLEX_T02_INJURED` | 7.43% |
| `CRISISLEX_CRISISLEXREC` | 6.82% |

##### Theme dictionary

Theme coverage is much more dispersed. The inventory contains 12,096 distinct labels; reaching broad coverage requires a larger dictionary than the crisis/count mappings alone.

| Share of theme assignments | Labels required |
| --- | ---: |
| 50% | 99 |
| 70% | 246 |
| 80% | 407 |
| 90% | 785 |
| 95% | 1,327 |

| Theme family | Share of assignments |
| --- | ---: |
| World Bank | 27.55% |
| `TAX_FNCACT` | 19.92% |
| Other native labels | 10.48% |
| EPU | 7.15% |
| CrisisLex | 5.44% |

The 287-label v2 profile was built by combining [authored crisis/count rules](src/gdelt_regkg/resources/themes/themes-count-candidates-v2.json), separately obtained CrisisLexRec terms and [authored news mappings](src/gdelt_regkg/resources/themes/theme_seeds.json). The news mappings add roles and World Bank, EPU and UNGP labels. This is a selected rule set, not simply the most frequent 287 labels copied from the inventory: statistics supply priorities and output codes, while phrases, aliases, conditions and parent labels are authored approximations.

| Profile | Enabled rules | Labels | Share of theme assignments | Change |
| --- | ---: | ---: | ---: | ---: |
| Crisis/count mappings | 446 | 37 | 8.02% | — |
| With authored news mappings, v2 | 692 | 287 | 60.63% | +52.61 pp |

The original [count profile](src/gdelt_regkg/resources/lexicons/counts.v1.json) uses quantity rules to emit the observed count labels. CrisisLexRec terms are imported separately under their [source terms](docs/installation.md#third-party-terms); EMTerms import is also supported. These inventories establish vocabulary coverage, not document-level precision or recall.

## 0.2.0 Counts quotations and entity checks

### Changes

- Aligned legacy/enhanced count formatting, including repeated entries and multiple labels for a quantity.
- Added quotation extraction and compared small/medium NER outputs on prepared bodies.

### Research

#### Count quantities, duplicates, and offsets

The count pilot compared legacy and enhanced cells in two midday archives. After removing enhanced offsets, their entries matched in every inspected row, including repetitions. Repeated entries and multiple labels for the same quantity are native behavior, so the implementation must preserve them rather than automatically deduplicate everything.

| Observation | Result |
| --- | ---: |
| Inspected rows | 3,233 |
| Rows containing counts | 369 |
| Entries in each count column | 1,487 |
| Legacy/enhanced mismatches without offsets | 0 |
| Duplicate enhanced entries | 86 |
| Quantity groups emitting multiple labels | 444 of 717 |
| Entries with empty objects | 1,091 |
| Positive / zero enhanced offsets | 1,430 / 57 |

Common paired labels included `KILL` with `CRISISLEX_T03_DEAD`, and `ARREST` with `CRISISLEX_C07_SAFETY`. Live-page examples also showed qualified nominal quantities and a percentage serialized as a count. They helped investigate triggers but were not scored examples, because the retrieved bodies were not verified as GDELT's original inputs. Exact duplicate and offset behavior remains unresolved.

#### Extraction and NER model checks

A prepared-body check used the small English spaCy model on a sample from the Parquet dataset. Processing completed without errors. The table shows field population, not agreement with GDELT; geography, dates, GCAM, all names and amounts were still unavailable at this stage.

| Sample or field | Articles |
| --- | ---: |
| Processed sample | 462 |
| Counts populated | 25 |
| Themes populated | 409 |
| Persons populated | 418 |
| Organizations populated | 441 |
| Tone populated | 462 |
| Quotations found in the later check | 292 |

Quotation processing was then checked for spans, reporting verbs and malformed delimiters. It found ordinary quoted spans but also unclosed quotations.

| Quotation diagnostic | Spans or issues |
| --- | ---: |
| Quoted spans | 1,780 |
| Spans with reporting verbs | 740 |
| Unclosed quotations | 28 |
| Delimiter issues | 5 |

A separate 100-article small/medium NER comparison returned different entity sets in 97 articles.

| Model | Person mentions | Organization mentions | Location mentions | Local analysis time |
| --- | ---: | ---: | ---: | ---: |
| `en_core_web_sm` | 1,112 | 1,293 | 931 | 9.74 s |
| `en_core_web_md` | 1,097 | 1,360 | 1,065 | 8.62 s |

An entity containing a reserved delimiter exposed a serialization failure. More mentions did not establish better accuracy, and recognized place names were not yet resolved GKG location tuples. These checks justified adding matched benchmarks before choosing models or refining rules.

## 0.3.0 Tone benchmark

### Changes

- Added comparison of retrieved article tone with stored GDELT tone vectors.

### Research

The first tone comparison paired native tone vectors from column 16 with retrieved bodies from two archive days. Source-round-robin selection limited repeated publishers. General Inquirer v1 scores each category as `100 × matching token occurrences / total tokens`; tone is positive density minus negative density. Numbers, stopwords, internal apostrophes and hyphens are retained. No stemming, contextual disambiguation or negation reversal is applied. GDELT uses its own [bag-of-words dictionaries](https://blog.gdeltproject.org/geg-comparing-classical-bag-of-word-and-neural-sentiment-algorithms/).

| Sample | Selected URLs | Usable bodies | Tone MAE | Tone RMSE | Bias | Pearson | Within ±1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| First sample | 150 | 112 | 2.78 | 3.61 | +2.33 | 0.560 | 25.0% |
| Second sample | 100 | 80 | 2.90 | 3.74 | +1.66 | 0.521 | 21.3% |
| Combined | 250 | 192 | 2.83 | 3.66 | +2.05 | 0.535 | 23.4% |

The scorer was too positive relative to GDELT. Activity was strongly underestimated, while self/group density was strongly overestimated. This suggested category-dictionary problems beyond a single tone offset.

| Component | Combined MAE | Combined bias |
| --- | ---: | ---: |
| Tone | 2.83 | +2.05 |
| Positive density | 2.34 | +1.93 |
| Negative density | 1.56 | −0.12 |
| Polarity | 2.58 | +1.45 |
| Activity density | 14.45 | −14.45 |
| Self/group density | 7.01 | +6.94 |
| Word count | 157.68 words | +118.31 words |

Restricting the comparison to bodies within 10% of native word count still left substantial tone error. That points to scoring or dictionary differences as well as body differences, although similar length cannot establish identical text. Retrieval failures were mostly restricted or unavailable pages; this early sample had no independent language audit.

## 0.4.0 Tone dictionary refinement

### Changes

- Added tone v2 with revised sentiment, activity and self/group dictionaries.
- Checked count/theme vocabulary across years and kept a numerical tone offset out of the scorer.

### Research

#### Tone bias correction

A constant correction learned from the first tone sample was tested on the second. It reduced average tone error, including on previously unseen sources, but **was not adopted**: subtracting an offset from net tone alone would break `tone = positive − negative` and leave the other tone-vector components unchanged.

| Evaluation | Original tone MAE | With offset |
| --- | ---: | ---: |
| Separate second sample | 2.90 | 2.24 |
| Unseen sources and bodies | 2.89 | 2.27 |

The next step was to refine positive, negative, activity and self/group dictionaries while retaining the scoring formula.

#### Tone dictionary refinement

##### Data and splits

A larger retrieved corpus sampled morning, midday and evening batches across six days, with source limits. Separate days were assigned to training, validation and testing. A source-hash group was kept out of fitting, and language screening plus exact/near-duplicate checks reduced cross-split overlap. The duplicate heuristic cannot guarantee removal of all syndicated text.

| Stage | Articles |
| --- | ---: |
| Selected URLs | 2,400 |
| Usable retrieved bodies before screening | 1,846 |
| Retained training split | 796 |
| Training bodies within the fitting length range | 612 |
| Validation | 211 |
| Test | 252 |

Candidate word edits came only from training vocabulary and required repeated appearances in aligned documents. Validation selected the positive/negative pair using tone and category errors, and selected activity and self/group lists using their own errors. Test outputs did not select words or settings.

##### Dictionary changes

| Category | v1 tokens | Revised tokens | Additions | Removals |
| --- | ---: | ---: | ---: | ---: |
| Positive | 1,636 | 1,576 | 8 | 68 |
| Negative | 2,005 | 2,031 | 45 | 19 |
| Activity | 1,567 | 1,725 | 158 | 0 |
| Self/group | 87 | 21 | 9 | 75 |

Positive edits removed broad words such as `company`, `education` and `like`; negative edits added common inflections such as `accused`, `injured` and `losses`. Activity gained verbs and auxiliaries such as `was`, `has` and `said`. The self/group list was narrowed to a small set of pronouns and contractions. These are empirical matches to native scores, not a recovered production dictionary: a selected token can reflect topic or input differences rather than GDELT's grammatical rules.

##### Test results

The comparison uses identical test bodies and the same tokenizer. No numerical bias correction was applied.

| Component | v1 MAE | Revised MAE | v1 bias | Revised bias |
| --- | ---: | ---: | ---: | ---: |
| Tone | 2.93 | 1.92 | +2.20 | +0.36 |
| Positive density | 2.11 | 1.15 | +1.75 | −0.06 |
| Negative density | 1.62 | 1.36 | −0.44 | −0.42 |
| Polarity | 2.24 | 1.89 | +0.99 | −0.53 |
| Activity density | 14.59 | 3.46 | −14.59 | −2.86 |
| Self/group density | 7.43 | 0.30 | +7.43 | +0.15 |
| Word count | 149.34 words | 149.34 words | +124.23 words | +124.23 words |

| Tone diagnostic | v1 | Revised |
| --- | ---: | ---: |
| Pearson correlation | 0.673 | 0.745 |
| Spearman correlation | 0.658 | 0.748 |
| Within ±1 point | 17.9% | 31.7% |
| Sign agreement | 55.2% | 67.9% |

| Test subset | Articles | Tone MAE, v1 → revised | Activity MAE, v1 → revised | Self/group MAE, v1 → revised |
| --- | ---: | ---: | ---: | ---: |
| Sources absent from fitting and validation | 52 | 2.89 → 1.76 | 14.84 → 3.79 | 7.22 → 0.26 |
| Word count within 10% of GDELT | 115 | 2.85 → 1.76 | 15.00 → 3.05 | 8.24 → 0.08 |

Dictionary changes reduced tone error and substantially improved activity and self/group density. Word-count error did not change. The v2 profile remains reproducible for historical comparisons; the current default is v3 from [version 0.7.0](#070-seasonal-evaluation-and-revised-extraction). See [tone formulas](docs/fields/tone.md) and the [reproduction instructions](#reproducing-the-benchmarks).

#### Count labels are sufficient, themes need expansion

The temporal scan checked count and theme vocabularies across years, months and UTC hours. Legacy and enhanced fields were counted separately to avoid doubling occurrences. A second scan rechecked the original reference inventory, including rare labels missing from the temporal sample.

| Sample | Archives | Rows | Malformed rows | Distinct count labels |
| --- | ---: | ---: | ---: | ---: |
| Temporal sample across 2015–2026 | 48 | 92,846 | 4 | 34 |
| Reference recheck | 102 | 158,951 | 2 | 37 |
| Combined | 150 | 251,797 | 6 | 37 |

No new count labels were found. The reference recheck recovered `ASSASSINATION`, `CRISISLEX_T08_MISSINGFOUNDTRAPPEDPEOPLE` and `TAX_FNCACT_STRIKERS`, which were absent from the temporal sample. The implemented label set therefore covers everything observed, although unexamined batches could contain rarer types. Quantity and trigger recognition remain the priority.

##### Missing themes

The temporal sample added labels absent from the earlier inventory, but the implemented theme set still covered only about three fifths of assignments. Broader sampling therefore confirmed that general-news theme expansion was needed.

| Theme measurement | Temporal sample | Combined sample |
| --- | ---: | ---: |
| Distinct legacy labels | 9,786 | 12,204 |
| Legacy theme assignments | 2,261,952 | 6,298,279 |
| Implemented legacy assignment share | 59.64% | 60.49% |
| Implemented enhanced assignment share | 60.68% | — |

| Legacy theme assignment share | Initial sample: labels required | Temporal sample: labels required |
| --- | ---: | ---: |
| 50% | 99 | 100 |
| 70% | 246 | 258 |
| 80% | 407 | 428 |
| 90% | 785 | 838 |
| 95% | 1,327 | 1,440 |

Implemented legacy-theme coverage ranged from 56.99% to 61.15% by year. The combined sample gives extra weight to the original reference period, so the separate temporal scan is the stronger check across years. Frequency tiers describe the highest-ranked labels; merely extending a dictionary to that size does not guarantee their coverage or correct matching.

## 0.5.0 Count theme and NER benchmarks

### Changes

- Added matched extraction benchmarks and individual count, theme and NER commands.

### Research

The first matched count, theme and NER benchmark used the six-day corpus from [version 0.4.0](#040-tone-dictionary-refinement). Both NER models used the same selected URLs and cached bodies. After retrieval and language exclusions, 421 English articles remained.

| Measurement | Precision | Recall | F1 |
| --- | ---: | ---: | ---: |
| Themes, complete native vocabulary | 0.6375 | 0.3397 | 0.4432 |
| Themes, supported labels only | 0.6375 | 0.5684 | 0.6009 |
| Count labels | 0.6667 | 0.2549 | 0.3688 |
| Count label + quantity, multiset | 0.4600 | 0.1597 | 0.2371 |
| Count label + quantity, deduplicated | 0.4583 | 0.1667 | 0.2444 |
| Count label + quantity + normalized object | 0.3400 | 0.1181 | 0.1753 |
| Full count tuple including geography | 0.0000 | 0.0000 | 0.0000 |
| Persons, small model, normalized names | 0.3579 | 0.7055 | 0.4749 |
| Persons, medium model, normalized names | 0.3970 | 0.7472 | 0.5185 |
| Organizations, small model, normalized names | 0.0819 | 0.2854 | 0.1272 |
| Organizations, medium model, normalized names | 0.0866 | 0.2937 | 0.1337 |

Theme recall was limited both by unsupported labels and by missed matches within the supported vocabulary. Counts had weak recall, while missing geography prevented complete tuple matches. Count evidence was sparse: only 51 scored articles contained native counts. Medium NER improved person agreement slightly but did little for organizations.

NER scores compare per-article name sets after Unicode, case, whitespace and apostrophe normalization. Raw-name person F1 was zero, showing that native name formatting needed attention alongside entity recognition. Word-count similarity does not verify input equality. Once these results informed the following changes, this corpus became development data rather than an untouched benchmark.

The maintained tools are `gdelt-regkg-benchmark-extraction` and the separate NER, count and theme commands. See [metric definitions and commands](scripts/README.md#ner-count-and-theme-benchmarks).

## 0.6.0 Theme count and name improvements

### Changes

- Expanded themes to 519 labels and added native-style name normalization.
- Introduced counts v2 and evaluated frozen choices on a new independent sample.

### Research

#### Theme and NER improvements

Theme and name-policy development reused [version 0.4.0](#040-tone-dictionary-refinement)'s training and validation splits. Its previously examined test day was also treated as development data; [version 0.6.0](#060-theme-count-and-name-improvements) collected a new independent sample. Candidate phrases came only from training articles, with minimum document/source support and a positive association with the label. Validation compared precision thresholds; training-only review removed obvious topic proxies.

| Theme profile | Enabled rules | Labels |
| --- | ---: | ---: |
| v2 | 692 | 287 |
| v3 | 1,315 | 519 |

The selected [theme revision](src/gdelt_regkg/resources/themes/revision.v3.json) expands coverage and matching rules. The resource builder replays recorded edits without fitting against benchmark articles.

NER compared source spelling with two native-style formatting policies on the same detected mentions. Validation selected `gdelt-full-names`, which normalizes spelling and omits single-word person and organization names. The detector was not retrained. Original mentions and offsets remain available, and alternative policies can retain valid single-word organizations that this policy excludes.

| Development validation measurement | Baseline F1 | Selected F1 |
| --- | ---: | ---: |
| Themes, all native labels | 0.4233 | 0.6108 |
| Persons, medium model | 0.4820 | 0.6522 |
| Organizations, medium model | 0.1298 | 0.3005 |

Theme expansion and name normalization improved validation agreement. These are candidate-selection scores; the following independent comparison measures the frozen choices.

#### Count rule calibration

Count development tested broader grammar, extra vocabulary, death phrases and duplicate suppression. The broad candidate reduced validation agreement, and a guard against time expressions such as `injured two weeks ago` gave no overall gain.

Training evidence instead supported two narrow changes: numeric `arrested` matches also emit `SOC_GENERALCRIME`, and the `{number} patients` nominal-total rule is disabled. Hospitalization and sickness event rules remain active. The resulting [counts v2](src/gdelt_regkg/resources/lexicons/counts.v2.json) retains the observed label vocabulary.

| Count label/quantity validation | F1 |
| --- | ---: |
| Existing rules | 0.2752 |
| Broad candidate | 0.2564 |
| Selected narrow changes | 0.3009 |

Adding grammar indiscriminately can introduce more false matches than useful detections. The narrow changes were frozen with themes and NER before the independent comparison.

#### Independent comparison

Frozen theme, count and NER choices were evaluated on newly collected archive days, using morning, midday and evening batches and source limits. Previously selected URLs and exact/near-duplicate bodies were excluded. No rules were changed after inspecting these results.

| Collection | Size |
| --- | ---: |
| Selected URLs | 1,200 |
| English scored bodies before duplicate exclusion | 816 |
| Final articles | 775 |
| Sources | 690 |

| Measurement | Baseline F1 | Current precision | Current recall | Current F1 |
| --- | ---: | ---: | ---: | ---: |
| Themes, all native labels | 0.4349 | 0.6785 | 0.5820 | 0.6265 |
| Themes, enabled labels only | 0.6006 | 0.6785 | 0.7497 | 0.7123 |
| Count labels | 0.4444 | 0.6577 | 0.3650 | 0.4695 |
| Count label + quantity, multiset | 0.3750 | 0.6241 | 0.2963 | 0.4018 |
| Count label + quantity, deduplicated | 0.3886 | 0.6183 | 0.3127 | 0.4154 |
| Count label + quantity + normalized object | 0.2407 | 0.4043 | 0.1919 | 0.2603 |
| Full count tuple including geography | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Persons, small model | 0.4540 | 0.5493 | 0.7163 | 0.6218 |
| Persons, medium model | 0.4996 | 0.5958 | 0.7559 | 0.6663 |
| Organizations, small model | 0.1102 | 0.2161 | 0.4377 | 0.2894 |
| Organizations, medium model | 0.1155 | 0.2151 | 0.4326 | 0.2873 |

The comparison uses themes v2/counts v1/source-spelling NER versus themes v3/counts v2/`gdelt-full-names`. Counts retain repeated occurrences unless marked deduplicated. Theme and person agreement improved, but organizations remained weak. Count recall was still limited, and full tuples could not match without geographic resolution.

| Native theme assignment coverage | Share |
| --- | ---: |
| v2 | 58.21% |
| v3 | 77.62% |

| Current subset | Articles | Theme F1, all labels | Count label/quantity F1 | Person F1, medium | Organization F1, medium |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sources absent from every earlier usable-body sample | 440 | 0.6245 | 0.2809 | 0.6734 | 0.3017 |
| Word count within 10% of GDELT | 395 | 0.6437 | 0.4108 | 0.7274 | 0.3302 |

| Tone diagnostic on the same articles | v1 | v2 |
| --- | ---: | ---: |
| MAE, points | 3.04 | 1.91 |
| Bias, points | +2.59 | +0.67 |
| Pearson correlation | 0.668 | 0.758 |
| Within ±1 point | 20.4% | 36.5% |

The unchanged tone v2 profile also improved agreement over v1 on this new sample. This supported the earlier dictionary changes without refitting them. The [report](docs/reports/benchmark-results-previous.json) retains component scores, count totals, failures and profile checksums. Further tuning needed another reserved sample.

## 0.7.0 Seasonal evaluation and revised extraction

### Changes

- Separated large seasonal development and benchmark samples, including CUDA-translated bodies and large-model NER.
- Added tone/counts v3, person-title normalization and organization filtering.

### Research

#### Seasonal development

Two larger samples were fixed before retrieval, with different months for development and benchmarking. The [saved plan](scripts/benchmark-plan.json) defines dates, source caps and selection seeds. Each sample spans four seasonal month groups and six UTC windows per day. The months are interleaved across years, so this tests generalization across seasons rather than forecasting only future articles.

| Sample design | Development | Benchmark |
| --- | --- | --- |
| Month groups | January, April, July, October | February, May, August, November |
| Selected English / translated URLs | 4,320 / 480 | 4,320 / 480 |
| Sampled days | 8 | 8 |
| UTC windows per day | 6 | 6 |

Within development, the first sampled day in each month supplies training and the second supplies validation. A source-hash group is excluded from training, and exact/near-duplicate bodies are removed. English bodies alone are used for fitting; translated bodies form a separate processing check.

| Retained development split | Articles |
| --- | ---: |
| Training | 1,059 |
| Validation | 1,322 |
| Training bodies within the tone fitting length range | 778 |

Tone v3 uses bounded training-vocabulary edits selected on validation, preserving the scoring formula. Count v3 adds bounded auxiliaries, adverbs, object nouns, participles and death-toll constructions without adding labels. Label pruning, generic-object omission and time-unit exclusions did not improve selection and were discarded. Geography and general count coreference were still absent at this stage.

Name rules remove leading person titles. Organization filtering uses a fixed logistic model trained on native per-article name presence; runtime needs only its recorded coefficients. Validation selects the filter strength and threshold. It may discard genuine organizations because it targets GKG agreement rather than human-annotated entity accuracy.

| Development validation metric | Baseline | Selected | Difference |
| --- | ---: | ---: | ---: |
| Tone MAE, points | 1.951 | 1.691 | -0.260 |
| Tone bias, points | 0.543 | 0.123 | -0.420 |
| Counts label/quantity F1 | 0.3053 | 0.3732 | +0.0678 |
| Counts including object F1 | 0.1399 | 0.2071 | +0.0671 |
| Person F1, medium | 0.6477 | 0.6541 | +0.0064 |
| Organization F1, medium | 0.2964 | 0.4435 | +0.1471 |
| Person F1, large | 0.6652 | 0.6716 | +0.0064 |
| Organization F1, large | 0.3009 | 0.4418 | +0.1409 |

The selected profiles are tone v3, counts v3, unchanged themes v3 and name rules v1. Organization filtering improves precision at the cost of recall; person changes are small. These are validation results, and all choices were frozen before the benchmark.

#### Seasonal benchmark

The benchmark uses months and selected URLs distinct from development. Rules, coefficients and model choices were frozen before scoring. The same retained bodies are used for each configuration within a cohort; no benchmark output was used for fitting or further selection.

| Split/cohort | Selected URLs | Prepared bodies | Fetch failures | Body/length failures | Language exclusions | Translation failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Development, english | 4,320 | 2,707 | 1,027 | 138 | 448 | 0 |
| Development, translated | 480 | 304 | 74 | 9 | 60 | 33 |
| Benchmark, english | 4,320 | 2,733 | 1,085 | 112 | 390 | 0 |
| Benchmark, translated | 480 | 320 | 69 | 4 | 51 | 36 |

| Final cohort after duplicate exclusion | Articles | Sources |
| --- | ---: | ---: |
| English | 2,626 | 1,808 |
| Translated | 317 | 292 |

Retrieval, language and translation failures are excluded from scoring and are not replaced. Exact/near-duplicate checks compare both source-language and analyzed English bodies with earlier corpora and development. Quotas apply to selected URLs, not successfully retrieved bodies.

##### English agreement

| Field and model | Baseline F1 | Current precision | Current recall | Current F1 | Difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| Themes, all labels | 0.6238 | 0.6743 | 0.5804 | 0.6238 | +0.0000 |
| Themes, enabled labels | 0.7087 | 0.6743 | 0.7469 | 0.7087 | +0.0000 |
| Counts, label/quantity | 0.2752 | 0.4595 | 0.2368 | 0.3126 | +0.0374 |
| Counts, including object | 0.1353 | 0.2583 | 0.1331 | 0.1757 | +0.0403 |
| Counts, full tuples | 0.0067 | 0.0165 | 0.0085 | 0.0112 | +0.0045 |
| Persons, small | 0.6116 | 0.5372 | 0.7162 | 0.6139 | +0.0023 |
| Persons, medium | 0.6522 | 0.5811 | 0.7535 | 0.6561 | +0.0040 |
| Persons, large | 0.6655 | 0.5977 | 0.7624 | 0.6701 | +0.0046 |
| Organizations, small | 0.2906 | 0.5192 | 0.3821 | 0.4402 | +0.1496 |
| Organizations, medium | 0.2887 | 0.5029 | 0.3746 | 0.4294 | +0.1407 |
| Organizations, large | 0.2907 | 0.4994 | 0.3741 | 0.4277 | +0.1371 |

The comparison uses tone/counts v2 without name rules versus tone/counts v3 with name rules; themes v3 is unchanged. Person and organization scores compare normalized per-article names. Count metrics preserve multiplicity, and themes compare per-article label sets. Organizations gain most from the new filter; the large model gives the strongest person agreement, while the small model is slightly better for organizations. Count recall remains weak, especially when object equality is required.

Full-count scores here precede geographic resolution and mainly test empty-geography tuples. They do not measure the later location implementation. Unsupported labels account for 22.30% of native theme assignments, limiting recall even with perfect phrase detection. Compare configurations within this table: the earlier independent comparison used different articles.

##### Translingual agreement

Source-language bodies from original translation records were translated with cached M2M100 418M on CUDA, using fp16, chunk size 384, batch size 8 and one beam. All retained articles were locally translated and span 40 source languages. Incomplete or non-English outputs were excluded. GDELT's English translations are unavailable, so these scores combine retrieval, translation and extraction differences rather than isolating translation quality.

| Field and model | Baseline F1 | Current precision | Current recall | Current F1 | Difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| Themes, all labels | 0.4446 | 0.5985 | 0.3537 | 0.4446 | +0.0000 |
| Themes, enabled labels | 0.5041 | 0.5985 | 0.4355 | 0.5041 | +0.0000 |
| Counts, label/quantity | 0.1429 | 0.2381 | 0.0980 | 0.1389 | -0.0040 |
| Counts, including object | 0.0857 | 0.1429 | 0.0588 | 0.0833 | -0.0024 |
| Counts, full tuples | 0.0857 | 0.1429 | 0.0588 | 0.0833 | -0.0024 |
| Persons, small | 0.0763 | 0.0554 | 0.1222 | 0.0763 | +0.0000 |
| Persons, medium | 0.0653 | 0.0467 | 0.1086 | 0.0653 | +0.0000 |
| Persons, large | 0.0715 | 0.0514 | 0.1176 | 0.0715 | +0.0000 |
| Organizations, small | 0.0224 | 0.0456 | 0.0236 | 0.0311 | +0.0087 |
| Organizations, medium | 0.0239 | 0.0494 | 0.0236 | 0.0319 | +0.0081 |
| Organizations, large | 0.0202 | 0.0460 | 0.0216 | 0.0294 | +0.0092 |

English-derived name rules do not reproduce native translated entity outputs well. Counts also remain weak, with few count-positive articles supporting the estimate. No multilingual improvement was inferred from these results, and no candidate was changed afterward.

##### Tone agreement

| Tone metric | English v2 | English v3 | Difference | Translingual v2 | Translingual v3 | Difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| MAE, points | 2.021 | 1.720 | -0.301 | 3.019 | 2.646 | -0.373 |
| Bias, points | 0.559 | 0.132 | -0.428 | 1.033 | 0.384 | -0.649 |
| Pearson | 0.763 | 0.814 | +0.051 | 0.404 | 0.520 | +0.116 |
| Within ±1 | 34.35% | 41.62% | +7.27 pp | 24.92% | 28.39% | +3.47 pp |

Tone improves on both cohorts through vocabulary changes, without numerical bias subtraction or a new token denominator. Correlation is stronger on English than on translated bodies, and exact-value agreement remains approximate.

##### Source and body-length checks

| Current English subset | Articles | Theme F1 | Count label/quantity F1 | Person F1, large | Organization F1, large |
| --- | ---: | ---: | ---: | ---: | ---: |
| Sources absent from every earlier usable-body sample | 777 | 0.6124 | 0.2923 | 0.6725 | 0.3885 |
| Source-hash group excluded from training | 522 | 0.6334 | 0.3777 | 0.6634 | 0.4348 |
| Word count within 10% of native GKG | 1,296 | 0.6516 | 0.3256 | 0.7338 | 0.4675 |

The benchmark is month-disjoint but not fully source-disjoint. New-source count improvement is negligible despite the aggregate gain; organization gains are larger, and person changes remain small. Novel-source tone MAE improves from 2.106 to 1.838 points. Six windows leave most processing batches unsampled, and successful retrieval can alter topic coverage. Similar body lengths do not verify identical text. The [report](docs/reports/benchmark-results.json) retains per-month/window results, per-label scores, split audits and checksums.

## 0.8.0 Remaining extraction fields

### Changes

- Implemented resolved locations, date mentions, amounts, all names and minimal GCAM.
- Shared entity analysis across fields and supplied resolved geography to counts.

### Research

The remaining extraction fields were implemented: resolved locations in both columns, explicit calendar dates, numeric amounts with objects, all names and minimal GCAM. One entity pass supplies persons, organizations, locations and all names. Resolved geography is also passed to counts, and translated English bodies use the same extractors.

The offline gazetteer preserves native feature identifiers and available GAUL ADM2 codes. It contains places observed in reference archives, so recognized names outside the snapshot remain unresolved rather than receiving invented geography. See [location limits](docs/fields/locations.md#limits). GCAM initially covers 8 of the codebook's 2,888 dimensions, using original General Inquirer categories with verified keys. Explicit dates use the `#` separators observed in archives; the benchmark also accepts the commas described in the codebook.

| Geographic reference | Size |
| --- | ---: |
| Observed place records | 17,177 |
| FIPS country codes | 237 |
| Reference archives | 20 from 2015–2019 |

A 96-article development check selected equal numbers of English articles per month from the saved seasonal corpus and used the large NER model. It did not use held-out benchmark bodies to construct resources or select rules. Metrics compare identity sets rather than offsets or repeated mentions; amounts require both numeric value and normalized object.

| Field | Native identities | Predicted identities | Matches | Precision | Recall | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Location feature identity | 350 | 361 | 220 | 0.6094 | 0.6286 | 0.6188 |
| Calendar date | 94 | 237 | 83 | 0.3502 | 0.8830 | 0.5015 |
| Broad surface name | 929 | 3,540 | 434 | 0.1226 | 0.4672 | 0.1942 |
| Numeric value and object | 338 | 899 | 136 | 0.1513 | 0.4024 | 0.2199 |

Geographic identity has the strongest agreement in this check. Dates find many native references but also extra years and calendar expressions. Broad names and amount objects have low precision. Unresolved and ambiguous place names show that geographic coverage needs checking separately from NER recognition.

| Geographic resolution in development | Spans |
| --- | ---: |
| Recognized | 1,675 |
| Resolved | 1,135 |
| Unknown | 521 |
| Ambiguous | 20 |

A recognized span can contain several comma-separated places, so these diagnostics are not a simple one-to-one entity total.

| GCAM category | Raw count MAE | Density MAE in percentage points |
| --- | ---: | ---: |
| BodyPt | 1.031 | 0.140 |
| Goal | 0.677 | 0.106 |
| Hostile | 3.188 | 0.648 |
| Know | 4.510 | 0.592 |
| Power | 6.323 | 0.827 |
| Vice | 3.802 | 0.956 |
| Virtue | 5.198 | 1.288 |
| Weak | 3.708 | 0.707 |

GCAM category counts are approximate. Normalizing by each document's word count helps compare different lengths but does not remove content differences; unsupported dimensions remain uncomputed. The [development report](docs/reports/extraction-fields-development.json) records the descriptive check. `gdelt-regkg-benchmark-fields` was added to evaluate these fields on saved bodies and original records without fitting or retrieval.

## 0.9.0 VADER and weighted GCAM

### Changes

- Added VADER dictionary-mode mean scores and match counts without changing GKG tone.
- Added custom-profile GCAM evaluation and the initial Lexicoder importer.

### Research

VADER adds GCAM's mean-valence score and match count while leaving the original General Inquirer categories unchanged. Scores average dictionary matches, including repeated and neutral terms. Negation, boosters and compound normalization are disabled to follow [GDELT's dictionary mode](https://blog.gdeltproject.org/vader-sentiment-lexicon-now-available-in-gcam/). No fitted word or weight changes are applied.

This and the following dictionary stages use the seasonal English development and reserved benchmark corpora from [version 0.7.0](#070-seasonal-evaluation-and-revised-extraction). The development check includes all accepted bodies, including duplicates excluded from fitting. Benchmark outputs do not select source vocabulary or matching rules. These are first measurements of the added dimensions on an existing corpus, not newly collected samples.

| VADER metric | Development | Benchmark | Benchmark minus development |
| --- | ---: | ---: | ---: |
| Comparable articles | 2,679 | 2,592 | -87 |
| Mean-score MAE | 0.2121 | 0.2102 | -0.0019 |
| Mean-score bias | -0.0702 | -0.0698 | +0.0004 |
| Pearson correlation | 0.8847 | 0.8979 | +0.0132 |
| Sign agreement | 92.27% | 92.75% | +0.47 pp |
| Word-count MAE | 117.52 | 125.32 | +7.80 |
| Median local/native word-count ratio | 1.0824 | 1.0792 | -0.0032 |

VADER mean scores agree closely with native values. The archives omit its match-count key, so count MAE cannot be estimated. Mean comparisons require a native value and local matches; no-match cases are excluded rather than treated as invented zeros. VADER error uses valence units, not the percentage-point scale of GKG tone.

| General Inquirer category | Benchmark count MAE | Benchmark density MAE in percentage points |
| --- | ---: | ---: |
| BodyPt | 0.739 | 0.146 |
| Goal | 0.473 | 0.102 |
| Hostile | 3.398 | 0.575 |
| Know | 3.712 | 0.521 |
| Power | 5.430 | 0.865 |
| Vice | 4.387 | 0.851 |
| Virtue | 6.535 | 1.191 |
| Weak | 4.182 | 0.720 |

The count categories remain approximate, and adding VADER does not alter GKG tone. [Development](docs/reports/gcam-development.json) and [benchmark](docs/reports/gcam-benchmark.json) reports preserve the detailed results. An optional Lexicoder importer was also introduced with fixture checks; the next experiment tests the actual dictionary.

## 0.10.0 Lexicoder import

### Changes

- Validated Lexicoder import against its original archive, including ZIP, directory and JSON inputs.

### Research

The original Lexicoder archive was imported and evaluated, replacing fixture-only validation. Its four sections map to native positive, negative and negated categories. ZIP, extracted-directory and category-JSON inputs are supported. Vocabulary remains separately supplied under the [publisher's terms](https://www.snsoroka.com/s/LSDagreement.pdf).

| Category | Development count MAE | Benchmark count MAE | Difference | Benchmark count bias | Benchmark density MAE in pp | Benchmark count Pearson |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Negative | 10.068 | 10.492 | +0.424 | -6.750 | 1.939 | 0.780 |
| Positive | 12.964 | 13.499 | +0.535 | -8.661 | 2.696 | 0.809 |
| Negated negative | 0.0240 | 0.0248 | +0.0007 | +0.0156 | 0.0057 | 0.781 |
| Negated positive | 0.0310 | 0.0255 | -0.0055 | +0.0156 | 0.0073 | 0.942 |

Positive and negative counts are systematically underestimated. Low error for negated categories partly reflects the many articles with no native matches, so it does not establish uniformly strong performance. Correlation describes variation in counts, not exact equality.

Matching uses normalized tokens, wildcard prefixes and phrases, selecting the longest nonoverlapping match within each independent category. Lexicoder's additional punctuation, proper-name, negation and false-hit preprocessing modules are not implemented. Unknown native preprocessing and differing article bodies remain possible sources of disagreement. This establishes dictionary-level agreement, not full Lexicoder replication or an improvement to GKG tone. See [development](docs/reports/lexicoder-development.json) and [benchmark](docs/reports/lexicoder-benchmark.json) results.

## 0.11.0 General Inquirer expansion

### Changes

- Expanded GCAM General Inquirer support to 217 of its 228 native categories.
- Added dimension, occurrence and category-presence coverage reporting.

### Research

GCAM expansion maps published dictionaries to native category keys rather than fitting new word lists. The codebook contains 2,888 conceptual dimensions after pairing count/value keys and excluding word count. A few inconsistent source columns required identity to follow the exported key. This is the denominator used throughout the coverage results.

General Inquirer expands to 217 of its 228 native categories. Mapping uses source category columns, marker tags and historical aliases. Case-sensitive labels such as `Food` and `FOOD` remain distinct; ambiguous or absent categories are unsupported. Sense variants are combined without the original disambiguation modules. The original categories and VADER scores keep their earlier behavior.

| Metric | Development | Benchmark | Difference |
| --- | ---: | ---: | ---: |
| Presence precision | 0.9513 | 0.9487 | -0.0025 |
| Presence recall | 0.9243 | 0.9225 | -0.0017 |
| Presence F1 | 0.9376 | 0.9355 | -0.0021 |
| Count WAPE | 36.04% | 37.80% | +1.76 pp |
| Density MAE, pp | 0.9272 | 0.9288 | +0.0016 |
| Median count Pearson | 0.8488 | 0.8103 | -0.0385 |

General Inquirer has strong category-presence agreement, while occurrence counts still differ. The cumulative coverage table in [version 0.16.0](#0160-gcam-theme-counts) compares the staged imports. It measures supported dimensions and native activity assigned to their keys, not correctly reproduced counts.

Expanded categories cannot be compared directly with the original eight-category error average because the evaluated set changes. The [split audit](docs/reports/gcam-expansion-split-audit.json) records that no further duplicate exclusions were needed. [Aggregate results](docs/reports/gcam-expansion-results.json) and the stage's [development](docs/reports/gcam-expansion-1-development.json) and [benchmark](docs/reports/gcam-expansion-1-benchmark.json) reports preserve per-category errors. Tables in [version 0.12.0](#0120-roget-categories) through [version 0.16.0](#0160-gcam-theme-counts) use the corrected combined profile after [version 0.17.0](#0170-wordnet-source-parsing); stage reports also retain earlier results where shared morphology differs.

## 0.12.0 Roget categories

### Changes

- Added optional Roget import covering all 1,042 native Roget categories.

### Research

The converted Roget 1911 dictionary maps all 1,042 native category paths. Mapping follows complete paths rather than printed head numbers. WordNet morphology and literal phrases approximate lemmatized matching; each category counts its longest nonoverlapping matches. The [source documentation](https://www.kovcomp.co.uk/wordstat/Roget.html) identifies gaps in modern vocabulary. The dictionary remains a separate import.

| Metric | Development | Benchmark | Difference |
| --- | ---: | ---: | ---: |
| Presence precision | 0.7796 | 0.7780 | -0.0016 |
| Presence recall | 0.8988 | 0.8976 | -0.0012 |
| Presence F1 | 0.8350 | 0.8335 | -0.0015 |
| Count WAPE | 64.73% | 67.22% | +2.50 pp |
| Density MAE, pp | 0.2001 | 0.2027 | +0.0027 |
| Median count Pearson | 0.7492 | 0.7433 | -0.0059 |

Roget gives the largest increase in supported dimensions. Category presence agrees reasonably well, but count error remains substantial. [Stage development](docs/reports/gcam-expansion-2-development.json), [stage benchmark](docs/reports/gcam-expansion-2-benchmark.json) and [corrected full-profile benchmark](docs/reports/gcam-expansion-6-benchmark.json) retain the comparisons.

## 0.13.0 WordNet lexical categories

### Changes

- Added all 44 native WordNet lexical categories with explicit category-key mapping.

### Research

WordNet 3.1 supplies all 44 native lexical categories. The importer maps file names to GCAM keys rather than assuming numeric order, and omits `NOUN/TOPS`, which has no native counterpart. It combines synonyms and senses, counting a match once per category and occurrence.

| Metric | Development | Benchmark | Difference |
| --- | ---: | ---: | ---: |
| Presence precision | 0.9520 | 0.9483 | -0.0036 |
| Presence recall | 0.9831 | 0.9833 | +0.0002 |
| Presence F1 | 0.9673 | 0.9655 | -0.0018 |
| Count WAPE | 70.30% | 72.97% | +2.67 pp |
| Density MAE, pp | 2.9272 | 2.9525 | +0.0253 |
| Median count Pearson | 0.7919 | 0.7687 | -0.0232 |

Category presence agrees strongly, but combining word senses does not reproduce native occurrence counts. [Stage development](docs/reports/gcam-expansion-3-development.json), [stage benchmark](docs/reports/gcam-expansion-3-benchmark.json) and the [corrected full-profile benchmark](docs/reports/gcam-expansion-6-benchmark.json) retain source/profile hashes and errors.

## 0.14.0 WordNet Affect

### Changes

- Added all 280 native Affect categories and configurable direct/ancestor matching.

### Research

WordNet Affect maps all 280 native categories using the corresponding WordNet 1.6 offsets. Noun-linked adjective, verb and adverb annotations are included. Spelling aliases are normalized, and hierarchy traversal handles a cycle without counting categories repeatedly.

Development compared matching direct labels with adding ancestor categories, across all parts of speech and with nouns alone. Direct labels across all parts of speech had the lowest count error and were selected before benchmark scoring, at the cost of presence recall.

| Affect matching | Development presence F1 | Development count WAPE |
| --- | ---: | ---: |
| All POS with ancestors | 0.4025 | 96.42% |
| All POS with direct labels | 0.3219 | 91.62% |
| Nouns with direct labels | 0.1094 | 97.54% |

| Metric | Development | Benchmark | Difference |
| --- | ---: | ---: | ---: |
| Presence precision | 0.7231 | 0.7287 | +0.0056 |
| Presence recall | 0.2078 | 0.2121 | +0.0044 |
| Presence F1 | 0.3228 | 0.3286 | +0.0058 |
| Count WAPE | 92.06% | 92.28% | +0.22 pp |
| Density MAE, pp | 0.0448 | 0.0457 | +0.0009 |
| Median count Pearson | 0.2792 | 0.2932 | +0.0140 |

Affect is the weakest added dictionary family. Complete vocabulary coverage does not imply accurate matching. Isolated and combined profiles can differ slightly because they combine morphology from different WordNet versions. See [development comparisons](docs/reports/gcam-affect-direct-all-development.json), [combined development](docs/reports/gcam-expansion-4-development.json) and [benchmark](docs/reports/gcam-expansion-4-benchmark.json). Further policy changes require fresh development data.

## 0.15.0 WordNet Domains

### Changes

- Added all 168 native domain categories using their matching WordNet version.

### Research

WordNet Domains adds all 168 native domain labels using WordNet 2.0. Source annotations are resolved against that version, including adjective satellites, and no ancestor labels are invented. Its WordNet version differs from the lexical-category and Affect sources.

| Metric | Development | Benchmark | Difference |
| --- | ---: | ---: | ---: |
| Presence precision | 0.9423 | 0.9399 | -0.0024 |
| Presence recall | 0.7337 | 0.7299 | -0.0038 |
| Presence F1 | 0.8250 | 0.8217 | -0.0033 |
| Count WAPE | 59.03% | 59.92% | +0.89 pp |
| Density MAE, pp | 1.5941 | 1.6013 | +0.0073 |
| Median count Pearson | 0.5900 | 0.5991 | +0.0090 |

Domains contributes a substantial share of native count activity and gives useful category-presence agreement, but missed assignments and count error still limit replication. The source remains separately supplied; see [setup and source terms](docs/installation.md). [Development](docs/reports/gcam-expansion-5-development.json) and [benchmark](docs/reports/gcam-expansion-5-benchmark.json) reports retain category-level measurements.

## 0.16.0 GCAM theme counts

### Changes

- Reused theme matches for 99 of GCAM's 368 theme dimensions.
- Added combined-profile rebuilding and checked indexed wildcard matching for parity.

### Research

The existing theme engine supplies 99 of GCAM's 368 theme dimensions. GCAM counts repeated matched spans rather than binary theme presence. It preserves context guards, removes duplicate identical spans and retains overlaps. Numeric keys come from the codebook; no new theme triggers were fitted for this expansion.

| Metric | Development | Benchmark | Difference |
| --- | ---: | ---: | ---: |
| Presence precision | 0.8054 | 0.8117 | +0.0063 |
| Presence recall | 0.6218 | 0.6263 | +0.0045 |
| Presence F1 | 0.7018 | 0.7070 | +0.0053 |
| Count WAPE | 65.68% | 64.84% | -0.84 pp |
| Density MAE, pp | 0.0453 | 0.0455 | +0.0002 |
| Median count Pearson | 0.7801 | 0.7714 | -0.0088 |

Although many theme dimensions remain unsupported, the selected categories account for most native theme counting activity. Presence agreement is useful, but count error remains high. The cumulative table below compares the resulting profiles.

#### Combined GCAM coverage

| Cumulative profile | Dimensions out of 2,888 | Codebook coverage | Native count-occurrence coverage | Added occurrence coverage |
| --- | ---: | ---: | ---: | ---: |
| V2 plus optional Lexicoder | 13 | 0.45% | 1.39% | — |
| Expanded General Inquirer | 222 | 7.69% | 28.96% | +27.57 pp |
| Add Roget | 1,264 | 43.77% | 44.31% | +15.35 pp |
| Add WordNet lexical categories | 1,308 | 45.29% | 55.03% | +10.72 pp |
| Add WordNet Affect | 1,588 | 54.99% | 55.70% | +0.66 pp |
| Add WordNet Domains | 1,756 | 60.80% | 77.51% | +21.82 pp |
| Add GCAM themes | 1,855 | 64.23% | 77.81% | +0.30 pp |
| Standard local profile, excludes Roget and Lexicoder | 809 | 28.01% | 61.92% | — |

Dimension coverage treats each supported category equally. Native count-occurrence coverage weights categories by their frequency in GDELT. Frequent categories make occurrence coverage higher than dimension coverage; neither measures correctly extracted counts. The standard profile omits Roget and Lexicoder, while the full profile includes them. Both are now built locally from separately obtained sources.

`gdelt-regkg-expand-gcam` rebuilds selected families from their sources; the field benchmark evaluates a frozen profile without fitting. An indexed wildcard matcher was checked against the previous Lexicoder implementation and preserved its counts on development bodies and authored phrases. [Standard-profile development](docs/reports/gcam-expansion-7-development.json), [standard-profile benchmark](docs/reports/gcam-expansion-7-benchmark.json) and [full optional benchmark](docs/reports/gcam-expansion-6-benchmark.json) distinguish the configurations. [Version 0.19.0](#0190-locally-built-resources) removes the historical bundled resources while preserving these outputs.

## 0.17.0 WordNet source parsing

### Changes

- Removed adjective metadata flags before phrase normalization and rebuilt affected profiles.

### Research

A source-format check found that WordNet adjective flags `(a)`, `(p)` and `(ip)` were being treated as words. For example, `in_labor(p)` became “in labor p”. The [WordNet specification](https://wordnet.princeton.edu/documentation/wndb5wn) identifies these suffixes as grammatical metadata. The importer now strips them before normalizing phrases across lexical, Affect and Domains imports.

This correction follows source syntax, not benchmark article errors. Development comparisons still selected direct Affect labels for lower count error. Profiles were rebuilt and frozen, then the existing benchmark was replayed. This is a replay of the same reserved cohort, not another untouched benchmark; no benchmark-derived vocabulary or matching-policy edits were made.

| Family | Initial presence F1 | Corrected presence F1 | Difference | Initial count WAPE | Corrected count WAPE | Difference |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WordNet lexical | 0.9655 | 0.9655 | +0.0000 | 73.47% | 72.97% | -0.50 pp |
| WordNet Affect | 0.3251 | 0.3286 | +0.0035 | 91.70% | 92.28% | +0.57 pp |
| WordNet Domains | 0.8214 | 0.8217 | +0.0003 | 59.96% | 59.92% | -0.05 pp |

Coverage is unchanged. Correct source parsing can add both matching and nonmatching occurrences, so it does not guarantee a lower error against native output. [Initial full benchmark](docs/reports/gcam-expansion-6-initial-benchmark.json), [corrected full benchmark](docs/reports/gcam-expansion-6-benchmark.json) and [aggregate results](docs/reports/gcam-expansion-results.json) preserve the comparison.

## 0.18.0 Remaining field benchmarks

### Changes

- Benchmarked locations, dates, amounts, all names and quotations on the reserved seasonal cohorts.
- Added malformed-reference exclusions, value-only amount diagnostics and bootstrap intervals.

### Research

Locations, dates, amounts, all names and quotations were evaluated on the reserved seasonal cohorts from [version 0.7.0](#070-seasonal-evaluation-and-revised-extraction), using the large NER model and the reference gazetteer. These fields had not previously been benchmarked on those articles. No new articles were collected, and the results did not change rules, vocabularies or model selection.

Records are joined by both record ID and URL because translated archives can reuse an ID for unrelated URLs. Duplicate exclusions remain in force. Two malformed English location cells are excluded only from location scoring. The [audit](docs/reports/extraction-fields-benchmark-audit.json) records per-field exclusions, model/resource hashes and split checks.

Metrics compare per-document identity sets, ignoring offsets and repetition. Dates require matching calendar components and resolution. Amounts require numeric value and normalized object, with value-only matching reported separately. Quotations require complete content equality after Unicode, case, apostrophe and whitespace normalization; punctuation remains significant. Reporting verbs are checked separately. This measures agreement with GDELT's selected quotations, not correctness of every quoted span.

#### English agreement

| Identity | Native-positive articles | Precision | Recall | F1 | 95% F1 interval |
| --- | ---: | ---: | ---: | ---: | ---: |
| Location feature identity | 2,063 | 0.7219 | 0.6176 | 0.6657 | 0.6510–0.6796 |
| Calendar date | 983 | 0.3041 | 0.8201 | 0.4437 | 0.4220–0.4642 |
| Broad surface name | 2,502 | 0.1615 | 0.5075 | 0.2450 | 0.2365–0.2536 |
| Numeric value and object | 2,004 | 0.1433 | 0.3564 | 0.2044 | 0.1872–0.2199 |
| Numeric value alone | 2,004 | 0.2858 | 0.7229 | 0.4096 | 0.3769–0.4372 |
| Quotation content | 605 | 0.0440 | 0.5263 | 0.0811 | 0.0716–0.0912 |
| Quotation content and verb | 605 | 0.0260 | 0.3126 | 0.0480 | 0.0411–0.0557 |

Intervals use document-bootstrap resampling. They describe sampling uncertainty within the retrieved corpus, excluding source clustering and uncertainty about native bodies. Empty-document agreement is retained in reports but is not a headline score.

Locations agree best. Dates recover many references but overproduce calendar expressions. All names and amount objects remain weak; better value-only amount agreement shows that object attachment contributes to the mismatch. Quotations include far more spans than GDELT selects, giving low precision despite finding many native contents.

The following diagnostic restricts bodies to within 10% of native word count. Higher agreement is consistent with input differences contributing to errors, but similar length does not establish identical text.

| Identity | All English F1 | Similar-length F1 | Difference |
| --- | ---: | ---: | ---: |
| Location feature identity | 0.6657 | 0.7169 | +0.0513 |
| Calendar date | 0.4437 | 0.5026 | +0.0588 |
| Broad surface name | 0.2450 | 0.2837 | +0.0387 |
| Numeric value and object | 0.2044 | 0.2432 | +0.0387 |
| Quotation content | 0.0811 | 0.0926 | +0.0115 |

The [English report](docs/reports/extraction-fields-benchmark.json) includes month and novel-source results.

#### Translated agreement

Saved M2M100 English bodies are reused without retranslating. The articles differ from the English cohort, and GDELT's English translations remain unavailable, so these differences do not isolate translation quality.

| Identity | English F1 | Translated F1 | Native-positive translated articles | Difference |
| --- | ---: | ---: | ---: | ---: |
| Location feature identity | 0.6657 | 0.5459 | 251 | -11.98 pp |
| Calendar date | 0.4437 | 0.0121 | 8 | -43.16 pp |
| Broad surface name | 0.2450 | 0.0180 | 305 | -22.70 pp |
| Numeric value and object | 0.2044 | 0.0298 | 173 | -17.46 pp |
| Numeric value alone | 0.4096 | 0.1921 | 173 | -21.75 pp |
| Quotation content | 0.0811 | — | 0 | — |
| Quotation content and verb | 0.0480 | — | 0 | — |

Native dates are sparse in this cohort, making that score uncertain. No native quotation references occur, so positive quotation recall cannot be estimated; zero-reference set scores do not establish successful quotation replication. The [translated report](docs/reports/extraction-fields-benchmark-translated.json) retains precision, recall, intervals and exclusions.

The field benchmark now includes quotations, value-only amount diagnostics, per-field malformed-reference exclusions and optional bootstrap intervals. See [commands](scripts/README.md#field-benchmark). Offset accuracy and human-reviewed extraction quality remain unmeasured.

## 0.19.0 Locally built resources

### Changes

- Removed external vocabularies, reference geography and the GCAM codebook from package bundles.
- Added source-based local rebuild recipes while retaining custom-resource overrides.

### Research

External vocabularies, the geographic snapshot and the GCAM codebook now build locally from separately obtained sources. The package retains authored rules, schemas, source hashes and replay instructions. CrisisLex phrases are restored from their source using hash-based rule IDs, and source-dependent tone exclusions are stored as hashes. Custom dictionaries and authored count/name rules remain usable independently of the supplied recipes. See [Installation and setup](docs/installation.md).

All rebuilt profiles have identical parsed contents to their predecessors. Replay on the same saved bodies checks whether moving resources out of the package changes extraction.

| Reserved sample | Articles | Changed output cells | Changed full GCAM outputs |
| --- | ---: | ---: | ---: |
| English | 2,626 | 0 | 0 |
| Saved translated English | 317 | 0 | 0 |

The comparison covers all columns, with identical empty media/extra inputs, frozen large-model entities and saved translations. Identical predictions against the same references preserve the previous metrics. This is a packaging migration check, not a new independent accuracy benchmark, and no rules were fitted on these samples. The [parity report](docs/reports/resource-migration.json) records the check.

## 1.0.0 Public release

### Changes

- Prepared `gdelt-regkg` for public release.

### Research

The release keeps the evaluated extraction choices and resource profiles. There is no additional fitting or new accuracy benchmark in this release. English and translated agreement is reported in [version 0.7.0](#070-seasonal-evaluation-and-revised-extraction); remaining-field results are in [version 0.18.0](#0180-remaining-field-benchmarks); GCAM coverage is in [version 0.16.0](#0160-gcam-theme-counts). Metadata formatting follows supplied inputs, while text-derived fields remain approximations to native extraction. Offset agreement and human-reviewed NLP accuracy are still unmeasured.

## Reproducing the benchmarks

The inventory measurements above describe research samples and frequency priorities. Theme/count resources can be rebuilt from their maintained mappings without fitting against article bodies:

```shell
gdelt-regkg-build-resources --fields themes counts --output built-resources
```

Defaults are themes v3, counts v3, tone v3 and name rules v1. The builder validates input rules and emits versioned dictionaries and schemas. See the [resource guide](src/gdelt_regkg/resources/README.md) and [field documentation](docs/README.md) for configuration and extraction behavior.

Install the package's `benchmark` extra and the medium English model, then prepare local resources using [Installation and setup](docs/installation.md#best-supported-setup). Historical comparisons must explicitly select their earlier profiles; defaults now use later revisions. The following collection selects tone v1:

```powershell
$dates = '20260922', '20260924', '20260926', '20260928', '20261002', '20261003'
$batches = foreach ($day in $dates) { foreach ($hour in '03', '12', '21') { "$($day)$($hour)0000" } }
gdelt-regkg-benchmark-tone --batches $batches --output benchmark-results --per-day 400 --per-source 2 --seed 42 --workers 8 --timeout 25 --lexicon local-resources/tone.v1.json
```

`--per-day` overrides `--sample-size`. Add `--offline` to replay cached HTML; fresh live fetches can produce different bodies. With the General Inquirer source TSV at `downloads/resources/inqtabs.txt`, run:

```shell
gdelt-regkg-refine-tone --results benchmark-results/results.jsonl --train-dates 20260922 20260924 20260926 20260928 --validation-date 20261002 --test-date 20261003 --gi-source downloads/resources/inqtabs.txt --output tone-revision --check-language
```

Outputs include the candidate lexicon, split audit, training token edits, validation comparisons, held-out metrics, and per-article test comparisons. Changing candidates after inspecting the final test requires a new test date. See [maintained benchmark tools](scripts/README.md#tone-benchmark-against-original-articles).

The historical independent comparison used tone v2, counts v2, themes v3, and canonical NER without name rules. To collect its dates with current defaults:

```powershell
$dates = '20260910', '20260912', '20260914'
$batches = foreach ($day in $dates) { foreach ($hour in '03', '12', '21') { "$($day)$($hour)0000" } }
gdelt-regkg-benchmark-extraction --batches $batches --output independent-results --per-day 400 --per-source 2 --seed 42 --workers 16 --timeout 20 --ner-model en_core_web_md
```

For the baseline, use the saved corpus and archives with `--offline`, `--ner-name-policy surface`, `--count-rules local-resources/counts.v1.json`, and `--theme-lexicon local-resources/themes.v2.json`. Raw collection includes duplicate bodies; the reported 775-article analysis excludes known URLs and normalized-token exact/SimHash near duplicates against earlier bodies and within the new sample. Fresh page downloads can change body text and retrieval success.

## Further work

- Counts — improve quantity recall and object attachment on new count-positive development articles.
- Organizations — improve recall while retaining the precision gain.
- Themes — add frequent unsupported labels and improve existing matches.
- Translation — compare engines on fresh multilingual development articles.
- Names amounts and quotations — improve precision, objects and quotation selection.
- GCAM — improve Affect matching and occurrence counts.
- Evaluation — reserve a new benchmark before tuning; obtain matching native bodies before scoring offsets.
