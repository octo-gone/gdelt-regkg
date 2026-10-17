# Enhanced persons

`V2ENHANCEDPERSONS` uses the same recognition and name policy as [persons](persons.md), retaining the start position of each accepted mention.

## Requirements

Install the `ner` extra and an English spaCy model. Name rules are included; see [installation](../../installation.md#english-models).

## Example

```python
from gdelt_regkg.fields.ner import SpacyNER
from gdelt_regkg.fields.ner import analyze_entities

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")
text = "Marie Curie spoke. Marie Curie returned."

print(analyze_entities(text, recognizer=ner).to_gkg("PERSON", enhanced=True))
entities = analyze_entities(text, recognizer=ner)
```

```text
Marie Curie,0;Marie Curie,19
```

## Behavior

Entries are `name,offset`, separated by `;`. Repeated names are separate. Offsets are zero-based character positions in the analyzed body, even when the cell policy changes a name’s spelling.

Use `entities.to_gkg("PERSON", enhanced=True)` to share one NER result with the standard field. Pass precomputed recognition to `generate_gkg(text, metadata, resources, ner_result=entities)`; the result must describe that exact body. After translation, offsets refer to the English body.

## Limitations

The extraction limitations are the same as for [persons](persons.md#limitations). After translation, offsets refer to the analyzed English body.

## Related

[Persons](persons.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)

[Field index](README.md)
