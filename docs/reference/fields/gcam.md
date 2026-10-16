# GCAM

`V2GCAM` contains word counts, dictionary category counts and weighted mean scores. `analyze_gcam` takes prepared English text, optionally accompanied by the original body and its language, using a compiled GCAM lexicon.

## Requirements

Prepare the corresponding [local resource profile](../../guides/resources.md). Models and additional dependencies are needed only for the selected workflow.

## Example

```python
from gdelt_regkg.fields.gcam import analyze_gcam

result = analyze_gcam("Good good bad.")
assert result.word_count == 3
assert result.counts["c26.1"] == 3
print(result.to_gkg())
```

The serialized cell begins with `wc:N`. Category counts use `c` keys and weighted means use `v` keys. Zero-match counts are omitted. A matched mean of zero is retained; a mean with no matches is omitted.

`result.counts` includes applicable zero-match categories. `result.values` contains defined means, and `result.implemented_dimensions` identifies evaluated keys. The lexicon's `implemented_dimensions` lists its complete compiled inventory.

## Profiles

| Profile | Compiled dimensions | Selection |
| --- | ---: | --- |
| `v3` | 809 / 2,888 | Default |
| `v4` | 1,855 / 2,888 | Adds Roget and Lexicoder |
| `v5` | 2,597 / 2,888 | 2,328 source-backed dimensions plus 269 approximations |
| `full` | Same as `v5` | Alias for `v5` |

