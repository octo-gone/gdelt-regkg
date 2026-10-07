# Amounts

`V2.1AMOUNTS` stores numeric quantities with an object description and offset. `extract_amounts` works independently of event counts and needs no model or downloaded dictionary.

## Example

```python
from gdelt_regkg import analyze_amounts
from gdelt_regkg.fields import extract_amounts

text = "We sent twenty-five boxes and spent $1.25 million."
print(extract_amounts(text))
result = analyze_amounts(text)
assert str(result.mentions[0].amount) == "25"
```

```text
25,boxes,8;1250000,dollars,36
```

## Behavior

Entries are `amount,object,offset`, separated by `;`. Offsets point to the numeric span in the analyzed body. `analyze_amounts` retains original spans and `Decimal` values.

Recognizes Western comma grouping, decimals, signed values, English number words through trillions, magnitude suffixes such as `25m`/`2bn`, and $, €, £, ₹, USD, EUR, GBP and INR prefixes. Currency prefixes become object names; other objects use up to three following words, stopping at common verbs, prepositions and punctuation. Missing objects stay empty.

Percentages, date spans and common version/time/fraction forms are excluded. Repeated quantities remain separate. No accepted amounts produces `""`.

## Options

Pass `numeric_order="mdy"` or `"dmy"` to control slash-date exclusion consistently with the date extractor. The generator uses `numeric_date_order=` for both fields.

## Limits

Indefinite quantities such as “hundreds of boxes” receive no exact value. European decimal commas, scientific notation and grammatical object attachment are unsupported. The bounded object description can include an unrelated word or miss a distant object.

## Related

[Counts](counts.md) · [Date mentions](enhanced-dates.md) · [Current agreement](../README.md#agreement-with-gdelt) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
