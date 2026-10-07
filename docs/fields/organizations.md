# Organizations

`V1ORGANIZATIONS` stores distinct recognized organization names. `extract_organizations` uses an English NER model.

## Example

```python
from gdelt_regkg import SpacyNER, analyze_entities

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")
text = "Marie Curie visited Microsoft in Paris, France."
entities = analyze_entities(text, recognizer=ner)

print("V1ORGANIZATIONS:", entities.to_gkg("ORG"))
print("V2ENHANCEDORGANIZATIONS:", entities.to_gkg("ORG", enhanced=True))
print("V1PERSONS:", entities.to_gkg("PERSON"))
print("Location mentions:", [(m.text, m.start) for m in entities.locations])
```

```text
V1ORGANIZATIONS: Microsoft
V2ENHANCEDORGANIZATIONS: Microsoft,20
V1PERSONS: Marie Curie
Location mentions: [('Paris', 33), ('France', 40)]
```

## Behavior

Names are separated by `;` and deduplicated in first-mention order. No accepted names produces `""`. Original organization spans remain available in `entities.organizations`.

Reuse a loaded recognizer across documents. The standalone extractor loads a cached small English recognizer if omitted; the row generator requires `ner=recognizer` or `ner=entities`. Recognized mentions are shared across both organization fields and the other entity columns.

## Options

`name_policy="surface"` retains spelling and single-word organizations such as `Microsoft`. The default `gdelt-full-names` canonicalizes names, removes single-word names and applies a learned organization filter. Some genuine organizations are consequently absent from GKG cells.

Use `name_policy="gdelt"` to keep single-word organizations with canonical formatting. Pass `name_rules=NameRules()` to disable the learned filter while retaining the selected policy. See [name policies](../usage.md#name-policies) and [supplied mentions](persons.md#options) for custom backends.

## Limits

Model spans and cell filtering can miss institutions, split names or classify a name incorrectly. The spaCy adapter filters organization spans longer than twelve words or 120 characters, spans crossing blank lines and recognized page-interface phrases. Construct `SpacyNER(nlp, filter_spans=False)` to retain raw model spans.

Abbreviations and alternate names are not resolved to one identity.

## Related

[Enhanced organizations](enhanced-organizations.md) · [Persons](persons.md) · [Shared NER and geography](locations.md#shared-ner-and-geographic-resolution) · [Installation and setup](../installation.md) · [Current agreement](../README.md#agreement-with-gdelt)
