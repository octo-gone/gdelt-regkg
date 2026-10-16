# Enhanced themes

`V2ENHANCEDTHEMES` uses the same matcher as [themes](themes.md), retaining the offset of every matched phrase.

## Requirements

Prepare the corresponding [local resource profile](../../guides/resources.md). Models and additional dependencies are needed only for the selected workflow.

## Example

```python
from gdelt_regkg.fields.themes import analyze_themes

text = "Heavy rain caused flooding."

print(analyze_themes(text).to_gkg(enhanced=True))
result = analyze_themes(text)
assert text[result.mentions[0].start : result.mentions[0].end] == "flooding"
```

```text
CRISISLEX_C06_WATER_SANITATION,18;NATURAL_DISASTER_FLOODING,18;
```

## Behavior

Each mention is written as `CODE,offset;`. Offsets are zero-based character positions in the analyzed body. Repeated and overlapping phrase hits remain separate; several labels can share an offset.

Use `analyze_themes(text).to_gkg(enhanced=True)` to reuse one analysis for both fields. Context conditions and label coverage are the same as for standard themes. After translation, offsets refer to the English body.

## Limitations

The extraction limitations are the same as for [themes](themes.md#limitations). After translation, offsets refer to the analyzed English body.

## Related

[Themes](themes.md) · [Translation information](translation-info.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)

[Field index](README.md) · [Python API](../python-api.md)
