# Enhanced persons

`V2ENHANCEDPERSONS` uses the same recognition and name policy as [persons](persons.md), retaining the start position of each accepted mention.

## Example

```python
from gdelt_regkg import SpacyNER, analyze_entities
from gdelt_regkg.fields import extract_enhanced_persons

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")
text = 'Marie Curie spoke. Marie Curie returned.'
print(extract_enhanced_persons(text, recognizer=ner))
entities = analyze_entities(text, recognizer=ner)
# Reuse entities.to_gkg("PERSON") for the standard person field.
```

```text
Marie Curie,0;Marie Curie,19
```

## Behavior

Entries are `name,offset`, separated by `;`. Repeated names remain separate. Offsets are zero-based character positions in the analyzed body, even when the cell policy changes a name’s spelling.

Use `entities.to_gkg("PERSON", enhanced=True)` to share one NER result with the standard field. The generator also accepts `ner=entities`. After translation, offsets refer to the English body.

## Related

[Persons](persons.md) · [Name policies](../usage.md#name-policies) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
