# GKG field reference

The library supports all 27 GKG wire columns. Text-derived fields approximate GDELT processing; metadata and media fields format caller-supplied values. Enhanced fields add zero-based character offsets into the exact analyzed English body.

Columns below follow the order declared by `GKG_COLUMNS`. Each page describes encoding, examples and limitations. See [quickstart](../../quickstart.md) for standalone analyzers and [record generation](../../guides/records.md) to combine fields.

| GKG column | How it is produced | Setup |
| --- | --- | --- |
| [GKGRECORDID](record-id.md) | Batch timestamp and sequence; `T` marks translated records | Supplied `RecordMetadata` |
| [V2.1DATE](date.md) | Batch timestamp; publication time is kept separately in extra XML | Supplied metadata |
| [V2SOURCECOLLECTIONIDENTIFIER](source-collection.md) | Validated source collection identifier | Supplied metadata |
| [V2SOURCECOMMONNAME](source-name.md) | Supplied source name or hostname derived from the document URL | Supplied metadata |
| [V2DOCUMENTIDENTIFIER](document-identifier.md) | Supplied document URL or identifier | Supplied metadata |
| [V1COUNTS](counts.md) | Authored English number/event rules with optional resolved geography | Rules included; [NER and geography](../../installation.md#basic-english-setup) for place enrichment |
| [V2.1COUNTS](enhanced-counts.md) | Count matches with character offsets | Same as counts |
| [V1THEMES](themes.md) | Phrase matching against theme dictionaries | [Build local resources](../../guides/resources.md) |
| [V2ENHANCEDTHEMES](enhanced-themes.md) | Theme matches with offsets | Same as themes |
| [V1LOCATIONS](locations.md) | NER place mentions resolved against an offline gazetteer | [spaCy model and local resources](../../installation.md#basic-english-setup) |
| [V2ENHANCEDLOCATIONS](enhanced-locations.md) | Resolved place occurrences with offsets and administrative details | Same as locations |
| [V1PERSONS](persons.md) | NER person mentions with name normalization and filtering | [NER extra and English model](../../installation.md#english-models) |
| [V2ENHANCEDPERSONS](enhanced-persons.md) | Person mentions with offsets | Same as persons |
| [V1ORGANIZATIONS](organizations.md) | NER organization mentions with authored name filtering | [NER extra and English model](../../installation.md#english-models) |
| [V2ENHANCEDORGANIZATIONS](enhanced-organizations.md) | Organization mentions with offsets | Same as organizations |
| [V1.5TONE](tone.md) | Dictionary-based tone, polarity, activity, self-reference and word counts | [Build tone resources](../../guides/resources.md) |
| [V2.1ENHANCEDDATES](enhanced-dates.md) | English calendar/date patterns with offsets | Core only |
| [V2GCAM](gcam.md) | Matches across configured affect dictionaries | [Build GCAM resources](../../guides/resources.md#gcam-profiles-and-expansion) |
| [V2.1SHARINGIMAGE](sharing-image.md) | Formats the supplied sharing-image URL | Supplied metadata |
| [V2.1RELATEDIMAGES](related-images.md) | Formats supplied related-image URLs | Supplied metadata |
| [V2.1SOCIALIMAGEEMBEDS](social-image-embeds.md) | Formats supplied social-image embed URLs | Supplied metadata |
| [V2.1SOCIALVIDEOEMBEDS](social-video-embeds.md) | Formats supplied social-video embed URLs | Supplied metadata |
| [V2.1QUOTATIONS](quotations.md) | Quoted-span detection with offsets and lengths | Core only |
| [V2.1ALLNAMES](all-names.md) | Broader NER name labels with authored filtering and offsets | [NER extra and English model](../../installation.md#english-models) |
| [V2.1AMOUNTS](amounts.md) | Number, currency and unit patterns with offsets | Core only |
| [V2.1TRANSLATIONINFO](translation-info.md) | Formats language/engine provenance from explicit translation or metadata | [Detection and translation setup](../../installation.md#non-english-articles) for automatic provenance |
| [V2EXTRASXML](extras-xml.md) | Escapes and serializes supplied extra metadata as XML | Supplied metadata |


Language detection is also available independently; see [translation](../../guides/translation.md). For measured reconstruction agreement and dictionary coverage, see [evaluation results](../../evaluation/results.md).