Use the [build command](../../guides/resources.md#gcam-profiles-and-expansion) to prepare a profile. The [dictionary reference](../dictionaries.md) lists dictionary IDs, descriptions, acquisition steps, license notes and BibTeX citations.

Coverage pairs a category's count/value keys and excludes `wc` and `nwc`. The v5 inventory contains 2,296 English and 301 non-English dimensions. Its 268 authored theme dimensions use local matching rules rather than recovered GDELT rules. Coverage reports separate `compiled_dimensions` (2,597) from source-backed `supported_dimensions` (2,328) and list `approximate_dimensions`. French imagery contributes one additional class-midpoint approximation. Neither count establishes extraction accuracy. `full` names the broadest preset; complete native coverage is not implied.

## Select dictionaries

The following example requires the v5 profile; build it using the [resource guide](../../guides/resources.md#gcam-profiles-and-expansion), or select another prepared lexicon file.

```python
from gdelt_regkg.fields.gcam import GCAMLexicon, analyze_gcam

lexicon = GCAMLexicon.from_json("local-resources/lexicons/gcam.v5.json.gz")
result = analyze_gcam(
    "Good good bad.",
    lexicon=lexicon,
    disabled_dictionaries=("roget", "wordnet-affect", 26),
)
```

Pass the lexicon as `Resources(gcam_lexicon=lexicon)` when generating a record. The generator's exclusion option is `gcam_disabled_dictionaries=...`.

Selectors accept a collection of dictionary names, integer IDs or numeric strings. Known dictionaries absent from the profile have no effect; unknown selectors raise an error. Exclusions remove counts, values and implemented keys while preserving word counts. Excluding dictionary 23 removes all its language variants. Excluding all dictionaries produces only `wc`, and `nwc` when an original-text stream is supplied.

Use `lexicon.without_dictionaries(...)` to reuse a filtered lexicon. For benchmarks, `--gcam-disable` applies the same exclusions to generation and scoring. A `V2GCAM` override bypasses GCAM analysis.

## Translation

After translation, generate the record from its English body and also supply the original body to include native GCAM dictionaries. This example represents an already translated body with `TranslationResult`; it requires the English NER model and standard resources. For actual model translation, follow the [translation guide](../../guides/translation.md).

```python
from gdelt_regkg import RecordMetadata, Resources, generate_gkg
from gdelt_regkg.fields.ner import SpacyNER
from gdelt_regkg.fields.translation import TranslationResult

result = TranslationResult("amour", "love", "fra", "Example translation engine")
metadata = RecordMetadata(
    identifier="https://example.org/story", batch_time="20261001091500", sequence=1,
    sharing_image="", related_images=[], social_image_embeds=[], social_video_embeds=[],
    extras={},
)
resources = Resources(resources_dir="local-resources", recognizer=SpacyNER.from_model())
translated_metadata = RecordMetadata.from_translation(result, metadata)
record = generate_gkg(
    result.text, translated_metadata, resources,
    gcam_original_text=result.original_text if result.translated else None,
    strict=True,
)
```

`RecordMetadata.from_translation` copies language and engine provenance. English dictionaries analyze `result.text`; dictionaries matching the source language analyze `gcam_original_text`. Other GKG fields and their offsets still use the English body. `wc` counts the English tokens; `GCAMResult.native_word_count` and the serialized `nwc` count original-language tokens when supplied. Metadata alone does not trigger native analysis.

All source languages use the same English-plus-original-text interface:

```python
from gdelt_regkg.fields.gcam import analyze_gcam

combined = analyze_gcam(
    result.text, lexicon=resources.gcam(),
    original_text=result.original_text, original_language=result.source_language,
)
```

Original-language names and ISO aliases normalize to three-letter codes. `text` is always prepared English and supplies `wc`; optional original text supplies `nwc`. Supply both original-text arguments together. Without them, GCAM analyzes English only. Dictionaries for other languages are not evaluated, even when their words also occur in the article. The analyzer does not detect or translate languages. See [translation usage](../../guides/translation.md#language-detection-and-translation).

Chinese Hedonometer uses this same interface: pass English text with Chinese `original_text` and `original_language="zho"`, or supply `gcam_original_text` to `generate_gkg` with Chinese source-language metadata. The `build` extra supplies Jieba segmentation, using its standard dictionary with HMM disabled. No dictionary-specific expansions are inferred. Word counts and matches can differ from GDELT’s segmentation.

## Custom lexicons

Load compatible JSON or gzip profiles with `GCAMLexicon.from_json`. The [schema](../../../src/gdelt_regkg/resources/schemas/gcam-lexicon.schema.json) supports count vocabularies, phrase/wildcard patterns and weighted score maps. Each dimension can declare a three-letter `language`; omitted metadata defaults to English. Weighted maps provide companion counts by default; `emit_count: false` enables value-only dimensions. Count/value companions share one language. Source exclusion tokens and phrases mask matching spans within their dictionary.

```python
from gdelt_regkg.fields.gcam import GCAMLexicon, analyze_gcam

lexicon = GCAMLexicon(name="example", dimensions={"c2.21": frozenset({"hand"})})
print(analyze_gcam("hand hand", lexicon=lexicon).to_gkg())
```

```text
wc:2,c2.21:2
```

Duplicate keys, nonfinite scores and conflicting count vocabularies are rejected. Custom vocabularies retain the terms of their source data.

## Limitations

- Dictionary editions, tokenization and word-sense handling can differ from GDELT.
- Native tokenization preserves Unicode letters and combining marks. No inferred stemming or GDELT-specific morphological expansion is applied; source wildcards and exclusions are retained.
- WordNet and Roget matching uses phrases and morphology without contextual sense disambiguation.
- VADER uses lexical means without sentence-level negation, emphasis or compound-score heuristics.
- Lexicoder's full preprocessing pipeline is not implemented.
- Theme matching covers a subset of native categories. Licensed and manually acquired dictionaries require separate source files.

## Dictionary licenses

Dictionary licenses apply to their vocabularies and compiled derivatives. See the [license table and per-dictionary notes](../dictionaries.md#dictionary-licenses) for license names, restrictions and source links.

## Related

[Build resources](../../guides/resources.md) · [API usage](../../guides/records.md) · [Dictionary reference](../dictionaries.md) · [GCAM agreement](../../evaluation/results.md#gcam)

[Field index](README.md) · [Python API](../python-api.md)
