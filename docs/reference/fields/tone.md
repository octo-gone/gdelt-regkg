# Tone

`V1.5TONE` stores seven numeric components computed by `analyze_tone`. The standard English tone profile uses locally prepared General Inquirer categories with evaluated edits. It approximates GDELT’s tone scoring.

## Requirements

Prepare the field's dictionaries using [Build resources](../../guides/resources.md). Models and additional dependencies are needed only for the selected workflow.

## Example

```python
from gdelt_regkg.fields.tone import analyze_tone

text = "We enjoyed the wonderful concert."

print(analyze_tone(text).to_gkg())
result = analyze_tone(text)
assert result.word_count == 5
```

```text
20,20,0,20,0,20,5
```

## Behavior

| Position | Component |
| --- | --- |
| 1 | Tone, positive density minus negative density |
| 2 | Positive-word density |
| 3 | Negative-word density |
| 4 | Polarity, union of positive and negative matches |
| 5 | Activity-word density |
| 6 | Self/group-reference density |
| 7 | Word count |

Components are separated by commas. Each density is `100 × matched token occurrences / total tokens`. Tone ranges from −100 to +100 points. See [Results](../../evaluation/results.md#tone-scale) for error relative to the native-tone spread. Repeated words count repeatedly. Numbers and stopwords count toward the denominator. Empty or punctuation-only input produces seven zeros.

Tokenization uses Unicode NFKC normalization, case folding and normalized apostrophes. Internal apostrophes and hyphens are included within tokens. Other punctuation separates them. The standard profile is tone v3. [Global Content Analysis Measures (GCAM)](../../get-started/concepts-and-glossary.md#gcam-and-dimensions) sentiment dictionaries are scored separately.

## Options

Load `ToneLexicon.from_json(path)` and pass `lexicon=` to the analyzer/extractor or `Resources(tone_lexicon=lexicon)` to the generator. To select a different local directory, use `default_tone_lexicon(resources_dir=path)` and reuse that object.

`ToneLexicon` accepts custom token sets for each scoring category.

```python
from gdelt_regkg.fields.tone import ToneLexicon
from gdelt_regkg.fields.tone import analyze_tone

lexicon = ToneLexicon(
    name="example", positive={"good"}, negative={"bad"}, activity={"play"}, self_group={"we"}
)
print(analyze_tone("We play good music.", lexicon=lexicon).to_gkg())
```

```text
25,25,0,25,25,25,4
```

JSON profiles require `name` and arrays for the four token categories. The [tone schema](https://github.com/octo-gone/gdelt-regkg/blob/master/src/gdelt_regkg/resources/schemas/tone-lexicon.schema.json) documents the format. The loader also validates normalized tokens.

## Limitations

No stemming, sense disambiguation, negation reversal, intensifier weighting or constant bias adjustment runs. The dictionaries and tokenizer are approximations. Native tone agreement also depends on whether the analyzed body matches GDELT’s original text.

## Related

[Installation and setup](../../get-started/installation-and-setup.md) · [GCAM](gcam.md) · [Current agreement](../../evaluation/results.md#results) · [Tone experiments](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md#seasonal-benchmark)

[GKG field reference](README.md)
