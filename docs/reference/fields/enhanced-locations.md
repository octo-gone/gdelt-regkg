# Enhanced locations

`V2ENHANCEDLOCATIONS` uses the same resolved geography as [locations](locations.md), adding ADM2 and a zero-based mention offset.

## Requirements

Install the `ner` extra and an English model, then [prepare the geographic reference](../../guides/resources.md#geographic-reference-files).

## Example

```python
from gdelt_regkg.fields.locations import analyze_locations
from gdelt_regkg.fields.ner import SpacyNER
from gdelt_regkg.fields.ner import analyze_entities

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")
text = "Paris, France hosted the exhibition."

print(analyze_locations(text, recognizer=ner).to_gkg(enhanced=True))
entities = analyze_entities(text, recognizer=ner)
resolved = analyze_locations(text, ner=entities)
```

```text
4#Paris, France (General), France#FR#FR00#16282#48.8667#2.33333#-1456928#0;1#France#FR#FR##46#2#FR#7
```

## Behavior

Each entry has nine `#` components: location type, name, country code, ADM1, ADM2, latitude, longitude, feature ID and offset. Entries are separated by `;`; repeated mentions are separate.

ADM2 uses the reference’s GAUL value when available and stays empty otherwise. It is not inferred from ADM1 or added to count cells. Offsets index the analyzed body; after translation they refer to English text.

Use `resolved.to_gkg(enhanced=True)` to share one geographic resolution pass with the standard field. Unknown or ambiguous places are reported as diagnostics and produce no geographic entry.

## Limitations

The extraction limitations are the same as for [locations](locations.md#limitations). After translation, offsets refer to the analyzed English body.

## Related

[Locations](locations.md) · [Shared NER and geography](locations.md#shared-ner-and-geographic-resolution) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)

[Field index](README.md)
