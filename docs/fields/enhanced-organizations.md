# Enhanced organizations

`V2ENHANCEDORGANIZATIONS` uses the same recognition and name policy as [organizations](organizations.md), retaining each accepted mention’s start position.

## Example

```python
from gdelt_regkg import SpacyNER, analyze_entities
from gdelt_regkg.fields import extract_enhanced_organizations

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")
text = 'Microsoft opened a store. Microsoft expanded.'
print(extract_enhanced_organizations(text, recognizer=ner))
entities = analyze_entities(text, recognizer=ner)
# Reuse entities.to_gkg("ORG") for the standard organization field.
```

```text
Microsoft,0;Microsoft,26
```

## Behavior

Entries are `name,offset`, separated by `;`. Repeated names remain separate. Offsets are zero-based character positions in the analyzed body; normalization and cell filters do not shift them.

Use `entities.to_gkg("ORG", enhanced=True)` to share one NER result with the standard field. The generator accepts `ner=entities`. After translation, offsets refer to the English body.

## Related

[Organizations](organizations.md) · [Name policies](../usage.md#name-policies) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
