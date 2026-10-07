# Persons

`V1PERSONS` stores distinct recognized person names. `extract_persons` uses an English NER model.

## Example

```python
from gdelt_regkg import SpacyNER, analyze_entities

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")
text = "Marie Curie visited Microsoft in Paris, France."
entities = analyze_entities(text, recognizer=ner)

print("V1PERSONS:", entities.to_gkg("PERSON"))
print("V2ENHANCEDPERSONS:", entities.to_gkg("PERSON", enhanced=True))
print("V1ORGANIZATIONS:", entities.to_gkg("ORG"))
print("Location mentions:", [(m.text, m.start) for m in entities.locations])
```

```text
V1PERSONS: Marie Curie
V2ENHANCEDPERSONS: Marie Curie,0
V1ORGANIZATIONS: Microsoft
Location mentions: [('Paris', 33), ('France', 40)]
```

## Behavior

Names are separated by `;` and deduplicated in first-mention order. No accepted names produces `""`. Original spelling and offsets remain available in `entities.persons`.

Load the recognizer once and reuse it. The standalone extractor uses a cached small English recognizer when `recognizer=` is omitted; missing models raise `NERUnavailableError`. In `generate_gkg`, explicitly pass `ner=recognizer` or `ner=entities` to enable the entity fields. A supplied result must belong to the unchanged body.

## Options

The example uses `name_policy="surface"` to retain spelling and single-word names. The default `gdelt-full-names` lowercases names, normalizes initials and possessives, removes configured leading titles and omits single-word person names. See [name policies](../usage.md#name-policies).

`SpacyNER.from_model("en_core_web_lg")` selects the large English model when it is installed. Existing spans can also be supplied to `analyze_entities` without loading a model.

```python
from gdelt_regkg import EntityMention, analyze_entities

text = "Alice Smith arrived."
entities = analyze_entities(text, mentions=[EntityMention("Alice Smith", "PERSON", 0, 11)])
print(entities.to_gkg("PERSON"))
```

```text
Alice Smith
```

Custom recognizers implement `analyze(text) -> NERResult`. Supplied span text must match its start/end positions. Reserved commas, semicolons and control characters are replaced during serialization; stored mentions remain unchanged.

## Limits

Names depend on the model and policy. The spaCy adapter filters person spans longer than six words or 120 characters, spans crossing blank lines and recognized page-interface phrases. Custom supplied mentions bypass those heuristics. Construct `SpacyNER(nlp, filter_spans=False)` to retain raw model spans.

Surnames and full names are not linked to one identity. A name omitted from a cell may still exist in the recognized mentions.

## Related

[Enhanced persons](enhanced-persons.md) · [Organizations](organizations.md) · [Shared NER and geography](locations.md#shared-ner-and-geographic-resolution) · [Installation and setup](../installation.md) · [Current agreement](../README.md#agreement-with-gdelt)
