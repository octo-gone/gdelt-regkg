# Enhanced counts

`V2.1COUNTS` uses the same extraction as [counts](counts.md), with a zero-based character offset for the quantity.

## Example

```python
from gdelt_regkg import SpacyNER, analyze_counts, analyze_entities, analyze_locations

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")
text = "Volunteers rescued 12 people in Paris, France."
entities = analyze_entities(text, recognizer=ner)
resolved = analyze_locations(text, ner=entities)
result = analyze_counts(text, locations=resolved.count_locations)
print(result.to_gkg(enhanced=True))
assert text[result.mentions[0].start:result.mentions[0].start + 2] == "12"
# Reuse result.to_gkg() for the standard count field.
```

```text
CRISISLEX_T08_MISSINGFOUNDTRAPPEDPEOPLE#12#people#4#Paris, France (General), France#FR#FR00#48.8667#2.33333#-1456928#19;
```

## Behavior

Entries have the ten standard count components followed by the number offset, separated by `#` and terminated with `;`. No ADM2 component is added.

Use `analyze_counts(text).to_gkg(enhanced=True)` when sharing one analysis across both count fields. Rules, geography and rejected-match diagnostics are the same as for standard counts. After translation, offsets refer to the analyzed English body.

## Related

[Counts](counts.md) · [Translation information](translation-info.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
