# Locations

`V1LOCATIONS` stores resolved geographic records. `extract_locations` recognizes place names with the shared English NER model, then looks them up in a locally prepared geographic reference database (gazetteer).

## Example

```python
from gdelt_regkg import SpacyNER, analyze_entities, analyze_locations

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")
text = 'Paris, France hosted the exhibition.'
entities = analyze_entities(text, recognizer=ner)
print("Location mentions:", [(m.text, m.source_label, m.start) for m in entities.locations])

# Resolve the recognized spans without running NER again.
resolved = analyze_locations(text, ner=entities)
print("V1LOCATIONS:", resolved.to_gkg())
print("V2ENHANCEDLOCATIONS:", resolved.to_gkg(enhanced=True))
```

```text
Location mentions: [('Paris', 'GPE', 0), ('France', 'GPE', 7)]
V1LOCATIONS: 4#Paris, France (General), France#FR#FR00#48.8667#2.33333#-1456928;1#France#FR#FR#46#2#FR
V2ENHANCEDLOCATIONS: 4#Paris, France (General), France#FR#FR00#16282#48.8667#2.33333#-1456928#0;1#France#FR#FR##46#2#FR#7
```

## Behavior

Each record has seven `#` components: location type, name, country code, ADM1 code, latitude, longitude and feature ID. Records are separated by `;`; identical formatted records are deduplicated. Country/ADM1 codes use FIPS conventions, and feature IDs retain GDELT’s GNS/GNIS identifiers.

The spaCy adapter maps `GPE` (countries, cities and states), `LOC` (other geographic areas) and `FAC` (facilities) into `LOCATION` spans. A recognized span needs a reference match before it can produce geographic codes or coordinates.

Nearby country or state mentions within 200 characters help resolve ambiguous names. Otherwise, a candidate must account for at least 80% of the alias’s reference frequency. Unresolved names appear in `resolved.issues`. `resolved.count_locations` supplies compatible spans for count extraction.

## Options

### Shared NER and geographic resolution

`analyze_entities` returns person, organization and location spans in one result. `analyze_names` and `analyze_locations` use that result to produce broad name and geographic fields without repeating recognition.

```python
from gdelt_regkg import SpacyNER, analyze_entities, analyze_locations, analyze_names

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")
text = "Marie Curie visited Microsoft in Paris, France."
entities = analyze_entities(text, recognizer=ner)
resolved = analyze_locations(text, ner=entities)
names = analyze_names(text, ner=entities)

print("V1PERSONS:", entities.to_gkg("PERSON"))
print("V1ORGANIZATIONS:", entities.to_gkg("ORG"))
print("Location mentions:", [(m.text, m.start) for m in entities.locations])
print("V2.1ALLNAMES:", names.to_gkg())
print("V1LOCATIONS:", resolved.to_gkg())
print("V2ENHANCEDLOCATIONS:", resolved.to_gkg(enhanced=True))
```

```text
V1PERSONS: Marie Curie
V1ORGANIZATIONS: Microsoft
Location mentions: [('Paris', 33), ('France', 40)]
V2.1ALLNAMES: Marie Curie,0;Microsoft,20;Paris,33;France,40
V1LOCATIONS: 4#Paris, France (General), France#FR#FR00#48.8667#2.33333#-1456928;1#France#FR#FR#46#2#FR
V2ENHANCEDLOCATIONS: 4#Paris, France (General), France#FR#FR00#16282#48.8667#2.33333#-1456928#33;1#France#FR#FR##46#2#FR#40
```

Pass `ner=entities` to `generate_gkg` to reuse recognition of that exact body. The generator resolves both location columns once and supplies their geography to counts.

### Unresolved mentions

Raw place spans remain available in `entities.locations` even when geographic resolution produces an empty cell.

```python
from gdelt_regkg import EntityMention, analyze_entities, analyze_locations

text = "Atlantis"
entities = analyze_entities(text, mentions=[EntityMention("Atlantis", "LOCATION", 0, 8)])
resolved = analyze_locations(text, ner=entities)
print([m.text for m in entities.locations])
print(repr(resolved.to_gkg()))
print([(issue.text, issue.reason) for issue in resolved.issues])
```

```text
['Atlantis']
''
[('Atlantis', 'unknown-place')]
```

`extract_location_mentions(text, recognizer=ner)` also returns raw place spans. `entities.to_gkg("LOCATION")` is unsupported because raw NER spans do not contain resolved geography.

Load a custom JSON/gzip database with `Gazetteer.from_json(path)` and pass `gazetteer=` to the analyzer, extractor or generator. See the [gazetteer schema](../../src/gdelt_regkg/resources/schemas/gazetteer.schema.json) and [resource setup](../installation.md#build-a-custom-gazetteer).

## Limits

The standard reference contains 17,177 records across 237 country codes; it misses unobserved cities, landmarks and spellings. Matching does not implement transliteration, demonym resolution or a complete geocoder. Frequency preferences can select the wrong place, and historical reference records are not a current boundary database.

This lookup was compiled from 20 GKG archives from 2015–2019. **A recognized place without a lookup entry is omitted from both GKG location columns and cannot supply geography to counts.** Its raw NER span and `unknown-place` diagnostic remain available. There is no external geocoding fallback. Use a more comprehensive compatible gazetteer when broad coverage is required; the recorded profile preserves the previous benchmark configuration.

## Related

[Enhanced locations](enhanced-locations.md) · [Persons](persons.md) · [Organizations](organizations.md) · [All names](all-names.md) · [Installation and setup](../installation.md) · [Current agreement](../README.md#agreement-with-gdelt)
