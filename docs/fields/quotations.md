# Quotations

`V2.1QUOTATIONS` stores directly quoted spans and nearby reporting verbs. `extract_quotations` uses quotation marks and English verb patterns; it needs no NER model or downloaded dictionary.

## Example

```python
from gdelt_regkg import analyze_quotations
from gdelt_regkg.fields import extract_quotations

text = 'Alice said, "The workshop is ready."'
print(extract_quotations(text))
result = analyze_quotations(text)
mention = result.mentions[0]
assert text[mention.start:mention.end] == mention.text
assert mention.verb == "said"
```

```text
13|22|said|The workshop is ready.
```

## Behavior

Entries use `offset|length|verb|quote`, separated by `#`. Offset starts at the first content character, excluding quotation marks and surrounding whitespace. Length describes that original body span. The verb may be empty; repeated quotations remain separate.

Recognizes straight/curly double and single quotation marks and guillemets. Apostrophes inside words are ignored. Nested quotes of another style remain inside the outer quote. Nearby reporting verbs are matched without crossing a sentence, line break or another quotation.

Reserved `#`/`|` separators and control characters become spaces, and whitespace is collapsed. Stored mentions preserve the original span; length can differ from the cleaned output’s length. `result.issues` reports delimiter normalization, unclosed quotes and content that becomes empty. No quotes produces `""`.

## Options

The generator fills this field automatically. An encoded `field_values["V2.1QUOTATIONS"]` override takes precedence. Use `analyze_quotations` when you need original spans, verbs or diagnostics.

## Limits

The extractor does not identify speakers or indirect speech, and can include quoted titles or scare quotes. Nearby verbs can be missed or assigned incorrectly. Exact-content agreement with native GDELT quotations is low; retrieved body and boundary differences also affect it.

## Related

[Shared API usage](../usage.md) · [Current agreement](../README.md#agreement-with-gdelt) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
