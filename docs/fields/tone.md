# Tone

`V1.5TONE` stores seven numeric components computed by `extract_tone`. The standard English tone profile uses locally prepared General Inquirer categories with evaluated edits; it approximates GDELT’s tone scoring.

## Example

```python
from gdelt_regkg import analyze_tone
from gdelt_regkg.fields import extract_tone

text = 'We enjoyed the wonderful concert.'
print(extract_tone(text))
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

Components are separated by commas. Each density is `100 × matched token occurrences / total tokens`. Repeated words count repeatedly; numbers and stopwords remain in the denominator. Empty or punctuation-only input produces seven zeros.

Tokenization uses Unicode NFKC normalization, case folding and normalized apostrophes. Internal apostrophes and hyphens remain within tokens; other punctuation separates them. The standard profile is tone v3; GCAM sentiment dictionaries are scored separately.

## Options

Load `ToneLexicon.from_json(path)` and pass `lexicon=` to the analyzer/extractor or `tone_lexicon=` to the generator. To select a different local directory, use `default_tone_lexicon(resources_dir=path)` and reuse that object.

`ToneLexicon` accepts custom token sets for each scoring category.

```python
from gdelt_regkg import ToneLexicon
from gdelt_regkg.fields import extract_tone

lexicon = ToneLexicon(
    name="example",
    positive={"good"},
    negative={"bad"},
    activity={"play"},
    self_group={"we"},
)
print(extract_tone("We play good music.", lexicon=lexicon))
```

```text
25,25,0,25,25,25,4
```

JSON profiles require `name` and arrays for the four token categories. The [tone schema](../../src/gdelt_regkg/resources/schemas/tone-lexicon.schema.json) documents the format; the loader also validates normalized tokens.

## Limits

No stemming, sense disambiguation, negation reversal, intensifier weighting or constant bias adjustment runs. The dictionaries and tokenizer are approximations; native tone agreement also depends on whether the analyzed body matches GDELT’s original text.

## Related

[Installation and setup](../installation.md) · [GCAM](gcam.md) · [Current agreement](../README.md#agreement-with-gdelt) · [Tone experiments](../../CHANGELOG.md#seasonal-benchmark)
