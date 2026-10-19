# All names

`V2.1ALLNAMES` stores broad name mentions and their offsets. `analyze_names` shares the English NER result with persons, organizations and locations, and also includes other named categories and proper-noun sequences.

## Requirements

Install the `ner` extra and an English spaCy model. Name rules are included. See [installation](../../get-started/installation-and-setup.md#english-models).

## Example

```python
from gdelt_regkg.fields.names import analyze_names
from gdelt_regkg.fields.ner import SpacyNER
from gdelt_regkg.fields.ner import analyze_entities

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")
text = "Marie Curie visited Microsoft in Paris, France."

print(analyze_names(text, recognizer=ner).to_gkg())
entities = analyze_entities(text, recognizer=ner)
names = analyze_names(text, ner=entities)
assert names.mentions == entities.all_names
```

```text
Marie Curie,0;Microsoft,20;Paris,33;France,40
```

## Behavior

Entries are `name,offset`, separated by `;`. Repeated names are separate. Surface spelling is retained independently of person/organization normalization, title removal and cell filters. Reserved delimiters and whitespace are cleaned only when serializing. Offsets are unchanged.

Alongside people, organizations and places, the spaCy backend includes named groups, products, events, works of art, laws and languages. Its tagger also finds proper-noun sequences outside recognized entities. Numeric and temporal entity categories are excluded.

Use `analyze_names(text, ner=entities)` or `entities.all_names` to reuse recognition. The generator shares that same result across entity and name fields.

## Options

Custom backends can supply `NameMention` spans through `NERResult(..., name_mentions=...)`. Without that extension, broad names fall back to supplied person, organization and location mentions. A backend without POS tags cannot provide the proper-noun fallback.

## Limitations

Broad proper-noun inclusion can create extra matches. Models can miss or split names. This is an approximation of GDELT’s separate Names engine and does not resolve aliases or identities.

## Related

[Persons](persons.md) · [Organizations](organizations.md) · [Locations](locations.md) · [Installation and setup](../../get-started/installation-and-setup.md) · [Current agreement](../../evaluation/results.md#results)

[GKG field reference](README.md)
