# Dictionaries

## Dictionary overview

Global Content Analysis Measures (GCAM) brings together dictionaries that describe the emotional, psychological and topical language in news articles. Each dictionary associates words or phrases with categories, such as positive sentiment, fear or moral values, or with numeric ratings, such as happiness. Matching an article against these vocabularies produces category counts and scores in its [Global Knowledge Graph (GKG)](../get-started/concepts-and-glossary.md#gkg) record.

The dictionaries offer different perspectives, for example, VADER measures sentiment; Moral Foundations describes moral language; Loughran–McDonald focuses on financial language. Choose dictionaries suited to your topic and the article's language. However their vocabularies, research methods and licenses differ. The entries below explain what each dictionary measures and provide source links and acquisition instructions. Citations are also provided, as GDELT recommends citing the sources when using the dictionary. For some dictionaries there are multiple BibTeX entries and also additional ones, for convenience. First block is the main ones, second block — additional.

In the table, **GCAM ID** identifies the dictionary in GDELT, and **Selector** is its name in this library. **Supported** counts categories covered by source-backed vocabulary. **Native** gives the category count in the GCAM codebook. Authored approximations are listed separately. **Availability** shows whether a dictionary is included in the resource build profile (`v5`), needs an optional import, or still requires its original vocabulary.

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

## Coverage and configuration

The `v5` preset compiles 2,597 dimensions: 2,328 source-backed dimensions, 268 authored theme approximations and one French imagery approximation. Its language inventory is 2,296 English and 301 non-English dimensions. LIWC 2007 adds 62 source-backed dimensions and MPQA adds 14. Together with v5, they compile 2,673 dimensions: 2,404 source-backed and 269 approximations. See [Build GCAM resources](../guides/gcam-resources.md#complete-expanded-example). Count/value keys for one category count as one dimension. These coverage counts describe the available vocabulary and categories. They do not establish extraction accuracy.

Use a dictionary's selector or numeric ID with `disabled_dictionaries`, `gcam_disabled_dictionaries` or `--gcam-disable` to exclude it. Implemented selectors can also be used with `--gcam-add` when building a profile. Optional imports require separate source files. Non-English dictionaries need the original-language body and its language label alongside prepared English text. Chinese scoring also needs optional Jieba segmentation from `gdelt-regkg[build]`. See [GCAM](fields/gcam.md) for scoring and language handling, and [Build GCAM resources](../guides/gcam-resources.md#choose-a-preset) for profile setup.

## Dictionary licenses

Terms below describe the named editions and selected distributions. A free download or citation request does not itself grant redistribution rights. Where a source states no reuse license, confirm the applicable permissions with its rights holder. See [Third-party terms](#third-party-terms) for attribution and redistribution requirements.

| ID | Dictionary | License / published terms |
| ---: | --- | --- |
| 1 | [Forest Values](#dictionary-1) | Free download; modification permitted |
| 2 | [General Inquirer](#dictionary-2) | Academic research |
| 3 | [Lexicoder sentiment](#dictionary-3) | Agreement |
| 4 | [Lexicoder topics](#dictionary-4) | Citation requested; no reuse license stated |
| 5 | [LIWC](#dictionary-5) | Proprietary |
| 6 | [Loughran–McDonald](#dictionary-6) | Academic research |
| 7 | [Opinion Observer](#dictionary-7) | CC BY 4.0 (selected NLTK distribution) |
| 8 | [English RID](#dictionary-8) | Download available; reuse terms not stated |
| 9 | [Roget](#dictionary-9) | Public-domain text; conversion terms separate |
| 10 | [SentiWordNet](#dictionary-10) | CC BY-SA 4.0 |
| 11 | [SentiWords](#dictionary-11) | CC BY-SA 3.0 |
| 12 | [MPQA Subjectivity](#dictionary-12) | GNU GPL; version not identified in archive |
| 13 | [Body Boundary](#dictionary-13) | Free download; citation required |
| 14 | [WordNet Affect 1.0](#dictionary-14) | CC BY 3.0 |
| 15 | [WordNet Affect 1.1](#dictionary-15) | CC BY 3.0 |
| 16 | [WordNet Domains](#dictionary-16) | CC BY 3.0 |
| 17 | [WordNet lexical categories](#dictionary-17) | Princeton WordNet |
| 18 | [GKG themes](#dictionary-18) | MIT |
| 19 | [ANEW](#dictionary-19) | Research distribution; reuse terms not stated |
| 20 | [English ML-SENTICON](#dictionary-20) | MIT (selected repository) |
| 21 | [English Hedonometer](#dictionary-21) | CC BY-NC-SA 4.0 |
| 22 | [Spanish ANEW](#dictionary-22) | Noncommercial research |
| 23 | [Non-English ML-SENTICON](#dictionary-23) | MIT (selected repository) |
| 24 | [Non-English Hedonometer](#dictionary-24) | CC BY-NC-SA 4.0 |
| 25 | [Moral Foundations](#dictionary-25) | Download available; no reuse license stated |
| 26 | [VADER](#dictionary-26) | MIT |
| 27 | [Portuguese emotion/pro-social](#dictionary-27) | Citation provided; reuse terms not stated |
| 28 | [French RID](#dictionary-28) | Download available; reuse terms not stated |
| 29 | [Russian RID](#dictionary-29) | Source and permission required |
| 30 | [Hungarian RID](#dictionary-30) | Download available; reuse terms not stated |
| 31 | [Swedish RID](#dictionary-31) | Download available; reuse terms not stated |
| 32 | [Portuguese RID](#dictionary-32) | Download available; reuse terms not stated |
| 33 | [German RID](#dictionary-33) | Download available; reuse terms not stated |
| 35 | [Hogenraad Motive](#dictionary-35) | Citation provided; reuse terms not stated |
| 36 | [French Hogenraad Motive](#dictionary-36) | Citation provided; reuse terms not stated |
| 37 | [Spanish Hogenraad Motive](#dictionary-37) | Citation provided; reuse terms not stated |
| 38 | [French imagery](#dictionary-38) | CC BY 4.0 (paper) |
| 39 | [Hogenraad TIME](#dictionary-39) | Citation provided; reuse terms not stated |
| 40 | [Temperament/Elements](#dictionary-40) | Citation provided; reuse terms not stated |
| 41 | [Central-bank sentiment](#dictionary-41) | Board public-domain policy, with exceptions |
| 42 | [eMFD](#dictionary-42) | Data license not stated in source repository |

## Dictionaries

<a id="dictionary-1"></a>
### Forest Values

Classifies forest-related language into economic, ecological, aesthetic and moral/spiritual values.

**License:** The [publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/forest-value-dictionary/) offers a free download and explicitly permits modification for other subjects. It does not publish a redistribution license for the WordStat conversion. Cite Bengston and Xu and confirm redistribution terms with the distributor.

Download `FOREST.zip` from the [WordStat publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/forest-value-dictionary/). Supply the ZIP or CAT file.

```bibtex
@techreport{bengston1995forest,
  author = {Bengston, David N. and Xu, Zhi},
  title = {Changing National Forest Values: A Content Analysis},
  institution = {USDA Forest Service, North Central Forest Experiment Station},
  type = {Research Paper},
  number = {NC-323},
  address = {St. Paul, MN},
  year = {1995}
}
```

<a id="dictionary-2"></a>
### General Inquirer

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

```bibtex
@book{stone1966inquirer,
  author = {Stone, Philip J. and Dunphy, Dexter C. and Smith, Marshall S. and Ogilvie, Daniel M.},
  title = {The General Inquirer: A Computer Approach to Content Analysis},
  publisher = {MIT Press},
  address = {Cambridge, MA},
  year = {1966}
}
```

<a id="dictionary-3"></a>
### Lexicoder Sentiment Dictionary

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
  number = {2},
  pages = {205--231},
  doi = {10.1080/10584609.2012.671234}
}
```

> [!NOTE]
> Original citation references `lexicoder.com`, however website is now unavailable (domain expired).

```bibtex
@misc{daku2015lexicoder,
  author = {Daku, Mark and Soroka, Stuart and Young, Lori},
  title = {Lexicoder, Version 3.0},
  year = {2015},
  howpublished = {Computer software, McGill University, Montreal},
  url = {https://www.snsoroka.com/data-lexicoder/}
}
```

<a id="dictionary-4"></a>
### Lexicoder Topic Dictionaries

Identifies policy and public-affairs topics.

**License:** The [publisher](https://www.snsoroka.com/data-lexicoder/) supplies the draft topic dictionaries and requests a citation, but states no reuse license for them. Its academic-use statement and user agreement concern the separate sentiment dictionary. Confirm topic-dictionary permissions with the authors.

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

> [!NOTE]
> Original citation references `lexicoder.com`, however website is now unavailable (domain expired).

```bibtex
@inproceedings{albaugh2013automated,
  author = {Albaugh, Quinn and Sevenans, Julie and Soroka, Stuart and Loewen, Peter John},
  title = {The Automated Coding of Policy Agendas: A Dictionary-Based Approach},
  booktitle = {6th Annual Comparative Agendas Project Conference},
  address = {Antwerp, Belgium},
  year = {2013}
}
```

<a id="dictionary-5"></a>
### Linguistic Inquiry and Word Count (LIWC)

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

> [!NOTE]
> Original citation references `www.liwc.net`, website is moved to `www.liwc.app`.

```bibtex
@techreport{pennebaker2007manual,
  author = {Pennebaker, James W. and Chung, Cindy K. and Ireland, Molly and Gonzales, Amy and Booth, Roger J.},
  title = {The Development and Psychometric Properties of {LIWC2007}},
  institution = {LIWC.net},
  address = {Austin, TX},
  year = {2007}
}
@article{tausczik2010psychological,
  author = {Tausczik, Yla R. and Pennebaker, James W.},
  title = {The Psychological Meaning of Words: {LIWC} and Computerized Text Analysis Methods},
  journal = {Journal of Language and Social Psychology},
  year = {2010},
  volume = {29},
  number = {1},
  pages = {24--54},
  doi = {10.1177/0261927X09351676}
}
```

<a id="dictionary-6"></a>
### Loughran–McDonald Financial Sentiment Dictionaries

Financial-context positive/negative tone, uncertainty, litigation and modal language.

**License:** Academic research. A commercial license is required for commercial use. [Publisher terms](https://sraf.nd.edu/loughranmcdonald-master-dictionary/).

Download the master CSV from the [authors' Notre Dame page](https://sraf.nd.edu/loughranmcdonald-master-dictionary/). The build recipe selects the 1993–2025 edition. Entries marked as removed are excluded.

```bibtex
@article{loughran2011liability,
  author = {Loughran, Tim and McDonald, Bill},
  title = {When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks},
  journal = {The Journal of Finance},
  year = {2011},
  volume = {66},
  number = {1},
  pages = {35--65},
  doi = {10.1111/j.1540-6261.2010.01625.x}
}
```

<a id="dictionary-7"></a>
### Opinion Observer

Positive and negative opinion words from the Hu–Liu resource.

**License:** CC BY 4.0 for the NLTK distribution used by the build. Both its archive README and [NLTK package metadata](https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/opinion_lexicon.xml) identify this license and Bing Liu as the author. Retain attribution, link to the [license](https://creativecommons.org/licenses/by/4.0/) and identify modifications. The citation instructions in the word-list headers also apply.

Obtain the [Hu–Liu opinion lexicon](https://www.cs.uic.edu/~liub/FBS/sentiment-analysis.html) or its [NLTK ZIP](https://raw.githubusercontent.com/nltk/nltk_data/gh-pages/packages/corpora/opinion_lexicon.zip). Keep `positive-words.txt`, `negative-words.txt` and their notices. Follow the downloaded edition's citation instructions.

```bibtex
@inproceedings{hu2004mining,
  author = {Hu, Minqing and Liu, Bing},
  title = {Mining and summarizing customer reviews},
  booktitle = {Proceedings of the tenth ACM SIGKDD international conference on Knowledge discovery and data mining (KDD '04)},
  pages = {168--177},
  year = {2004},
  publisher = {ACM},
  doi = {10.1145/1014052.1014073}
}
```

```bibtex
@inproceedings{liu2005opinion,
  author = {Liu, Bing and Hu, Minqing and Cheng, Junsheng},
  title = {Opinion observer: analyzing and comparing opinions on the Web},
  booktitle = {Proceedings of the 14th international conference on World Wide Web (WWW '05)},
  pages = {342--351},
  year = {2005},
  publisher = {ACM},
  doi = {10.1145/1060745.1060797}
}
```

<a id="dictionary-8"></a>
### Regressive Imagery Dictionary

Categories distinguish primary/primordial cognition, secondary/conceptual cognition and emotions.

**License:** The [publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/) provides downloads and citations without an explicit reuse license. [Yoshikoder](https://www.yoshikoder.org/), which converts the WordStat editions, directs dictionary-permission questions to their authors and distinguishes them from its software license. Confirm redistribution permissions for the selected edition.

Download English `RID.ZIP` from the [WordStat page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Keep CAT and EXC files together. Exclusions affect matching.

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
### Roget's Thesaurus, 1911 Edition

Broad semantic categories group words and phrases by concept.

**License:** The historical 1911 text is public domain. The [WordStat conversion description](https://www.kovcomp.co.uk/wordstat/Roget.html) and selected archive do not provide a separate redistribution license for the categorization file. Do not treat the text's status as a license for every later conversion.

Download [Roget.zip](https://provalisresearch.com/Download/Roget.zip). The importer also requires WordNet 3.1. Cite the historical text and its [WordStat conversion](https://www.kovcomp.co.uk/wordstat/Roget.html) separately.

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
### SentiWordNet 3.0

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

```bibtex
@inproceedings{esuli2006sentiwordnet,
  author = {Esuli, Andrea and Sebastiani, Fabrizio},
  title = {{SentiWordNet}: A Publicly Available Lexical Resource for Opinion Mining},
  booktitle = {Proceedings of the 5th International Conference on Language Resources and Evaluation (LREC 2006)},
  year = {2006},
  pages = {417--422}
}
```

<a id="dictionary-11"></a>
### SentiWords

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

```bibtex
@article{gatti2016sentiwords,
  author = {Gatti, Lorenzo and Guerini, Marco and Turchi, Marco},
  title = {{SentiWords}: Deriving a High Precision and High Coverage Lexicon for Sentiment Analysis},
  journal = {IEEE Transactions on Affective Computing},
  year = {2016},
  volume = {7},
  number = {4},
  pages = {409--421},
  doi = {10.1109/TAFFC.2015.2476456}
}
```

<a id="dictionary-12"></a>
### MPQA Subjectivity Lexicon

Strong/weak subjectivity clues are grouped by positive, negative, neutral and mixed prior polarity.

**License:** GNU GPL; confirm the applicable version with the [MPQA publisher](https://mpqa.cs.pitt.edu/lexicons/subj_lexicon/). The selected mirror archive includes the authors' README but no GPL text or version identifier. Preserve the source notices and obtain the applicable license text before redistribution.

Obtain the 2005 TFF clues file from [MPQA](https://mpqa.cs.pitt.edu/lexicons/subj_lexicon/) or the [MPQA mirror ZIP](https://tjzhifei.github.io/resources/mpqasubj.zip). TFF, ZIP, TGZ and extracted directories are supported. The profile's source metadata records normalizations and omitted records.

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

```bibtex
@article{wilson2009recognizing,
  author = {Wilson, Theresa and Wiebe, Janyce and Hoffmann, Paul},
  title = {Recognizing Contextual Polarity: An Exploration of Features for Phrase-Level Sentiment Analysis},
  journal = {Computational Linguistics},
  year = {2009},
  volume = {35},
  number = {3},
  pages = {399--433}
}
```

<a id="dictionary-13"></a>
### Body Boundary Dictionary

Vocabulary associated with psychological body-boundary concepts, including barrier and penetration imagery.

**License:** The [publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/body-type-dictionary/) offers a free download and requires citation of Wilson (2006) in publications using it. No explicit redistribution license is stated for the conversion. Confirm those permissions with the author or distributor.

Download `BodyType.zip` from the [WordStat publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/body-type-dictionary/), retaining CAT and EXC files. Its `SPECIAL ANIMALS (1)` heading contains 40 source patterns and is imported as `c13.6`. The category weight is distinct from vocabulary weights. The build preserves wildcards and source exclusions.

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
### WordNet Affect 1.0

Eleven broad affect labels applied to WordNet concepts.

**License:** CC BY 3.0. Underlying WordNet notices also apply. [FBK terms](https://wndomains.fbk.eu/download.html).

Obtain the [FBK annotations](https://wndomains.fbk.eu/download.html), or the [recorded mirror](https://github.com/larsmans/wordnet-domains-sentiwords), and WordNet 1.6. The input is `wn-affect-labels-1.0.txt`.

```bibtex
@inproceedings{strapparava2004affect,
  author = {Strapparava, Carlo and Valitutti, Alessandro},
  title = {{WordNet-Affect}: An Affective Extension of {WordNet}},
  booktitle = {Proceedings of the 4th International Conference on Language Resources and Evaluation (LREC 2004)},
  year = {2004},
  pages = {1083--1086},
  url = {https://wndomains.fbk.eu/download.html}
}
```

<a id="dictionary-15"></a>
### WordNet Affect 1.1

A more detailed hierarchy of affective WordNet labels.

**License:** CC BY 3.0. Underlying WordNet notices also apply. [FBK terms](https://wndomains.fbk.eu/download.html).

Obtain the [FBK annotations](https://wndomains.fbk.eu/download.html) and WordNet 1.6, selecting the 1.1 annotations. Cite `strapparava2004affect` from [Affect 1.0](#dictionary-14).

<a id="dictionary-16"></a>
### WordNet Domains 3.2

Subject-field labels such as medicine or economics assigned to WordNet concepts.

**License:** CC BY 3.0. Underlying WordNet notices also apply. [FBK terms](https://wndomains.fbk.eu/download.html).

Obtain [WordNet Domains 3.2](https://wndomains.fbk.eu/download.html) and WordNet 2.0. The publisher provides a form-based download. The build recipe also supports an annotations mirror.

```bibtex
@inproceedings{magnini2000domains,
  author = {Magnini, Bernardo and Cavaglia, Gabriela},
  title = {Integrating Subject Field Codes into {WordNet}},
  booktitle = {Proceedings of the 2nd International Conference on Language Resources and Evaluation (LREC 2000)},
  year = {2000},
  pages = {1413--1418},
  url = {https://wndomains.fbk.eu/download.html}
}
```

```bibtex
@inproceedings{bentivogli2004revising,
  author = {Bentivogli, Luisa and Forner, Pamela and Magnini, Bernardo and Pianta, Emanuele},
  title = {Revising the {WordNet} Domains Hierarchy: Semantics, Coverage and Balancing},
  booktitle = {Proceedings of the COLING Workshop on Multilingual Linguistic Resources},
  year = {2004},
  pages = {94--101}
}
```

<a id="dictionary-17"></a>
### WordNet 3.1 Lexical Categories

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

```bibtex
@book{fellbaum1998wordnet,
  editor = {Fellbaum, Christiane},
  title = {{WordNet}: An Electronic Lexical Database},
  publisher = {MIT Press},
  address = {Cambridge, MA},
  year = {1998}
}
@misc{princeton2010wordnet,
  author = {{Princeton University}},
  title = {About {WordNet}},
  year = {2010},
  howpublished = {Princeton University},
  url = {https://wordnet.princeton.edu}
}
```

<a id="dictionary-18"></a>
### GDELT GKG Themes

Topic and taxonomy categories corresponding to GKG themes.

**License:** MIT. Applies to local rules and CrisisLex. GDELT metadata retains its source terms. [Project license](https://github.com/octo-gone/gdelt-regkg/blob/master/LICENSE), [CrisisLex](https://github.com/sajao/CrisisLex), [GDELT](https://www.gdeltproject.org/data.html).

Build from the package's theme rules, [CrisisLex](https://github.com/sajao/CrisisLex) and the GCAM codebook. The codebook supplies category IDs. Public category lists do not supply GDELT's production matching rules.

The v5 preset includes authored rules for another 268 dimensions, giving 367 compiled theme dimensions out of 368. Existing matches and document context guards are retained. Source metadata and coverage reports mark the added dimensions as authored approximations. They have not established equivalent native scores. The `themes-authored` build component is included automatically in v5. Disabling dictionary `themes` disables both the existing and authored rules.

```bibtex
@misc{leetaru2013gkg,
  author = {Leetaru, Kalev Hannes},
  title = {The {GDELT} Global Knowledge Graph ({GKG})},
  year = {2013},
  url = {https://www.gdeltproject.org/}
}
```

```bibtex
@inproceedings{leetaru2013gdelt,
  author = {Leetaru, Kalev and Schrodt, Philip A.},
  title = {{GDELT}: Global Data on Events, Location, and Tone, 1979--2012},
  booktitle = {ISA Annual Convention},
  year = {2013}
}
@inproceedings{olteanu2014crisislex,
  author = {Olteanu, Alexandra and Castillo, Carlos and Diaz, Fernando and Vieweg, Sarah},
  title = {{CrisisLex}: A Lexicon for Collecting and Filtering Microblogged Communications in Crises},
  booktitle = {Proceedings of ICWSM 2014},
  year = {2014},
  pages = {376--385}
}
@inproceedings{olteanu2015expect,
  author = {Olteanu, Alexandra and Vieweg, Sarah and Castillo, Carlos},
  title = {What to Expect When the Unexpected Happens: Social Media Communications Across Crises},
  booktitle = {Proceedings of CSCW 2015},
  year = {2015},
  pages = {994--1009}
}
```

<a id="dictionary-19"></a>
### Affective Norms for English Words (ANEW)

Mean valence, arousal and dominance ratings for all participants, men and women.

**License:** The [authors' report](https://pdodds.w3.uvm.edu/teaching/courses/2009-08UVM-300/docs/others/everything/bradley1999a.pdf) describes research distribution through CSEA but states no reuse or redistribution license. Confirm the terms for the original ratings with CSEA or the rights holder. The report does not establish a specific noncommercial license.

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

```bibtex
@techreport{bradley2010anew,
  author = {Bradley, Margaret M. and Lang, Peter J.},
  title = {Affective Norms for English Words ({ANEW}): Instruction Manual and Affective Ratings},
  institution = {The Center for Research in Psychophysiology, University of Florida},
  type = {Technical Report},
  number = {C-2},
  address = {Gainesville, FL},
  year = {2010}
}
```

<a id="dictionary-20"></a>
### ML-SENTICON (English)

Eight layers of positive and negative lemma polarity estimates.

**License:** MIT in the [selected ITALIC-US repository](https://github.com/ITALIC-US/ML-Senticon/blob/main/LICENSE). Retain its copyright and license notice, and the README's citation to Cruz et al. (2014). This identifies the selected distribution rather than establishing terms for every copy of ML-SENTICON.

The v5 build downloads [senticon.en.xml](https://raw.githubusercontent.com/ITALIC-US/ML-Senticon/refs/heads/main/senticon.en.xml) and retain the [repository README and license](https://github.com/ITALIC-US/ML-Senticon). Preserve all eight layers and signed polarity scores. Layers are cumulative: later layers inherit distinct records from earlier layers. XML and explicit sixteen-score-column CSV inputs are supported.

```bibtex
@article{cruz2014building,
  author = {Cruz, Ferm{\'i}n L. and Troyano, Jos{\'e} A. and Pontes, Beatriz and Ortega, F. Javier},
  title = {Building layered, multilingual sentiment lexicons at synset and lemma levels},
  journal = {Expert Systems with Applications},
  volume = {41},
  number = {13},
  pages = {5984--5994},
  year = {2014},
  doi = {10.1016/j.eswa.2014.04.005},
  publisher = {Elsevier}
}
```

```bibtex
@article{cruz2014mlsenti
  author = {Cruz, Ferm{\'i}n L. and Troyano, Jos{\'e} A. and Pontes, Beatriz and Ortega, F. Javier},
  title = {{ML-SentiCon}: un lexic{\'o}n multiling{\"u}e de polaridades sem{\'a}nticas a nivel de lemas},
  journal = {Procesamiento del Lenguaje Natural},
  number = {53},
  pages = {113--120},
  year = {2014},
  url = {https://unirioja.es},
  publisher = {Sociedad Espa{\~n}ola para el Procesamiento del Lenguaje Natural}
}
```

<a id="dictionary-21"></a>
### Hedonometer (English)

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
  doi = {10.48550/arXiv.1406.3855}
}
```

<a id="dictionary-22"></a>
### Spanish Adaptation of ANEW

Spanish affective word ratings. This is a language-specific adaptation with its own dimensions.

**License:** Noncommercial research and education with attribution. The [original supplementary ZIP](https://media.springernature.com/original/springer-static/esm/art%3A10.3758%2FBF03193031/MediaObjects/Redondo-BRM-2007.zip) contains `ReadMe_Terms_of_Use.txt`. Cite both the paper and downloaded archive materials.

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
### ML-SENTICON (Non-English)

Layered sentiment lexicons for Catalan, Galician and Spanish.

**License:** MIT in the [selected ITALIC-US repository](https://github.com/ITALIC-US/ML-Senticon/blob/main/LICENSE), as for the [English distribution](#dictionary-20). Retain the repository notices and cite Cruz et al. (2014).

The [ML-Senticon repository](https://github.com/ITALIC-US/ML-Senticon) provides Catalan, Galician and Spanish XML files. Cite `cruz2014senticon` from the [English entry](#dictionary-20). The v5 build downloads and imports all three variants with cumulative layers. Native codebook keys are selected by language. Spanish and Galician keys follow the Catalan block within dictionary 23. Basque is outside the native GCAM inventory.

<a id="dictionary-24"></a>
### Hedonometer (Non-English)

Happiness ratings for the codebook's Arabic, German, French, Hindi, Indonesian, Korean, Portuguese, Russian, Spanish, Urdu and Chinese word lists.

**License:** CC BY-NC-SA 4.0. [API terms](https://www.hedonometer.org/api.html).

Obtain language-specific word lists from [Hedonometer](https://hedonometer.org/words/). Cite the selected release and the references in the [English entry](#dictionary-21). The v5 build acquires and compiles eleven complete labMT JSON lists. Chinese uses the standard Jieba dictionary with HMM disabled. It requires the `build` extra when analyzing Chinese text. This segmentation is not established as identical to GDELT’s preprocessing.

<a id="dictionary-25"></a>
### Moral Foundations Dictionary

Virtue/vice vocabulary for five moral foundations plus general moral language.

**License:** The [authors' materials page](https://moralfoundations.org/other-materials/) and selected `mft_original.dic` copy provide no explicit reuse license. Preserve Graham and Haidt's attribution and confirm permissions with the rights holder. This entry uses the original MFD, not MFD 2.0 or eMFD; terms for those resources do not establish the original dictionary's license.

Obtain the original dictionary from [Moral Foundations materials](https://moralfoundations.org/other-materials/). The [eMFD repository](https://github.com/medianeuroscience/emfd/tree/master/dictionaries) also hosts `mft_original.dic`. Preserve the original vocabulary attribution.

```bibtex
@misc{grahamhaidtMFD,
  author = {Graham, Jesse and Haidt, Jonathan},
  title = {Moral Foundations Dictionary},
  url = {https://moralfoundations.org/other-materials/},
}
```

```bibtex
@article{graham2009liberals,
  author = {Graham, Jesse and Haidt, Jonathan and Nosek, Brian A.},
  title = {Liberals and Conservatives Rely on Different Sets of Moral Foundations},
  journal = {Journal of Personality and Social Psychology},
  year = {2009},
  volume = {96},
  number = {5},
  pages = {1029--1046},
  doi = {10.1037/a0015141}
}
@article{haidt2007when,
  author = {Haidt, Jonathan and Graham, Jesse},
  title = {When Morality Opposes Justice: Conservatives Have Moral Intuitions That Liberals May Not Recognize},
  journal = {Social Justice Research},
  year = {2007},
  volume = {20},
  number = {1},
  pages = {98--116},
  doi = {10.1007/s11211-007-0034-z}
}
```

<a id="dictionary-26"></a>
### VADER Sentiment Lexicon

Valence ratings of sentiment-bearing words and tokens.

**License:** MIT. [Author repository](https://github.com/cjhutto/vaderSentiment).

Obtain the vocabulary from the [author repository](https://github.com/cjhutto/vaderSentiment) or the recorded wheel. GCAM uses lexical scores in bag-of-words mode rather than VADER's sentence-level compound algorithm.

```bibtex
@inproceedings{hutto2014vader,
  author = {Hutto, C. J. and Gilbert, Eric},
  title = {{VADER}: A Parsimonious Rule-Based Model for Sentiment Analysis of Social Media Text},
  booktitle = {Proceedings of the 8th International AAAI Conference on Weblogs and Social Media (ICWSM)},
  year = {2014},
  pages = {216--225},
  doi = {10.1609/icwsm.v8i1.14550}
}
```

<a id="dictionary-27"></a>
### Portuguese Emotion and Pro-Social Dimensions

Portuguese affective and pro-social vocabulary from Detry, Lopo and Hogenraad.

**License:** The [GDELT announcement](https://blog.gdeltproject.org/detry-lopo-hogenraad-portuguese-emotion-pro-social-available-in-gcam/) identifies the 1992 source and its authors but states no reuse or redistribution terms. Request the vocabulary and applicable permissions from its custodian.

Request the original Portuguese vocabulary and usage terms from its custodian, using the [GDELT resource citation](https://blog.gdeltproject.org/detry-lopo-hogenraad-portuguese-emotion-pro-social-available-in-gcam/) to identify the dictionary. Supply verified `word,Emotion,ProSocial` CSV with scores on the native 10–70 scales.

```bibtex
@techreport{detry1992portuguese,
  author = {Detry, B. and Lopo, T. and Hogenraad, Robert},
  title = {Valores afectivo e pro-social de 1040 palavras da lingua portuguesa: Para a construcao de indicadores do discurso educativo},
  institution = {Instituto de Inovacao Educacional},
  type = {Relatorio final},
  year = {1992},
}
```

<a id="dictionary-28"></a>
<a id="regressive-imagery-dictionary--french"></a>
### Regressive Imagery Dictionary — French

French translation of RID by Robert Hogenraad.

**License:** No reuse license is stated for this translation in the selected download. See [RID permissions](#dictionary-8) and confirm terms with its translators or distributor.

Obtain the French CAT/EXC distribution from the [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Preserve translator attribution and edition-specific terms. Cite the base RID work and the translation record below. The v5 build imports this edition for explicitly selected French text. Preserve source wildcard and exclusion behavior. No additional morphological expansion is inferred.

```bibtex
@misc{hogenraadRIDFrench,
  author = {Hogenraad, Robert},
  title = {Regressive Imagery Dictionary: French Translation},
  url = {https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/}
}
```

<a id="dictionary-29"></a>
<a id="regressive-imagery-dictionary--russian"></a>
### Regressive Imagery Dictionary — Russian

Russian translation attributed to Leonid Dorfman.

**License:** The [publisher](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/) lists the Russian translation as under development and supplies no download or reuse license for it. Request the source and permissions from the translator or custodian.

Request the Russian vocabulary and usage terms from the translator or custodian. The [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/) identifies Leonid Dorfman as translator. A manual native-category JSON import is supported. The original vocabulary is still required.

```bibtex
@misc{dorfmanRIDRussian,
  author = {Dorfman, Leonid},
  title = {Regressive Imagery Dictionary: Russian Translation},
}
```

<a id="dictionary-30"></a>
<a id="regressive-imagery-dictionary--hungarian"></a>
### Regressive Imagery Dictionary — Hungarian

Hungarian translation by Tibor Polya and Levente Szasz.

**License:** No reuse license is stated for this translation in the selected download. See [RID permissions](#dictionary-8) and confirm terms with its translators or distributor.

Obtain the Hungarian CAT/EXC distribution from the [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Preserve translator attribution and edition-specific terms. Cite the base RID work and the translation record below. The v5 build imports this edition for explicitly selected Hungarian text. Preserve source wildcard and exclusion behavior. No additional morphological expansion is inferred.

```bibtex
@misc{polyaRIDHungarian,
  author = {Polya, Tibor and Szasz, Levente},
  title = {Regressive Imagery Dictionary: Hungarian Translation},
  url = {https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/}
}
```

<a id="dictionary-31"></a>
<a id="regressive-imagery-dictionary--swedish"></a>
### Regressive Imagery Dictionary — Swedish

Swedish RID translation.

**License:** No reuse license is stated for this translation in the selected download. See [RID permissions](#dictionary-8) and confirm terms with its translators or distributor.

Obtain the Swedish CAT/EXC distribution from the [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Preserve translator attribution and edition-specific terms. Cite the base RID work and the translation record below. The v5 build imports this edition for explicitly selected Swedish text. Preserve source wildcard and exclusion behavior. No additional morphological expansion is inferred.

```bibtex
@misc{norlanderRIDSwedish,
  author = {Norlander, Torsten and Linnarud, Moira and Kjellen-Simes, Marika and Hogenraad, Robert},
  title = {Regressive Imagery Dictionary: Swedish Translation},
  url = {https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/}
}
```

<a id="dictionary-32"></a>
<a id="regressive-imagery-dictionary--portuguese"></a>
### Regressive Imagery Dictionary — Portuguese

Portuguese RID translation. The native codebook identifies partial vocabulary expansion.

**License:** No reuse license is stated for this translation in the selected download. See [RID permissions](#dictionary-8) and confirm terms with its translators or distributor.

Obtain the Portuguese CAT/EXC distribution from the [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Preserve translator attribution and edition-specific terms. Cite the base RID work and the translation record below. The v5 build imports this edition for explicitly selected Portuguese text. Preserve source wildcard and exclusion behavior. No additional morphological expansion is inferred.

```bibtex
@misc{cunhaRIDPortuguese,
  author = {Cardoso e Cunha, Tito and Detry, Brigitte and Hogenraad, Robert},
  title = {Regressive Imagery Dictionary: Portuguese Translation},
  url = {https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/}
}
```

<a id="dictionary-33"></a>
<a id="regressive-imagery-dictionary--german"></a>
### Regressive Imagery Dictionary — German

German RID translation. GDELT identifies nearly complete vocabulary expansion.

**License:** No reuse license is stated for this translation in the selected download. See [RID permissions](#dictionary-8) and confirm terms with its translators or distributor.

Obtain the German CAT/EXC distribution from the [WordStat RID page](https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/). Preserve translator attribution and edition-specific terms. Cite the base RID work and the translation record below. The v5 build imports this edition for explicitly selected German text. Preserve source wildcard and exclusion behavior. No additional morphological expansion is inferred.

```bibtex
@misc{delphendahlRIDGerman,
  author = {Delphendahl, Renate},
  title = {Regressive Imagery Dictionary: German Translation},
  url = {https://provalisresearch.com/products/content-analysis-software/wordstat-dictionary/regressive-imagery-dictionary/}
}
```

<a id="dictionary-35"></a>
### Hogenraad's Motive Dictionary

Achievement, affiliation and power motivation, with subordinate goal, action, evaluation and relationship categories.

**License:** The [GDELT announcement](https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/) provides edition-specific citations, not a reuse license. Obtain the English vocabulary and its usage and redistribution terms from the author or custodian.

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
<a id="hogenraads-motive-dictionary--french"></a>
### Hogenraad's Motive Dictionary — French

French version of the motivation categories.

**License:** The [GDELT announcement](https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/) cites the French edition without specifying reuse terms. Obtain permissions for this translation from its author or custodian.

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
<a id="hogenraads-motive-dictionary--spanish"></a>
### Hogenraad's Motive Dictionary — Spanish

Spanish version of the motivation categories.

**License:** The [GDELT announcement](https://blog.gdeltproject.org/hogenraads-motive-dictionary-available-in-gcam/) cites the Spanish edition without specifying reuse terms. Obtain permissions for this translation from its authors or custodian.

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
<a id="hogenraad--oriannes-french-imagery-dictionary"></a>
### Hogenraad & Orianne's French Imagery Dictionary

Imagery values for French nouns.

The optional [PDF converter](../guides/dictionary-imports.md#french-imagery-pdf-conversion) downloads this paper, renders its appendix and uses line-by-line Tesseract OCR to build class-midpoint estimates. It retrieves checksum-verified French recognition data separately, saves extraction diagnostics and marks the resulting scores as approximate and unreviewed. These estimates are included in v5 and recorded separately from source-backed coverage. Exact-data CSV imports are available.

**License:** CC BY 4.0 for the [published paper](https://psychologicabelgica.com/articles/10.5334/pb.672). Confirm the applicable terms of any separately obtained rating file.

Request the original machine-readable French noun ratings through the authors or custodian, using the [GDELT resource citation](https://blog.gdeltproject.org/hogenraad-oriannes-french-imagery-dictionary-available-in-gcam/). The published appendix groups nouns into rating intervals. It does not supply the exact word-level means needed to recover native scores. OCR of those intervals cannot recover the missing values. Supply a verified `word,ImageryValence` CSV on the native 10–70 scale. Class midpoints are not an equivalent replacement.

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
### Hogenraad's TIME Dictionary

Temporal language beyond explicit dates: duration, sequence, frequency, age, past, present and future.

**License:** The [GDELT announcement](https://blog.gdeltproject.org/hogenraads-time-dictionary-available-gcam/) credits Hogenraad and supplies a citation, but does not state reuse or redistribution terms. Request those terms with the original vocabulary.

Request the original English TIME term lists, category hierarchy and matching rules from the author or custodian. Supply CAT or category JSON. The [GDELT announcement](https://blog.gdeltproject.org/hogenraads-time-dictionary-available-gcam/) identifies the resource.

```bibtex
@misc{hogenraadTIME,
  author = {Hogenraad, Robert},
  title = {{TIME} Dictionary},
  url = {https://blog.gdeltproject.org/hogenraads-time-dictionary-available-gcam/}
}
```

<a id="dictionary-40"></a>
<a id="martindale--martindales-temperamentelements-dictionary"></a>
### Martindale & Martindale's Temperament/Elements Dictionary

Vocabulary connecting the four elements with sanguine, choleric, melancholic and phlegmatic imagery.

**License:** The [GDELT announcement](https://blog.gdeltproject.org/martindales-temperamentelements-available-in-gcam/) supplies the Martindale and Martindale citation without dictionary reuse terms. Obtain vocabulary permissions from the rights holder or custodian; the article citation is not a dictionary license.

Request the original English vocabulary for all eight native categories, with its matching rules and usage terms. CAT and category JSON inputs are supported. Use the [GDELT-recommended study](https://blog.gdeltproject.org/martindales-temperamentelements-available-in-gcam/) to identify the resource.

```bibtex
@article{martindale1988temperament,
  author = {Martindale, Audrey E. and Martindale, Colin},
  title = {Metaphorical Equivalence of Elements and Temperaments: Empirical Studies of Bachelard's Theory of Imagination},
  journal = {Journal of Personality and Social Psychology},
  year = {1988},
  volume = {55},
  number = {5},
  pages = {836--848}
}
```

<a id="dictionary-41"></a>
### Central Bank Financial Stability Report Sentiment

Positive, negative and neutral financial-stability vocabulary.

**License:** The Federal Reserve Board's [copyright policy](https://www.federalreserve.gov/disclaimer.htm) places website information in the public domain unless otherwise indicated and requests attribution to the Board. The selected XLSX appendix contains no separate copyright or license notice. Cite the Board and the dictionary authors. Any specifically identified third-party material has its own permissions.

Download the [XLSX dictionary appendix](https://www.federalreserve.gov/econres/ifdp/files/ifdp1203-appendix.xlsx) from the Federal Reserve. The importer reads literal spreadsheet values and rejects formulas. Use native ID 41 from the codebook's `Variable` column.

```bibtex
@techreport{correa2017stability,
  author = {Correa, Ricardo and Garud, Keshav and Londono, Juan M. and Mislang, Nathan},
  title = {Sentiment in Central Banks' Financial Stability Reports},
  institution = {Board of Governors of the Federal Reserve System},
  type = {International Finance Discussion Papers},
  number = {1203},
  year = {2017},
  doi = {10.17016/IFDP.2017.1203}
}
```

```bibtex
@article{correa2021sentiment,
  author = {Correa, Ricardo and Garud, Keshav and Londono, Juan M. and Mislang, Nathan},
  title = {Sentiment in Central Banks' Financial Stability Reports},
  journal = {Review of Finance},
  year = {2021},
  volume = {25},
  number = {1},
  pages = {85--120},
  doi = {10.1093/rof/rfaa014}
}
```

<a id="dictionary-42"></a>
### Extended Moral Foundations Dictionary (eMFD)

Moral-word coverage and probabilistic foundation/sentiment scores derived from crowd annotations.

**License:** The [source dictionary repository](https://github.com/medianeuroscience/emfd) supplies `emfd_scoring.csv` without an explicit data-license statement. The separate [eMFDscore software repository](https://github.com/medianeuroscience/emfdscore) contains a GPL-3.0 license and commercial-licensing instructions for that package. This library imports the CSV directly, not eMFDscore. Confirm permissions for the dictionary data with its authors rather than assigning the software's terms to the CSV.

Obtain `emfd_scoring.csv` from the [authors' repository](https://github.com/medianeuroscience/emfd). The importer emits one moral-word count and ten value-only dimensions.

```bibtex
@article{hopp2020emfd,
  author = {Hopp, Frederic R. and Fisher, Jacob T. and Cornell, Devin and Huskey, Richard and Weber, Rene},
  title = {The Extended Moral Foundations Dictionary ({eMFD}): Development and Applications of a Crowd-Sourced Approach to Extracting Moral Intuitions from Text},
  journal = {Behavior Research Methods},
  year = {2021},
  volume = {53},
  pages = {232--246},
  doi = {10.3758/s13428-020-01433-0}
}
```

## Resource source files

The build downloads these files automatically with `--download-sources`. For manual downloads, use the exact filenames below.

| Filename | Obtain from | Purpose |
| --- | --- | --- |
| `inqtabs.txt` | [General Inquirer basic TSV](https://inquirer.sites.fas.harvard.edu/inqtabs.txt) | Tone and General Inquirer GCAM categories |
| `CrisisLexRec.txt` | [CrisisLexRec](https://raw.githubusercontent.com/sajao/CrisisLex/master/data/CrisisLexLexicon/CrisisLexRec.txt) | Crisis-related theme phrases |
| `vader_lexicon.txt` | `vaderSentiment/vader_lexicon.txt` inside the [vaderSentiment 3.3.2 wheel](https://pypi.org/project/vaderSentiment/3.3.2/#files) | VADER GCAM scores<br>setup extracts this member without installing the library |
| `GCAM-MASTER-CODEBOOK.TXT` | [GDELT master codebook](http://data.gdeltproject.org/documentation/GCAM-MASTER-CODEBOOK.TXT) | Native category IDs and coverage denominator |
| `wn3.1.dict.tar.gz` | [WordNet 3.1](https://wordnetcode.princeton.edu/wn3.1.dict.tar.gz) | Lexical categories and morphology |
| `wn2.0.tar.gz` | [WordNet 2.0](https://wordnetcode.princeton.edu/2.0/WordNet-2.0.tar.gz) | Domains synset mapping |
| `wn1.6.tar.gz` | [WordNet 1.6](https://wordnetcode.princeton.edu/1.6/wn16.unix.tar.gz) | Affect synset mapping |
| `wndomains-mirror.zip` | [Domains/Affect mirror](https://codeload.github.com/larsmans/wordnet-domains-sentiwords/zip/refs/heads/master), [publisher](https://wndomains.fbk.eu/download.html) | Domains 3.2 and Affect 1.1 annotations |
| Twenty reference `*.gkg.csv.zip` archives | Exact HTTP URLs in [recipes.json](https://github.com/octo-gone/gdelt-regkg/blob/master/src/gdelt_regkg/resources/recipes.json) | GKG place names, codes, coordinates and feature IDs<br>see [Build gazetteers](../guides/gazetteers.md#build-the-default-reference) |

## Third-party terms

> [!WARNING]
> MIT applies to this project's code and original rules. Downloaded dictionaries, models, article bodies and source-derived profiles retain their own terms. A combined build profile can contain resources with different restrictions. When distributing profiles, obtain permission where required and retain the notices and licenses applicable to each source.

The [license table](#dictionary-licenses) identifies the selected dictionaries and distributions. Per-dictionary entries provide source links, permission details and BibTeX citations. Preserve applicable notices with converted files; a paper citation alone does not replace a license notice or permission.

| Source | Terms and attribution |
| --- | --- |
| [Forest Values (1)](#dictionary-1) | Bengston and Xu. The publisher offers a free download and permits modification for other subjects. Confirm redistribution terms for the WordStat conversion. |
| [General Inquirer (2)](#dictionary-2) | Philip J. Stone and contributors. Academic research is permitted. Commercial use of categories, including modified categories, requires permission under the [Harvard terms](https://inquirer.sites.fas.harvard.edu/spreadsheet_guide.htm). |
| [Lexicoder sentiment (3)](#dictionary-3) | Lori Young and Stuart Soroka. Follow the [sentiment-dictionary agreement](https://www.snsoroka.com/s/LSDagreement.pdf), including its academic-use, transfer and adaptation restrictions. |
| [Lexicoder topics (4)](#dictionary-4) | Albaugh, Sevenans and Soroka. The publisher requests citation but states no topic-dictionary reuse license. Confirm permissions separately from the sentiment dictionary. |
| [LIWC (5)](#dictionary-5) | Proprietary dictionary. Use a licensed LIWC 2007 source under its purchase or access agreement. An importer does not authorize sharing its vocabulary or converted profiles. |
| [Loughran–McDonald (6)](#dictionary-6) | Free for academic research. Obtain a commercial license for commercial use through the [authors' publisher page](https://sraf.nd.edu/loughranmcdonald-master-dictionary/). |
| [Opinion Observer (7)](#dictionary-7) | Bing Liu. The selected NLTK archive declares [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Preserve attribution and notices, link to the license, identify modifications and follow the source citation instructions. |
| [English RID (8)](#dictionary-8), [French (28)](#dictionary-28), [Russian (29)](#dictionary-29), [Hungarian (30)](#dictionary-30), [Swedish (31)](#dictionary-31), [Portuguese (32)](#dictionary-32), [German (33)](#dictionary-33) | Credit Colin Martindale and the selected translation's authors. Downloads and citations do not establish a redistribution license. Confirm edition-specific permissions with the authors or distributor; see [Yoshikoder's dictionary notice](https://www.yoshikoder.org/). Russian source files must also be obtained separately. |
| [Roget (9)](#dictionary-9) | The historical text is public domain. Cite its edition and the WordStat conversion separately; confirm any applicable rights in the conversion file. |
| [SentiWordNet (10)](#dictionary-10) | CC BY-SA 4.0 in the selected source header. Preserve attribution, license information and modification notices, and follow ShareAlike requirements for shared adaptations. |
| [SentiWords (11)](#dictionary-11) | CC BY-SA 3.0 in the selected distribution. Preserve its source header and attribution and follow the license's ShareAlike requirements. |
| [MPQA Subjectivity (12)](#dictionary-12) | GNU GPL. Confirm the version applicable to the selected source and retain its notices and license when redistributing the lexicon or adaptations. The mirror README does not identify a GPL version. |
| [Body Boundary (13)](#dictionary-13) | Andrew Wilson. Free download with a required Wilson (2006) citation in publications. Confirm redistribution permissions for the conversion. |
| [WordNet Affect 1.0 (14)](#dictionary-14), [Affect 1.1 (15)](#dictionary-15), [Domains (16)](#dictionary-16) | Fondazione Bruno Kessler. CC BY 3.0 for the annotations. Retain attribution, license information and underlying WordNet notices. Follow the [publisher's citation instructions](https://wndomains.fbk.eu/download.html) for the resources used. |
| [Princeton WordNet (17)](#dictionary-17) | Princeton University. Retain the copyright, permission notice and disclaimer required by the [WordNet license](https://wordnet.princeton.edu/license-and-commercial-use). |
| [GKG themes (18)](#dictionary-18) and CrisisLexRec | Local authored rules and CrisisLexRec use MIT. Retain the project and [CrisisLex](https://github.com/sajao/CrisisLex) copyright and license notices. CrisisLexRec attribution includes Alexandra Olteanu and Carlos Castillo. GDELT codebook metadata is a separate source. |
| [ANEW (19)](#dictionary-19) | Bradley and Lang / CSEA. The selected report describes research distribution without specifying reuse or redistribution terms. Obtain applicable permissions for its ratings; a public report copy is not an express data license. |
| [ML-SENTICON English (20)](#dictionary-20) and [non-English (23)](#dictionary-23) | The selected ITALIC-US repository declares MIT. Preserve that repository's copyright and license notice and cite Cruz et al. (2014), as requested in its README. |
| [Hedonometer English (21)](#dictionary-21) and [non-English (24)](#dictionary-24) | CC BY-NC-SA 4.0 under the [API terms](https://hedonometer.org/api.html). Preserve attribution and license information, identify modifications, and follow NonCommercial and ShareAlike requirements. Cite the selected word lists and requested publications. |
| [Spanish ANEW (22)](#dictionary-22) | The publisher archive's `ReadMe_Terms_of_Use.txt` permits noncommercial research and educational use with citations to both the article and downloaded materials. Retain that notice; confirm permissions for other uses. |
| [Original Moral Foundations (25)](#dictionary-25) | Credit Graham and Haidt. The selected original dictionary has no explicit reuse license in its source materials. Confirm permissions for that edition; MFD 2.0 and eMFD are separate resources. |
| [VADER (26)](#dictionary-26) | C. J. Hutto and Eric Gilbert. MIT. Preserve copyright and license notices from the [source repository](https://github.com/cjhutto/vaderSentiment). |
| [Portuguese emotion/pro-social (27)](#dictionary-27) | Detry, Lopo and Hogenraad. The GDELT announcement supplies a citation but no reuse terms. Request the source and permissions from its custodian. |
| [Motive English (35)](#dictionary-35), [French (36)](#dictionary-36), [Spanish (37)](#dictionary-37), [TIME (39)](#dictionary-39) | Preserve Hogenraad and coauthors' edition-specific citations. GDELT's announcements do not publish reuse licenses. Obtain permissions for each vocabulary and translation from its rights holder or custodian. |
| [French imagery (38)](#dictionary-38) | The paper is CC BY 4.0. Attribute the paper and identify OCR and class-midpoint transformations when using its appendix. A separately obtained exact-rating file needs its own applicable terms. |
| [Temperament/Elements (40)](#dictionary-40) | Martindale and Martindale. The cited study and GDELT announcement supply no dictionary reuse terms. Obtain source files and permissions from the rights holder or custodian. |
| [Central-bank sentiment (41)](#dictionary-41) | Cite the Federal Reserve Board and Correa et al. The [Board policy](https://www.federalreserve.gov/disclaimer.htm) permits copying and distribution of website information unless otherwise indicated. Respect any identified non-Board material's separate rights. |
| [eMFD (42)](#dictionary-42) | Cite Hopp et al. and confirm permissions for `emfd_scoring.csv` with its authors. The source data repository provides no explicit data license; do not assign the separate eMFDscore software's terms to it. |
| GDELT archives and codebook | Preserve applicable GDELT attribution and source notices. The project's MIT license does not establish terms for downloaded archives or codebook metadata. [Data and documentation](https://www.gdeltproject.org/data.html). |

Profiles retain source hashes and mappings for reproducibility. An importer provides a technical conversion interface, not additional source rights. Creative Commons [Attribution](https://creativecommons.org/licenses/by/4.0/), [ShareAlike](https://creativecommons.org/licenses/by-sa/3.0/) and [NonCommercial-ShareAlike](https://creativecommons.org/licenses/by-nc-sa/4.0/) conditions apply to the material covered by each license. A profile containing an openly licensed resource can also contain resources with more restrictive or unstated terms.
