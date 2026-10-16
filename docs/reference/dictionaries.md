# GCAM dictionary reference

## Contents

- [Dictionary overview](#dictionary-overview)
- [Dictionary licenses](#dictionary-licenses)
- [Forest Values](#forest-values)
- [General Inquirer](#general-inquirer)
- [Lexicoder Sentiment Dictionary](#lexicoder-sentiment-dictionary)
- [Lexicoder Topic Dictionaries](#lexicoder-topic-dictionaries)
- [Linguistic Inquiry and Word Count (LIWC)](#linguistic-inquiry-and-word-count-liwc)
- [Loughran–McDonald Financial Sentiment Dictionaries](#loughranmcdonald-financial-sentiment-dictionaries)
- [Opinion Observer](#opinion-observer)
- [Regressive Imagery Dictionary](#regressive-imagery-dictionary)
- [Roget's Thesaurus, 1911 Edition](#rogets-thesaurus-1911-edition)
- [SentiWordNet 3.0](#sentiwordnet-30)
- [SentiWords](#sentiwords)
- [MPQA Subjectivity Lexicon](#mpqa-subjectivity-lexicon)
- [Body Boundary Dictionary](#body-boundary-dictionary)
- [WordNet Affect 1.0](#wordnet-affect-10)
- [WordNet Affect 1.1](#wordnet-affect-11)
- [WordNet Domains 3.2](#wordnet-domains-32)
- [WordNet 3.1 Lexical Categories](#wordnet-31-lexical-categories)
- [GDELT GKG Themes](#gdelt-gkg-themes)
- [Affective Norms for English Words (ANEW)](#affective-norms-for-english-words-anew)
- [ML-SENTICON (English)](#ml-senticon-english)
- [Hedonometer (English)](#hedonometer-english)
- [Spanish Adaptation of ANEW](#spanish-adaptation-of-anew)
- [ML-SENTICON (Non-English)](#ml-senticon-non-english)
- [Hedonometer (Non-English)](#hedonometer-non-english)
- [Moral Foundations Dictionary](#moral-foundations-dictionary)
- [VADER Sentiment Lexicon](#vader-sentiment-lexicon)
- [Portuguese Emotion and Pro-Social Dimensions](#portuguese-emotion-and-pro-social-dimensions)
- [Regressive Imagery Dictionary — French](#regressive-imagery-dictionary--french)
- [Regressive Imagery Dictionary — Russian](#regressive-imagery-dictionary--russian)
- [Regressive Imagery Dictionary — Hungarian](#regressive-imagery-dictionary--hungarian)
- [Regressive Imagery Dictionary — Swedish](#regressive-imagery-dictionary--swedish)
- [Regressive Imagery Dictionary — Portuguese](#regressive-imagery-dictionary--portuguese)
- [Regressive Imagery Dictionary — German](#regressive-imagery-dictionary--german)
- [Hogenraad's Motive Dictionary](#hogenraads-motive-dictionary)
- [Hogenraad's Motive Dictionary — French](#hogenraads-motive-dictionary--french)
- [Hogenraad's Motive Dictionary — Spanish](#hogenraads-motive-dictionary--spanish)
- [Hogenraad & Orianne's French Imagery Dictionary](#hogenraad--oriannes-french-imagery-dictionary)
- [Hogenraad's TIME Dictionary](#hogenraads-time-dictionary)
- [Martindale & Martindale's Temperament/Elements Dictionary](#martindale--martindales-temperamentelements-dictionary)
- [Central Bank Financial Stability Report Sentiment](#central-bank-financial-stability-report-sentiment)
- [Extended Moral Foundations Dictionary (eMFD)](#extended-moral-foundations-dictionary-emfd)
- [Resource source files](#resource-source-files)
- [Third-party terms](#third-party-terms)

## Dictionary overview

The **GCAM ID** is GDELT's numeric dictionary identifier: for example, `c26.1` and `v26.1` belong to dictionary 26. A **selector** is the corresponding name accepted by `disabled_dictionaries`, `gcam_disabled_dictionaries` and `--gcam-disable`; numeric IDs are also accepted. Implemented dictionary selectors can also be used with `--gcam-add` to build a profile.

**Supported** counts categories covered by source-backed vocabulary; **Native** is the category count in the GCAM codebook. Authored approximations are identified separately. Count/value keys for one category count as one dimension. The `v5` preset compiles 2,597 dimensions: 2,328 source-backed dimensions, 268 authored theme approximations and one French imagery approximation. Its language inventory is 2,296 English and 301 non-English dimensions. Optional imports require separate source files. “Source required” identifies an importer whose original dictionary vocabulary must be acquired. Native dictionaries require an original-language body and its language label alongside prepared English text. Chinese scoring uses optional Jieba segmentation; install `gdelt-regkg[build]`.

| Dictionary | GCAM ID | Selector | Supported | Native | Availability |
| --- | ---: | --- | ---: | ---: | --- |
| [Forest Values](#dictionary-1) | 1 | `forest-values` | 4 | 4 | v5 |
| [General Inquirer](#dictionary-2) | 2 | `general-inquirer` | 228 | 228 | v5 |
| [Lexicoder sentiment](#dictionary-3) | 3 | `lexicoder` | 4 | 4 | v5 |
| [Lexicoder topics](#dictionary-4) | 4 | `lexicoder-topics` | 28 | 28 | v5 |
| [LIWC](#dictionary-5) | 5 | `liwc` | 62 | 62 | Optional import |
| [Loughran–McDonald](#dictionary-6) | 6 | `loughran-mcdonald` | 6 | 6 | v5 |
| [Opinion Observer](#dictionary-7) | 7 | `opinion-observer` | 2 | 2 | v5 |
| [English RID](#dictionary-8) | 8 | `rid` | 43 | 43 | v5 |
| [Roget](#dictionary-9) | 9 | `roget` | 1,042 | 1,042 | v5 |
| [SentiWordNet](#dictionary-10) | 10 | `sentiwordnet` | 2 | 2 | v5 |
| [SentiWords](#dictionary-11) | 11 | `sentiwords` | 1 | 1 | v5 |
| [MPQA Subjectivity](#dictionary-12) | 12 | `subjectivity` | 14 | 14 | Optional import |
| [Body Boundary](#dictionary-13) | 13 | `body-boundary` | 14 | 14 | v5 |
| [WordNet Affect 1.0](#dictionary-14) | 14 | `wordnet-affect-v1` | 11 | 11 | v5 |
| [WordNet Affect 1.1](#dictionary-15) | 15 | `wordnet-affect` | 280 | 280 | v5 |
| [WordNet Domains](#dictionary-16) | 16 | `wordnet-domains` | 168 | 168 | v5 |
| [WordNet lexical categories](#dictionary-17) | 17 | `wordnet-lexical` | 44 | 44 | v5 |
| [GKG themes](#dictionary-18) | 18 | `themes` | 99 + 268 authored | 368 | v5 |
| [ANEW](#dictionary-19) | 19 | `anew` | 9 | 9 | v5 |
| [English ML-SENTICON](#dictionary-20) | 20 | `ml-senticon` | 16 | 16 | v5 |
| [English Hedonometer](#dictionary-21) | 21 | `hedonometer` | 1 | 1 | v5 |
| [Spanish ANEW](#dictionary-22) | 22 | `anew-spanish` | 12 | 12 | v5 |
| [Non-English ML-SENTICON](#dictionary-23) | 23 | `ml-senticon-multilingual` | 48 | 48 | v5 |
| [Non-English Hedonometer](#dictionary-24) | 24 | `hedonometer-multilingual` | 11 | 11 | v5 |
| [Moral Foundations](#dictionary-25) | 25 | `moral-foundations` | 11 | 11 | v5 |
| [VADER](#dictionary-26) | 26 | `vader` | 1 | 1 | v5 |
| [Portuguese emotion/pro-social](#dictionary-27) | 27 | `portuguese-emotion` | 0 | 2 | Source required |
| [French RID](#dictionary-28) | 28 | `rid-french` | 43 | 43 | v5 |
| [Russian RID](#dictionary-29) | 29 | `rid-russian` | 0 | 64 | Source required |
| [Hungarian RID](#dictionary-30) | 30 | `rid-hungarian` | 36 | 36 | v5 |
| [Swedish RID](#dictionary-31) | 31 | `rid-swedish` | 64 | 64 | v5 |
| [Portuguese RID](#dictionary-32) | 32 | `rid-portuguese` | 43 | 43 | v5 |
| [German RID](#dictionary-33) | 33 | `rid-german` | 43 | 43 | v5 |
| [Hogenraad Motive](#dictionary-35) | 35 | `hogenraad-motive` | 0 | 33 | Source required |
| [French Hogenraad Motive](#dictionary-36) | 36 | `hogenraad-motive-french` | 0 | 33 | Source required |
| [Spanish Hogenraad Motive](#dictionary-37) | 37 | `hogenraad-motive-spanish` | 0 | 33 | Source required |
| [French imagery](#dictionary-38) | 38 | `french-imagery` | 1 approximate | 1 | v5 |
| [Hogenraad TIME](#dictionary-39) | 39 | `time` | 0 | 41 | Source required |
| [Temperament/Elements](#dictionary-40) | 40 | `temperament` | 0 | 8 | Source required |
| [Central-bank sentiment](#dictionary-41) | 41 | `central-bank` | 3 | 3 | v5 |
| [eMFD](#dictionary-42) | 42 | `emfd` | 11 | 11 | v5 |

## Dictionary licenses

See each dictionary's license notes for conditions. “Free distribution” describes source availability; “Unverified” means that an applicable reuse license is not established.

| ID | Dictionary | License |
| ---: | --- | --- |
| 1 | [Forest Values](#dictionary-1) | Free distribution |
| 2 | [General Inquirer](#dictionary-2) | Academic research |
| 3 | [Lexicoder sentiment](#dictionary-3) | Agreement |
| 4 | [Lexicoder topics](#dictionary-4) | Unverified |
| 5 | [LIWC](#dictionary-5) | Proprietary |
| 6 | [Loughran–McDonald](#dictionary-6) | Academic research |
| 7 | [Opinion Observer](#dictionary-7) | Unverified |
| 8 | [English RID](#dictionary-8) | Free distribution |
| 9 | [Roget](#dictionary-9) | Public domain |
| 10 | [SentiWordNet](#dictionary-10) | CC BY-SA 4.0 |
| 11 | [SentiWords](#dictionary-11) | CC BY-SA 3.0 |
| 12 | [MPQA Subjectivity](#dictionary-12) | GPL-3.0 |
| 13 | [Body Boundary](#dictionary-13) | Free distribution |
| 14 | [WordNet Affect 1.0](#dictionary-14) | CC BY 3.0 |
| 15 | [WordNet Affect 1.1](#dictionary-15) | CC BY 3.0 |
| 16 | [WordNet Domains](#dictionary-16) | CC BY 3.0 |
| 17 | [WordNet lexical categories](#dictionary-17) | Princeton WordNet |
| 18 | [GKG themes](#dictionary-18) | MIT |
| 19 | [ANEW](#dictionary-19) | Unverified |
| 20 | [English ML-SENTICON](#dictionary-20) | MIT |
| 21 | [English Hedonometer](#dictionary-21) | CC BY-NC-SA 4.0 |
| 22 | [Spanish ANEW](#dictionary-22) | Noncommercial research |
| 23 | [Non-English ML-SENTICON](#dictionary-23) | MIT |
| 24 | [Non-English Hedonometer](#dictionary-24) | CC BY-NC-SA 4.0 |
| 25 | [Moral Foundations](#dictionary-25) | Unverified |
| 26 | [VADER](#dictionary-26) | MIT |
| 27 | [Portuguese emotion/pro-social](#dictionary-27) | Unverified |
| 28 | [French RID](#dictionary-28) | Unverified |
| 29 | [Russian RID](#dictionary-29) | Unverified |
| 30 | [Hungarian RID](#dictionary-30) | Unverified |
| 31 | [Swedish RID](#dictionary-31) | Unverified |
| 32 | [Portuguese RID](#dictionary-32) | Unverified |
| 33 | [German RID](#dictionary-33) | Unverified |
| 35 | [Hogenraad Motive](#dictionary-35) | Unverified |
| 36 | [French Hogenraad Motive](#dictionary-36) | Unverified |
| 37 | [Spanish Hogenraad Motive](#dictionary-37) | Unverified |
| 38 | [French imagery](#dictionary-38) | CC BY 4.0 (paper) |
| 39 | [Hogenraad TIME](#dictionary-39) | Unverified |
| 40 | [Temperament/Elements](#dictionary-40) | Unverified |
| 41 | [Central-bank sentiment](#dictionary-41) | Unverified |
| 42 | [eMFD](#dictionary-42) | Unverified |

<a id="dictionary-1"></a>
## Forest Values

Classifies forest-related language into economic, ecological, aesthetic and moral/spiritual values.

**License:** Free distribution. Redistribution rights for the conversion are unverified. [Publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/forest-value-dictionary/).

Download `FOREST.zip` from the [WordStat publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/forest-value-dictionary/). Supply the ZIP or CAT file.

```bibtex
@techreport{bengston1995forest,
  author = {Bengston, David N. and Xu, Zhi},
  title = {Changing National Forest Values: A Content Analysis},
  year = {1995},
  institution = {US Department of Agriculture, Forest Service, North Central Forest Experiment Station},
  url = {https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/forest-value-dictionary/}
}
```

<a id="dictionary-2"></a>
## General Inquirer

Harvard IV-4 and Lasswell vocabulary measures psychological, social and evaluative categories.

**License:** Academic research. Commercial use requires permission. [Harvard terms](https://inquirer.sites.fas.harvard.edu/spreadsheet_guide.htm).

Download Harvard's [basic TSV](https://inquirer.sites.fas.harvard.edu/inqtabs.txt). Add the [dictionary text](https://inquirer.sites.fas.harvard.edu/inqdict.txt) with `general-inquirer-legacy` to include all 228 categories.

```bibtex
@article{stone1962inquirer,
  author = {Stone, Philip J. and Bales, Robert F. and Namenwirth, Zvi and Ogilvie, Daniel M.},
  title = {The General Inquirer: A Computer System for Content Analysis and Retrieval Based on the Sentence as a Unit of Information},
  journal = {Behavioral Science},
  year = {1962},
  volume = {7},
  number = {4},
  pages = {484--498}
}
```

<a id="dictionary-3"></a>
## Lexicoder Sentiment Dictionary

Positive, negative and negated polarity categories developed for political/news texts.

**License:** Agreement. Follow the agreement's use, transfer and adaptation restrictions. [Agreement](https://www.snsoroka.com/s/LSDagreement.pdf).

Download `LSDaug2015.zip` from the [publisher](https://www.snsoroka.com/data-lexicoder/). Keep both LC3 files. ZIP, extracted directory and four-category JSON inputs are supported.

```bibtex
@article{young2012affective,
  author = {Young, Lori and Soroka, Stuart},
  title = {Affective News: The Automated Coding of Sentiment in Political Texts},
  journal = {Political Communication},
  year = {2012},
  volume = {29},
  pages = {205--231}
}
```

<a id="dictionary-4"></a>
## Lexicoder Topic Dictionaries

Identifies policy and public-affairs topics.

**License:** Unverified. [Publisher](https://www.snsoroka.com/data-lexicoder/).

Obtain the June 2013 `LTDjun2013.zip` distribution from the [publisher](https://www.snsoroka.com/data-lexicoder/). The English input is `policy_agendas_english.lcd`.

```bibtex
@misc{albaugh2013topics,
  author = {Albaugh, Quinn and Sevenans, Julie and Soroka, Stuart},
  title = {Lexicoder Topic Dictionaries, June 2013 Versions},
  year = {2013},
  howpublished = {McGill University, Montreal, Canada},
  url = {https://www.snsoroka.com/data-lexicoder/}
}
```

<a id="dictionary-5"></a>
## Linguistic Inquiry and Word Count (LIWC)

Psycholinguistic categories cover function words, emotions, cognition, social relations and other language dimensions.

**License:** Proprietary. Obtain a licensed dictionary from the publisher. [Publisher](https://www.liwc.app/dictionaries).

Obtain a compatible English LIWC 2007 `.dic` through [licensed publisher access](https://www.liwc.app/dictionaries). Later editions use different categories. The importer maps source category names to the 62 native categories.

```bibtex
@misc{pennebaker2007liwc,
  author = {Pennebaker, James W. and Booth, Roger J. and Francis, Martha E.},
  title = {Linguistic Inquiry and Word Count: {LIWC}},
  year = {2007},
  howpublished = {Computer software, Austin, Texas},
  url = {https://www.liwc.app/}
}
```

<a id="dictionary-6"></a>
## Loughran–McDonald Financial Sentiment Dictionaries

Financial-context positive/negative tone, uncertainty, litigation and modal language.

**License:** Academic research. A commercial license is required for commercial use. [Publisher terms](https://sraf.nd.edu/loughranmcdonald-master-dictionary/).

Download the master CSV from the [authors' Notre Dame page](https://sraf.nd.edu/loughranmcdonald-master-dictionary/). The build recipe selects the 1993–2025 edition; entries marked as removed are excluded.

```bibtex
@article{loughran2011liability,
  author = {Loughran, Tim and McDonald, Bill},
  title = {When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks},
  journal = {The Journal of Finance},
  year = {2011},
  volume = {66},
  pages = {35--65}
}
```

<a id="dictionary-7"></a>
## Opinion Observer

Positive and negative opinion words from the Hu–Liu resource.

**License:** Unverified. [Publisher](https://www.cs.uic.edu/~liub/FBS/sentiment-analysis.html).

Obtain the [Hu–Liu opinion lexicon](https://www.cs.uic.edu/~liub/FBS/sentiment-analysis.html) or its [NLTK ZIP](https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/opinion_lexicon.zip). Keep `positive-words.txt`, `negative-words.txt` and their notices. Follow the downloaded edition's citation instructions as well as the GCAM reference below.

```bibtex
@inproceedings{liu2005opinion,
  author = {Liu, Bing and Hu, Minqing and Cheng, Junsheng},
  title = {Opinion Observer: Analyzing and Comparing Opinions on the Web},
  booktitle = {Proceedings of the 14th International World Wide Web Conference},
  year = {2005}
}
```

<a id="dictionary-8"></a>
## Regressive Imagery Dictionary

Categories distinguish primary/primordial cognition, secondary/conceptual cognition and emotions.

**License:** Free distribution. Redistribution rights for the conversion are unverified. [Publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/).

Download English `RID.ZIP` from the [WordStat page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Keep CAT and EXC files together; exclusions affect matching.

```bibtex
@incollection{martindale1987narrative,
  author = {Martindale, Colin},
  title = {Narrative Pattern Analysis: A Quantitative Method for Inferring the Symbolic Meaning of Narratives},
  booktitle = {Literary Discourse: Aspects of Cognitive and Social Psychological Approaches},
  editor = {Halasz, Laszlo},
  publisher = {De Gruyter},
  year = {1987},
  pages = {167--181}
}
```

<a id="dictionary-9"></a>
## Roget's Thesaurus, 1911 Edition

Broad semantic categories group words and phrases by concept.

**License:** Public domain, copyright expired. [Source information](https://www.kovcomp.co.uk/wordstat/Roget.html).

Download [Roget.zip](https://provalisresearch.com/Download/Roget.zip). The importer also requires WordNet 3.1. The historical text and its [WordStat conversion](https://www.kovcomp.co.uk/wordstat/Roget.html) have separate provenance.

```bibtex
@book{roget1911thesaurus,
  author = {Roget, Peter Mark},
  title = {Roget's Thesaurus of English Words and Phrases},
  year = {1911},
  publisher = {T. Y. Crowell Company},
  address = {New York}
}
```

<a id="dictionary-10"></a>
## SentiWordNet 3.0

Positive and negative scores are associated with WordNet senses.

**License:** CC BY-SA 4.0. [Author repository](https://github.com/aesuli/SentiWordNet).

Download `SentiWordNet_3.0.0.txt` from the [author repository](https://github.com/aesuli/SentiWordNet). The importer averages sense scores per normalized lemma.

```bibtex
@inproceedings{baccianella2010sentiwordnet,
  author = {Baccianella, Stefano and Esuli, Andrea and Sebastiani, Fabrizio},
  title = {{SentiWordNet} 3.0: An Enhanced Lexical Resource for Sentiment Analysis and Opinion Mining},
  booktitle = {Proceedings of LREC},
  year = {2010}
}
```

<a id="dictionary-11"></a>
## SentiWords

Word-level prior polarity derived from sense-level sentiment resources.

**License:** CC BY-SA 3.0. [Selected distribution](https://github.com/larsmans/wordnet-domains-sentiwords).

Obtain `SentiWords_1.0.txt` from the [annotations distribution](https://github.com/larsmans/wordnet-domains-sentiwords). Retain its CC BY-SA 3.0 source header.

```bibtex
@inproceedings{guerini2013prior,
  author = {Guerini, Marco and Gatti, Lorenzo and Turchi, Marco},
  title = {Sentiment Analysis: How to Derive Prior Polarities from {SentiWordNet}},
  booktitle = {Proceedings of EMNLP},
  year = {2013},
  pages = {1259--1269},
  url = {https://aclanthology.org/D13-1125/}
}
```

<a id="dictionary-12"></a>
## MPQA Subjectivity Lexicon

Strong/weak subjectivity clues are grouped by positive, negative, neutral and mixed prior polarity.

**License:** GPL-3.0. [GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.html).

Obtain the 2005 TFF clues file from [MPQA](https://mpqa.cs.pitt.edu/lexicons/subj_lexicon/) or the [MPQA mirror ZIP](https://tjzhifei.github.io/resources/mpqasubj.zip). TFF, ZIP, TGZ and extracted directories are supported. Source normalizations and omitted records are recorded in provenance.

Use `--download-mpqa` to add this optional dictionary and explicitly permit the checksum-verified mirror download at your discretion. `--download-sources` alone does not fetch it. See [LIWC and MPQA build instructions](../guides/dictionary-imports.md#optional-liwc-and-mpqa-imports).

```bibtex
@inproceedings{wilson2005polarity,
  author = {Wilson, Theresa and Wiebe, Janyce and Hoffmann, Paul},
  title = {Recognizing Contextual Polarity in Phrase-Level Sentiment Analysis},
  booktitle = {Proceedings of HLT-EMNLP},
  year = {2005},
  pages = {347--354},
  url = {https://aclanthology.org/H05-1044/}
}
```

<a id="dictionary-13"></a>
## Body Boundary Dictionary

Vocabulary associated with psychological body-boundary concepts, including barrier and penetration imagery.

**License:** Free distribution. Redistribution rights for the conversion are unverified. [Publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/body-type-dictionary/).

Download `BodyType.zip` from the [WordStat publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/body-type-dictionary/), retaining CAT and EXC files. Its `SPECIAL ANIMALS (1)` heading contains 40 source patterns and is imported as `c13.6`; the category weight is distinct from vocabulary weights. The build preserves wildcards and source exclusions.

```bibtex
@article{wilson2006boundary,
  author = {Wilson, Andrew},
  title = {Development and Application of a Content Analysis Dictionary for Body Boundary Research},
  journal = {Literary and Linguistic Computing},
  year = {2006},
  volume = {21},
  pages = {105--110}
}
```

<a id="dictionary-14"></a>
## WordNet Affect 1.0

Eleven broad affect labels applied to WordNet concepts.

**License:** CC BY 3.0. Underlying WordNet notices also apply. [FBK terms](https://wndomains.fbk.eu/download.html).

Obtain the [FBK annotations](https://wndomains.fbk.eu/download.html), or the [recorded mirror](https://github.com/larsmans/wordnet-domains-sentiwords), and WordNet 1.6. The input is `wn-affect-labels-1.0.txt`.

```bibtex
@inproceedings{strapparava2004affect,
  author = {Strapparava, Carlo and Valitutti, Alessandro},
  title = {{WordNet-Affect}: An Affective Extension of {WordNet}},
  booktitle = {Proceedings of LREC},
  year = {2004},
  pages = {1083--1086},
  url = {https://wndomains.fbk.eu/download.html}
}
```

<a id="dictionary-15"></a>
## WordNet Affect 1.1

A more detailed hierarchy of affective WordNet labels.

**License:** CC BY 3.0. Underlying WordNet notices also apply. [FBK terms](https://wndomains.fbk.eu/download.html).

Obtain the [FBK annotations](https://wndomains.fbk.eu/download.html) and WordNet 1.6, selecting the 1.1 annotations. Cite `strapparava2004affect` from [Affect 1.0](#dictionary-14).

<a id="dictionary-16"></a>
## WordNet Domains 3.2

Subject-field labels such as medicine or economics assigned to WordNet concepts.

**License:** CC BY 3.0. Underlying WordNet notices also apply. [FBK terms](https://wndomains.fbk.eu/download.html).

Obtain [WordNet Domains 3.2](https://wndomains.fbk.eu/download.html) and WordNet 2.0. The publisher provides a form-based download; the build recipe also supports an annotations mirror.

```bibtex
@inproceedings{magnini2000domains,
  author = {Magnini, Bernardo and Cavaglia, Gabriela},
  title = {Integrating Subject Field Codes into {WordNet}},
  booktitle = {Proceedings of LREC},
  year = {2000},
  pages = {1413--1418},
  url = {https://wndomains.fbk.eu/download.html}
}
```

<a id="dictionary-17"></a>
## WordNet 3.1 Lexical Categories

Broad lexical/semantic classes derived from WordNet's lexicographer categories.

**License:** Princeton WordNet. Retain the copyright, license and disclaimer. [Princeton terms](https://wordnet.princeton.edu/license-and-commercial-use).

Download [WordNet 3.1](https://wordnetcode.princeton.edu/wn3.1.dict.tar.gz) from Princeton. TAR archives and extracted dictionary directories are supported.

```bibtex
@article{miller1995wordnet,
  author = {Miller, George A.},
  title = {{WordNet}: A Lexical Database for English},
  journal = {Communications of the ACM},
  year = {1995},
  volume = {38},
  number = {11},
  pages = {39--41}
}
```

<a id="dictionary-18"></a>
## GDELT GKG Themes

Topic and taxonomy categories corresponding to GKG themes.

**License:** MIT. Applies to local rules and CrisisLex; GDELT metadata retains its source terms. [Project license](../../LICENSE), [CrisisLex](https://github.com/sajao/CrisisLex), [GDELT](https://www.gdeltproject.org/data.html).

Build from the package's theme rules, [CrisisLex](https://github.com/sajao/CrisisLex) and the GCAM codebook. The codebook supplies category IDs; public category lists do not supply GDELT's production matching rules.

The v5 preset includes authored rules for another 268 dimensions, giving 367 compiled theme dimensions out of 368. Existing matches and document context guards are retained. Source metadata and coverage reports mark the added dimensions as authored approximations. They have not established equivalent native scores. The `themes-authored` build component is included automatically in v5; disabling dictionary `themes` disables both the existing and authored rules.

```bibtex
@misc{leetaru2013gkg,
  author = {Leetaru, Kalev Hannes},
  title = {The {GDELT} Global Knowledge Graph ({GKG})},
  year = {2013},
  url = {https://www.gdeltproject.org/}
}
```

<a id="dictionary-19"></a>
## Affective Norms for English Words (ANEW)

Mean valence, arousal and dominance ratings for all participants, men and women.

**License:** Unverified. [Publisher](https://csea.phhp.ufl.edu/media/anewmessage.html), [report copy](https://pdodds.w3.uvm.edu/teaching/courses/2009-08UVM-300/docs/others/everything/bradley1999a.pdf).

The build downloads the [original technical report](https://pdodds.w3.uvm.edu/teaching/courses/2009-08UVM-300/docs/others/everything/bradley1999a.pdf) and converts its 1,034-word rating tables into nine all-, male- and female-participant mean scores. GCAM's “ANEW 2010” label refers to the reissued report and original ratings. See [report conversion](../guides/dictionary-imports.md#anew-report-conversion) for dependencies and the standalone script. A prepared [CSV](../guides/dictionary-imports.md#gcam-source-formats) can also be supplied. Extended ANEW datasets use different vocabularies and ratings. Public access to the report does not establish redistribution rights for its data.

```bibtex
@techreport{bradley1999anew,
  author = {Bradley, Margaret M. and Lang, Peter J.},
  title = {Affective Norms for English Words ({ANEW}): Stimuli, Instruction Manual and Affective Ratings},
  institution = {Center for Research in Psychophysiology, University of Florida},
  number = {C-1},
  year = {1999}
}
```

<a id="dictionary-20"></a>
## ML-SENTICON (English)

Eight layers of positive and negative lemma polarity estimates.

**License:** MIT. [Repository license](https://github.com/ITALIC-US/ML-Senticon/blob/main/LICENSE).

The v5 build downloads [senticon.en.xml](https://raw.githubusercontent.com/ITALIC-US/ML-Senticon/refs/heads/main/senticon.en.xml) and retain the [repository README and license](https://github.com/ITALIC-US/ML-Senticon). Preserve all eight layers and signed polarity scores. Layers are cumulative: later layers inherit distinct records from earlier layers. XML and explicit sixteen-score-column CSV inputs are supported.

```bibtex
@article{cruz2014senticon,
  author = {Cruz, Fermin L. and Troyano, Jose A. and Pontes, Beatriz and Ortega, F. Javier},
  title = {Building Layered, Multilingual Sentiment Lexicons at Synset and Lemma Levels},
  journal = {Expert Systems with Applications},
  year = {2014},
  url = {https://github.com/ITALIC-US/ML-Senticon}
}
```

<a id="dictionary-21"></a>
## Hedonometer (English)

Mean word happiness ratings from the English labMT vocabulary.

**License:** CC BY-NC-SA 4.0. [API terms](https://www.hedonometer.org/api.html).

Obtain the complete [labMT-en-v1 word list](https://hedonometer.org/words/labMT-en-v1/) through the API. Cite the codebook's English-resource paper and the additional reference requested by the [API](https://hedonometer.org/api.html), both provided below.

```bibtex
@article{dodds2011hedonometer,
  author = {Dodds, Peter S. and Harris, Kameron D. and Kloumann, Isabel M. and Bliss, Catherine A. and Danforth, Christopher M.},
  title = {Temporal Patterns of Happiness and Information in a Global Social Network: Hedonometrics and Twitter},
  journal = {PLoS ONE},
  year = {2011},
  volume = {6},
  number = {12},
  pages = {e26752},
  doi = {10.1371/journal.pone.0026752}
}
```

```bibtex
@misc{dodds2014a,
  author = {Dodds, P. S. and Clark, E. M. and Desu, S. and Frank, M. R. and Reagan, A. J. and Williams, J. R. and Mitchell, L. and Harris, K. D. and Kloumann, I. M. and Bagrow, J. P. and Megerdoomian, K. and McMahon, M. T. and Tivnan, B. F. and Danforth, C. M.},
  title = {Human Language Reveals a Universal Positivity Bias},
  year = {2014},
  url = {https://arxiv.org/abs/1406.3855}
}
```

<a id="dictionary-22"></a>
## Spanish Adaptation of ANEW

Spanish affective word ratings; this is a language-specific adaptation with its own dimensions.

**License:** Noncommercial research and education with attribution. The [original supplementary ZIP](https://media.springernature.com/original/springer-static/esm/art%3A10.3758%2FBF03193031/MediaObjects/Redondo-BRM-2007.zip) contains `ReadMe_Terms_of_Use.txt`; cite both the paper and downloaded archive materials.

The v5 build downloads the publisher's original supplementary ZIP and imports `Redondo(2007).txt`. Its 1,034 records provide nine all-, female- and male-participant affective means plus familiarity, concreteness and imageability. Unavailable ratings are omitted rather than filled with zero. Newer regional adaptations are different datasets.

```bibtex
@article{redondo2007anew,
  author = {Redondo, Jaime and Fraga, Isabel and Padron, Isabel and Comesana, Montserrat},
  title = {The Spanish Adaptation of {ANEW} (Affective Norms for English Words)},
  journal = {Behavior Research Methods},
  year = {2007},
  volume = {39},
  number = {3},
  pages = {600--605},
  doi = {10.3758/BF03193031}
}
```

<a id="dictionary-23"></a>
## ML-SENTICON (Non-English)

Layered sentiment lexicons for Catalan, Galician and Spanish.

**License:** MIT. [Repository license](https://github.com/ITALIC-US/ML-Senticon/blob/main/LICENSE).

The [ML-Senticon repository](https://github.com/ITALIC-US/ML-Senticon) provides Catalan, Galician and Spanish XML files. Cite `cruz2014senticon` from the [English entry](#dictionary-20). The v5 build downloads and imports all three variants with cumulative layers. Native codebook keys are selected by language; Spanish and Galician keys follow the Catalan block within dictionary 23. Basque is outside the native GCAM inventory.

<a id="dictionary-24"></a>
## Hedonometer (Non-English)

Happiness ratings for the codebook's Arabic, German, French, Hindi, Indonesian, Korean, Portuguese, Russian, Spanish, Urdu and Chinese word lists.

**License:** CC BY-NC-SA 4.0. [API terms](https://www.hedonometer.org/api.html).

Obtain language-specific word lists from [Hedonometer](https://hedonometer.org/words/). Cite the selected release and the references in the [English entry](#dictionary-21). The v5 build acquires and compiles eleven complete labMT JSON lists. Chinese uses the standard Jieba dictionary with HMM disabled; it requires the `build` extra when analyzing Chinese text. This segmentation is not established as identical to GDELT’s preprocessing.

<a id="dictionary-25"></a>
## Moral Foundations Dictionary

Virtue/vice vocabulary for five moral foundations plus general moral language.

**License:** Unverified. [Publisher](https://moralfoundations.org/other-materials/).

Obtain the original dictionary from [Moral Foundations materials](https://moralfoundations.org/other-materials/). The [eMFD repository](https://github.com/medianeuroscience/emfd/tree/master/dictionaries) also hosts `mft_original.dic`. Preserve the original vocabulary attribution.

```bibtex
@misc{grahamhaidtMFD,
  author = {Graham, Jesse and Haidt, Jonathan},
  title = {Moral Foundations Dictionary},
  url = {https://moralfoundations.org/other-materials/},
}
```

<a id="dictionary-26"></a>
## VADER Sentiment Lexicon

Valence ratings of sentiment-bearing words and tokens.

**License:** MIT. [Author repository](https://github.com/cjhutto/vaderSentiment).

Obtain the vocabulary from the [author repository](https://github.com/cjhutto/vaderSentiment) or the recorded wheel. GCAM uses lexical scores in bag-of-words mode rather than VADER's sentence-level compound algorithm.

```bibtex
@inproceedings{hutto2014vader,
  author = {Hutto, C. J. and Gilbert, Eric E.},
  title = {{VADER}: A Parsimonious Rule-Based Model for Sentiment Analysis of Social Media Text},
  booktitle = {Proceedings of ICWSM},
  year = {2014},
  url = {https://github.com/cjhutto/vaderSentiment}
}
```

<a id="dictionary-27"></a>
## Portuguese Emotion and Pro-Social Dimensions

Portuguese affective and pro-social vocabulary from Detry, Lopo and Hogenraad.

**License:** Unverified. [GDELT announcement](https://blog.gdeltproject.org/detry-lopo-hogenraad-portuguese-emotion-pro-social-available-in-gcam/).

Request the original Portuguese vocabulary and usage terms from its custodian, using the [GDELT resource citation](https://blog.gdeltproject.org/detry-lopo-hogenraad-portuguese-emotion-pro-social-available-in-gcam/) to identify the dictionary. Supply verified `word,Emotion,ProSocial` CSV with scores on the native 10–70 scales.

```bibtex
@techreport{detry1992portuguese,
  author = {Detry, B. and Lopo, T. and Hogenraad, Robert},
  title = {Valores afectivo e pro-social de 1040 palavras da lingua portuguesa: Para a construcao de indicadores do discurso educativo},
  institution = {Instituto de Inovacao Educacional},
  year = {1992},
}
```

<a id="dictionary-28"></a>
## Regressive Imagery Dictionary — French

French translation of RID by Robert Hogenraad.

**License:** Unverified. [Publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/).

Obtain the French CAT/EXC distribution from the [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Preserve translator attribution and edition-specific terms. Cite the base RID work and the translation record below. The v5 build imports this edition for explicitly selected French text. Preserve source wildcard and exclusion behavior; no additional morphological expansion is inferred.

```bibtex
@misc{hogenraadRIDFrench,
  author = {Hogenraad, Robert},
  title = {Regressive Imagery Dictionary: French Translation},
  url = {https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/}
}
```

<a id="dictionary-29"></a>
## Regressive Imagery Dictionary — Russian

Russian translation attributed to Leonid Dorfman.

**License:** Unverified. [Publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/).

Request the Russian vocabulary and usage terms from the translator or custodian. The [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/) identifies Leonid Dorfman as translator. A manual native-category JSON import is supported; the original vocabulary is still required.

```bibtex
@misc{dorfmanRIDRussian,
  author = {Dorfman, Leonid},
  title = {Regressive Imagery Dictionary: Russian Translation},
}
```

<a id="dictionary-30"></a>
## Regressive Imagery Dictionary — Hungarian

Hungarian translation by Tibor Polya and Levente Szasz.

**License:** Unverified. [Publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/).

Obtain the Hungarian CAT/EXC distribution from the [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Preserve translator attribution and edition-specific terms. Cite the base RID work and the translation record below. The v5 build imports this edition for explicitly selected Hungarian text. Preserve source wildcard and exclusion behavior; no additional morphological expansion is inferred.

```bibtex
@misc{polyaRIDHungarian,
  author = {Polya, Tibor and Szasz, Levente},
  title = {Regressive Imagery Dictionary: Hungarian Translation},
  url = {https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/}
}
```

<a id="dictionary-31"></a>
## Regressive Imagery Dictionary — Swedish

Swedish RID translation.

**License:** Unverified. [Publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/).

Obtain the Swedish CAT/EXC distribution from the [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Preserve translator attribution and edition-specific terms. Cite the base RID work and the translation record below. The v5 build imports this edition for explicitly selected Swedish text. Preserve source wildcard and exclusion behavior; no additional morphological expansion is inferred.

```bibtex
@misc{norlanderRIDSwedish,
  author = {Norlander, Torsten and Linnarud, Moira and Kjellen-Simes, Marika and Hogenraad, Robert},
  title = {Regressive Imagery Dictionary: Swedish Translation},
  url = {https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/}
}
```

<a id="dictionary-32"></a>
## Regressive Imagery Dictionary — Portuguese

Portuguese RID translation; the native codebook identifies partial vocabulary expansion.

**License:** Unverified. [Publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/).

Obtain the Portuguese CAT/EXC distribution from the [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Preserve translator attribution and edition-specific terms. Cite the base RID work and the translation record below. The v5 build imports this edition for explicitly selected Portuguese text. Preserve source wildcard and exclusion behavior; no additional morphological expansion is inferred.

```bibtex
@misc{cunhaRIDPortuguese,
  author = {Cardoso e Cunha, Tito and Detry, Brigitte and Hogenraad, Robert},
  title = {Regressive Imagery Dictionary: Portuguese Translation},
  url = {https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/}
}
```

<a id="dictionary-33"></a>
## Regressive Imagery Dictionary — German

German RID translation; GDELT identifies nearly complete vocabulary expansion.

**License:** Unverified. [Publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/).

Obtain the German CAT/EXC distribution from the [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Preserve translator attribution and edition-specific terms. Cite the base RID work and the translation record below. The v5 build imports this edition for explicitly selected German text. Preserve source wildcard and exclusion behavior; no additional morphological expansion is inferred.

```bibtex
@misc{delphendahlRIDGerman,
  author = {Delphendahl, Renate},
  title = {Regressive Imagery Dictionary: German Translation},
  url = {https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/}
}
```

<a id="dictionary-35"></a>
## Hogenraad's Motive Dictionary

Achievement, affiliation and power motivation, with subordinate goal, action, evaluation and relationship categories.

**License:** Unverified. [GDELT citation](https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/).

Request the original English version 7.0 vocabulary, category hierarchy and matching rules from the author or custodian. CAT and category JSON inputs are supported. The [GDELT announcement](https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/) provides the resource citation.

```bibtex
@misc{hogenraad2013motive,
  author = {Hogenraad, Robert},
  title = {Hogenraad's Motive Dictionary, Version 7.0},
  year = {2013},
  url = {https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/}
}
```

<a id="dictionary-36"></a>
## Hogenraad's Motive Dictionary — French

French version of the motivation categories.

**License:** Unverified. [GDELT citation](https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/).

Request French version 1.2 and its matching rules from the custodian identified through the [GDELT announcement](https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/). Supply native-category JSON for manual French builds.

```bibtex
@misc{hogenraad2008motiveFrench,
  author = {Hogenraad, Robert},
  title = {Hogenraad's Motive Dictionary, French Version 1.2},
  year = {2008},
  url = {https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/}
}
```

<a id="dictionary-37"></a>
## Hogenraad's Motive Dictionary — Spanish

Spanish version of the motivation categories.

**License:** Unverified. [GDELT citation](https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/).

Request Spanish version 1.1 and its matching rules through the original authors or custodian. The [GDELT announcement](https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/) identifies the edition. Supply native-category JSON for manual Spanish builds.

```bibtex
@misc{hogenraad2009motiveSpanish,
  author = {Hogenraad, Robert and Rey, Pablo and Urchaga, David and Rivas, Pedro},
  title = {Hogenraad's Motive Dictionary, Spanish Version 1.1},
  year = {2009},
  url = {https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/}
}
```

<a id="dictionary-38"></a>
## Hogenraad & Orianne's French Imagery Dictionary

Imagery values for French nouns.

The optional [PDF converter](../guides/dictionary-imports.md#french-imagery-pdf-conversion) downloads this paper, renders its appendix and uses line-by-line Tesseract OCR to build class-midpoint estimates. It retrieves checksum-verified French recognition data separately, saves extraction diagnostics and marks the resulting scores as approximate and unreviewed. These estimates are included in v5 and recorded separately from source-backed coverage; exact-data CSV imports remain available.

**License:** CC BY 4.0 for the [published paper](https://psychologicabelgica.com/articles/10.5334/pb.672). Confirm the applicable terms of any separately obtained rating file.

Request the original machine-readable French noun ratings through the authors or custodian, using the [GDELT resource citation](https://blog.gdeltproject.org/hogenraad-oriannes-french-imagery-dictionary-available-in-gcam/). The published appendix groups nouns into rating intervals; it does not supply the exact word-level means needed to recover native scores. OCR of those intervals cannot recover the missing values. Supply a verified `word,ImageryValence` CSV on the native 10–70 scale; class midpoints are not an equivalent replacement.

```bibtex
@article{hogenraad1981imagery,
  author = {Hogenraad, Robert and Orianne, Etienne},
  title = {Valences d'imagerie de 1.130 noms de la langue francaise parlee},
  journal = {Psychologica Belgica},
  year = {1981},
  volume = {21},
  number = {1},
  pages = {21--30},
}
```

<a id="dictionary-39"></a>
## Hogenraad's TIME Dictionary

Temporal language beyond explicit dates: duration, sequence, frequency, age, past, present and future.

**License:** Unverified. [GDELT citation](https://blog.gdeltproject.org/hogenraads-time-dictionary-available-gcam/).

Request the original English TIME term lists, category hierarchy and matching rules from the author or custodian. Supply CAT or category JSON. The [GDELT announcement](https://blog.gdeltproject.org/hogenraads-time-dictionary-available-gcam/) identifies the resource.

```bibtex
@misc{hogenraadTIME,
  author = {Hogenraad, Robert},
  title = {{TIME} Dictionary},
  url = {https://blog.gdeltproject.org/hogenraads-time-dictionary-available-gcam/}
}
```

<a id="dictionary-40"></a>
## Martindale & Martindale's Temperament/Elements Dictionary

Vocabulary connecting the four elements with sanguine, choleric, melancholic and phlegmatic imagery.

**License:** Unverified. [GDELT citation](https://blog.gdeltproject.org/martindales-temperamentelements-available-in-gcam/).

Request the original English vocabulary for all eight native categories, with its matching rules and usage terms. CAT and category JSON inputs are supported. Use the [GDELT-recommended study](https://blog.gdeltproject.org/martindales-temperamentelements-available-in-gcam/) to identify the resource.

```bibtex
@article{martindale1988temperament,
  author = {Martindale, A. E. and Martindale, Colin},
  title = {Metaphorical Equivalence of Elements and Temperaments: Empirical Studies of Bachelard's Theory of Imagination},
  journal = {Journal of Personality and Social Psychology},
  year = {1988},
  volume = {55},
  number = {5},
  pages = {836--848}
}
```

<a id="dictionary-41"></a>
## Central Bank Financial Stability Report Sentiment

Positive, negative and neutral financial-stability vocabulary.

**License:** Unverified. [Publisher](https://www.federalreserve.gov/econres/ifdp/sentiment-in-central-banks-financial-stability-reports.htm).

Download the [XLSX dictionary appendix](https://www.federalreserve.gov/econres/ifdp/files/ifdp1203-appendix.xlsx) from the Federal Reserve. The importer reads literal spreadsheet values and rejects formulas. Use native ID 41 from the codebook's `Variable` column.

```bibtex
@techreport{correa2017stability,
  author = {Correa, Ricardo and Garud, Keshav and Londono, Juan M. and Mislang, Nathan},
  title = {Sentiment in Central Banks' Financial Stability Reports},
  institution = {Board of Governors of the Federal Reserve System},
  type = {International Finance Discussion Papers},
  number = {1203},
  year = {2017},
  url = {https://www.federalreserve.gov/econres/ifdp/sentiment-in-central-banks-financial-stability-reports.htm}
}
```

<a id="dictionary-42"></a>
## Extended Moral Foundations Dictionary (eMFD)

Moral-word coverage and probabilistic foundation/sentiment scores derived from crowd annotations.

**License:** Unverified. [Author repository](https://github.com/medianeuroscience/emfd).

Obtain `emfd_scoring.csv` from the [authors' repository](https://github.com/medianeuroscience/emfd). The importer emits one moral-word count and ten value-only dimensions.

```bibtex
@article{hopp2020emfd,
  author = {Hopp, Frederic R. and Fisher, Jacob T. and Cornell, Devin and Huskey, Richard and Weber, Rene},
  title = {The Extended Moral Foundations Dictionary ({eMFD}): Development and Applications of a Crowd-Sourced Approach to Extracting Moral Intuitions from Text},
  journal = {Behavior Research Methods},
  year = {2020},
  doi = {10.3758/s13428-020-01433-0},
}
```


## Resource source files

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
| Twenty reference `*.gkg.csv.zip` archives | Exact HTTP URLs in [recipes.json](../../src/gdelt_regkg/resources/recipes.json) | GKG place names, codes, coordinates and feature IDs; see [Geographic reference files](../guides/resources.md#geographic-reference-files) |

## Third-party terms

> [!WARNING]
> MIT applies to this project's code and original rules. Downloaded dictionaries, models, article bodies and source-derived profiles retain their own terms. When distributing generated profiles, obtain permission where required and retain the upstream notices that apply to those files.

The [GCAM license table](#dictionary-licenses) summarizes terms for every native dictionary. The [dictionary reference](dictionaries.md) provides per-dictionary license notes, acquisition instructions and BibTeX citations.

| Source | Terms and attribution |
| --- | --- |
| General Inquirer | Philip J. Stone and contributors; Harvard IV-4 and Lasswell dictionaries. Academic research is permitted; commercial use, including modified categories, requires permission. [Publisher terms](https://inquirer.sites.fas.harvard.edu/spreadsheet_guide.htm) |
| CrisisLexRec | Alexandra Olteanu and Carlos Castillo; MIT. [Source and license](https://github.com/sajao/CrisisLex) |
| VADER | C. J. Hutto and Eric Gilbert; MIT. [Source and license](https://github.com/cjhutto/vaderSentiment) |
| Princeton WordNet | Princeton University; retain its license and attribution. [License](https://wordnet.princeton.edu/license-and-commercial-use) |
| WordNet Domains/Affect | Fondazione Bruno Kessler; CC BY 3.0. [Publisher terms](https://wndomains.fbk.eu/download.html) |
| Roget (1911) | Public-domain thesaurus. The build downloads the WordStat categorization file from [Provalis](https://provalisresearch.com/Download/Roget.zip); [Kovach](https://www.kovcomp.co.uk/wordstat/Roget.html) describes that conversion. |
| Lexicoder | Lori Young and Stuart Soroka / McGill University; noncommercial academic use with transfer/adaptation restrictions. A download does not establish permission for every conversion. [Agreement](https://www.snsoroka.com/s/LSDagreement.pdf) |
| GDELT | Archives and codebook retain source terms. [Data/documentation](https://www.gdeltproject.org/data.html) |

Profiles retain source hashes and mappings for reproducibility. An importer provides a technical conversion interface, not additional source rights.
