# Counts

`V1COUNTS` stores event-related quantities, object descriptions and geographic components. `analyze_counts` applies English quantity and trigger rules with 37 supported labels. Count rules are included with the package.

## Requirements

Core package only. Count geography additionally requires an English NER model and a prepared geographic reference.

## Example

```python
from gdelt_regkg.fields.counts import analyze_counts
from gdelt_regkg.fields.locations import analyze_locations
from gdelt_regkg.fields.ner import SpacyNER
from gdelt_regkg.fields.ner import analyze_entities

ner = SpacyNER.from_model("en_core_web_sm", name_policy="surface")
text = "Volunteers rescued 12 people in Paris, France."

entities = analyze_entities(text, recognizer=ner)
resolved = analyze_locations(text, ner=entities)
result = analyze_counts(text, locations=resolved.count_locations)
print("V1COUNTS:", result.to_gkg())
print("V2.1COUNTS:", result.to_gkg(enhanced=True))
assert result.mentions[0].number == 12
```

```text
V1COUNTS: CRISISLEX_T08_MISSINGFOUNDTRAPPEDPEOPLE#12#people#4#Paris, France (General), France#FR#FR00#48.8667#2.33333#-1456928;
V2.1COUNTS: CRISISLEX_T08_MISSINGFOUNDTRAPPEDPEOPLE#12#people#4#Paris, France (General), France#FR#FR00#48.8667#2.33333#-1456928#19;
```

The count carries Paris's location type, reference name, country and ADM1 codes, coordinates and feature ID. The enhanced entry adds `19`, the character offset of `12`. The example requires an installed English NER model and the [prepared geographic reference](../../installation.md#basic-english-setup).

## Behavior

Each entry has ten `#` components: label, quantity, object, location type, full location name, country code, ADM1 code, latitude, longitude and feature ID. Entries end with `;`. Without resolved geography, the type is `0` and the other geographic components are empty.

The matcher accepts digit and cardinal-word quantities with supported event phrases. One mention can emit several labels. Original number spans and rejected candidates are available through `result.mentions` and `result.issues`. No accepted matches produces `""`.

Pass resolved `CountLocation` spans through `locations=`. `analyze_locations(...).count_locations` provides compatible spans; `generate_gkg(text, metadata, Resources(recognizer=ner))` supplies resolved geography automatically unless `count_locations=` is provided. The standalone `analyze_counts(text).to_gkg()` does not run NER or geographic resolution by itself. Object descriptions and location names replace reserved separators and control characters with spaces.

## Options

### Rules

Load a custom rule file with `load_count_rules(path)` or `CountRules.from_json(path)` and pass `rules=` to the standalone extractor. Compose `Resources(count_rules=rules)` for record generation.

The [count-rule schema](../../../src/gdelt_regkg/resources/schemas/count-rules.schema.json) uses `name`, `settings` and `rules`. Only `enabled` rules execute; IDs must be unique.

| Rule kind | Match |
| --- | --- |
| `predicate` | Quantity before an event phrase |
| `active_predicate` | Event phrase before or after the quantity |
| `template` | Literal context containing one `{number}` placeholder |

Settings control object nouns, auxiliaries, context bounds and unsafe-phrase guards. Enabling `reject_time_objects` rejects durations without a casualty object; it is off in the standard profiles.

## Limitations

The 37 labels cover all count labels observed in the statistical inventory, but this does not guarantee detection of their quantities. Grammar, object attachment and duplicate handling are approximations. Each count takes the supplied location nearest its number span, without sentence or grammatical attachment checks; this can assign the wrong event location. Counts can describe historical events; the extractor does not determine when an event occurred.

## Related

[Enhanced counts](enhanced-counts.md) · [Amounts](amounts.md) · [Custom rules](../../guides/resources.md#resource-selection) · [Current agreement](../../evaluation/results.md#agreement-with-gdelt) · [Count inventory](../../../CHANGELOG.md#count-labels)

[Field index](README.md) · [Python API](../python-api.md)
