# Persons

`V1PERSONS` stores distinct recognized person names. `analyze_entities` uses an English NER model.

## Requirements

Install the `ner` extra and an English spaCy model. Name rules are included; see [installation](../../installation.md#english-models).

## Example

```python
from gdelt_regkg.fields.ner import SpacyNER
from gdelt_regkg.fields.ner import analyze_entities

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

Load the recognizer once and reuse it. `analyze_entities` uses a cached small English recognizer when `recognizer=` is omitted; missing models raise `NERUnavailableError`. For record generation, supply it through `Resources(recognizer=ner)` and call `generate_gkg(text, metadata, resources)`, or pass precomputed recognition as `ner_result=entities`. The result must describe the exact analyzed body. See [the generation example](../../guides/records.md#generate-a-gkg-record).

## Options

The example uses `name_policy="surface"` to retain spelling and single-word names. The default `gdelt-full-names` lowercases names, normalizes initials and possessives, removes configured leading titles and omits single-word person names. See [name policies](../python-api.md#name-policies).

`SpacyNER.from_model("en_core_web_lg")` selects the large English model when it is installed. Existing spans can also be supplied to `analyze_entities` without loading a model.

```python
from gdelt_regkg.fields.ner import EntityMention
from gdelt_regkg.fields.ner import analyze_entities

text = "Alice Smith arrived."
entities = analyze_entities(text, mentions=[EntityMention("Alice Smith", "PERSON", 0, 11)])
print(entities.to_gkg("PERSON"))
```

```text
Alice Smith
```

Custom recognizers implement `analyze(text) -> NERResult`. Supplied span text must match its start/end positions. Reserved commas, semicolons and control characters are replaced during serialization; stored mentions remain unchanged.

## Limitations

Names depend on the model and policy. The spaCy adapter filters person spans longer than six words or 120 characters, spans crossing blank lines and recognized page-interface phrases. Custom supplied mentions bypass those heuristics. Construct `SpacyNER(nlp, filter_spans=False)` to retain raw model spans.

Surnames and full names are not linked to one identity. A name omitted from a cell may still exist in the recognized mentions.

## Related

[Enhanced persons](enhanced-persons.md) · [Organizations](organizations.md) · [Shared NER and geography](locations.md#shared-ner-and-geographic-resolution) · [Installation and setup](../../installation.md) · [Current agreement](../../evaluation/results.md#agreement-with-gdelt)

[Field index](README.md) · [Python API](../python-api.md)
