# Enhanced themes

`V2ENHANCEDTHEMES` uses the same matcher as [themes](themes.md), retaining the offset of every matched phrase.

## Example

```python
from gdelt_regkg import analyze_themes
from gdelt_regkg.fields import extract_enhanced_themes

text = 'Heavy rain caused flooding.'
print(extract_enhanced_themes(text))
result = analyze_themes(text)
assert text[result.mentions[0].start:result.mentions[0].end] == "flooding"
# Reuse result.to_gkg() for the standard theme field.
```

```text
CRISISLEX_C06_WATER_SANITATION,18;NATURAL_DISASTER_FLOODING,18;
```

## Behavior

Each mention is written as `CODE,offset;`. Offsets are zero-based character positions in the analyzed body. Repeated and overlapping phrase hits remain separate; several labels can share an offset.

Use `analyze_themes(text).to_gkg(enhanced=True)` to reuse one analysis for both fields. Context conditions and label coverage are the same as for standard themes. After translation, offsets refer to the English body.

## Related

[Themes](themes.md) · [Translation information](translation-info.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
