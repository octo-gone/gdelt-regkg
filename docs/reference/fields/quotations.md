# Quotations

`V2.1QUOTATIONS` stores directly quoted spans and nearby reporting verbs. `analyze_quotations` uses quotation marks and English verb patterns. It needs no named NER model or downloaded dictionary.

## Requirements

Core package only. No external dictionary or NLP model is required.

## Example

```python
from gdelt_regkg.fields.quotations import analyze_quotations

text = "Alice said, \"The workshop is ready.\""

print(analyze_quotations(text).to_gkg())
result = analyze_quotations(text)
mention = result.mentions[0]
assert text[mention.start : mention.end] == mention.text
assert mention.verb == "said"
```

```text
13|22|said|The workshop is ready.
```

## Behavior

Entries use `offset|length|verb|quote`, separated by `#`. Offset starts at the first content character, excluding quotation marks and surrounding whitespace. Length describes that original body span. The verb may be empty. Repeated quotations are separate.

Recognizes straight/curly double and single quotation marks and guillemets. Apostrophes inside words are ignored. Nested quotes of another style are included inside the outer quote. Nearby reporting verbs are matched without crossing a sentence, line break or another quotation.

Reserved `#`/`|` separators and control characters become spaces, and whitespace is collapsed. Stored mentions preserve the original span. Length can differ from the cleaned output’s length. `result.issues` reports delimiter normalization, unclosed quotes and content that becomes empty. No quotes produces `""`.

## Options

The generator fills this field automatically. An encoded `overrides["V2.1QUOTATIONS"]` override takes precedence. Use `analyze_quotations` when you need original spans, verbs or diagnostics.

## Limitations

The extractor does not identify speakers or indirect speech, and can include quoted titles or scare quotes. Nearby verbs can be missed or assigned incorrectly. Exact-content agreement with native GDELT quotations is low. Retrieved body and boundary differences also affect it.

Content-only and content-plus-verb agreement use different matching rules. No comparable trivial extraction baseline has been reported. See [Results](../../evaluation/results.md#tone-scale) for scores and interpretation.

## Related

[Generate records](../../guides/records.md) · [Current agreement](../../evaluation/results.md#results) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)

[GKG field reference](README.md)
