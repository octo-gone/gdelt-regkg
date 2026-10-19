# GKG field reference

The library supports all 27 [Global Knowledge Graph (GKG)](../../get-started/concepts-and-glossary.md#gkg) columns. Text-derived fields approximate GDELT processing. Metadata and media fields format caller-supplied values. Enhanced fields add zero-based character offsets into the exact analyzed English body.

Entity fields use named entity recognition (NER). [Global Content Analysis Measures (GCAM)](../../get-started/concepts-and-glossary.md#gcam-and-dimensions) combines dictionary counts and scores from original and translated texts.

Columns below follow the wire order declared by `GKG_COLUMNS`. Each page describes encoding, examples and limitations. See [Quickstart](../../get-started/quickstart.md) for standalone analyzers and [Generate records](../../guides/records.md) to combine fields.

| Position | GKG column | How it is produced | Setup |
| ---: | --- | --- | --- |
| 1 | [GKGRECORDID](record-id.md) | Batch timestamp and sequence<br>`T` marks translated records | Supplied `RecordMetadata` |
| 2 | [V2.1DATE](date.md) | Batch timestamp<br>publication time is kept separately in extra XML | Supplied metadata |
| 3 | [V2SOURCECOLLECTIONIDENTIFIER](source-collection.md) | Validated source collection identifier | Supplied metadata |
| 4 | [V2SOURCECOMMONNAME](source-name.md) | Supplied source name or hostname derived from the document URL | Supplied metadata |
| 5 | [V2DOCUMENTIDENTIFIER](document-identifier.md) | Supplied document URL or identifier | Supplied metadata |
| 6 | [V1COUNTS](counts.md) | Authored English number/event rules with optional resolved geography | Rules included<br>[NER and geography](../../get-started/installation-and-setup.md#basic-english-setup) for place enrichment |
| 7 | [V2.1COUNTS](enhanced-counts.md) | Count matches with character offsets | Same as counts |
| 8 | [V1THEMES](themes.md) | Phrase matching against theme dictionaries | [Build resources](../../guides/resources.md) |
| 9 | [V2ENHANCEDTHEMES](enhanced-themes.md) | Theme matches with offsets | Same as themes |
| 10 | [V1LOCATIONS](locations.md) | NER place mentions resolved against an offline gazetteer | [spaCy model and local resources](../../get-started/installation-and-setup.md#basic-english-setup) |
| 11 | [V2ENHANCEDLOCATIONS](enhanced-locations.md) | Resolved place occurrences with offsets and administrative details | Same as locations |
| 12 | [V1PERSONS](persons.md) | NER person mentions with name normalization and filtering | [NER extra and English model](../../get-started/installation-and-setup.md#english-models) |
| 13 | [V2ENHANCEDPERSONS](enhanced-persons.md) | Person mentions with offsets | Same as persons |
| 14 | [V1ORGANIZATIONS](organizations.md) | NER organization mentions with authored name filtering | [NER extra and English model](../../get-started/installation-and-setup.md#english-models) |
| 15 | [V2ENHANCEDORGANIZATIONS](enhanced-organizations.md) | Organization mentions with offsets | Same as organizations |
| 16 | [V1.5TONE](tone.md) | Dictionary-based tone, polarity, activity, self-reference and word counts | [Build resources](../../guides/resources.md) |
| 17 | [V2.1ENHANCEDDATES](enhanced-dates.md) | English calendar/date patterns with offsets | Core only |
| 18 | [V2GCAM](gcam.md) | Matches across configured affect dictionaries | [Build GCAM resources](../../guides/gcam-resources.md#choose-a-preset) |
| 19 | [V2.1SHARINGIMAGE](sharing-image.md) | Formats the supplied sharing-image URL | Supplied metadata |
| 20 | [V2.1RELATEDIMAGES](related-images.md) | Formats supplied related-image URLs | Supplied metadata |
| 21 | [V2.1SOCIALIMAGEEMBEDS](social-image-embeds.md) | Formats supplied social-image embed URLs | Supplied metadata |
| 22 | [V2.1SOCIALVIDEOEMBEDS](social-video-embeds.md) | Formats supplied social-video embed URLs | Supplied metadata |
| 23 | [V2.1QUOTATIONS](quotations.md) | Quoted-span detection with offsets and lengths | Core only |
| 24 | [V2.1ALLNAMES](all-names.md) | Broader NER name labels with authored filtering and offsets | [NER extra and English model](../../get-started/installation-and-setup.md#english-models) |
| 25 | [V2.1AMOUNTS](amounts.md) | Number, currency and unit patterns with offsets | Core only |
| 26 | [V2.1TRANSLATIONINFO](translation-info.md) | Formats the original language and translation engine from translation results or supplied metadata | [Detection and translation setup](../../guides/translation.md#setup) to populate these values automatically |
| 27 | [V2EXTRASXML](extras-xml.md) | Escapes and serializes supplied extra metadata as XML | Supplied metadata |

Language detection is also available independently. See [Translation](../../guides/translation.md). For measured reconstruction agreement and dictionary coverage, see [Results](../../evaluation/results.md).
