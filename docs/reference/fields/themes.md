# Themes

`V1THEMES` stores topic labels matched in English article text. `analyze_themes` uses the locally prepared theme profile, with 519 supported labels in the standard configuration.

## Requirements

Prepare the field's dictionaries using [Build resources](../../guides/resources.md). Models and additional dependencies are needed only for the selected workflow.

## Example

```python
from gdelt_regkg.fields.themes import analyze_themes

text = "Heavy rain caused flooding."

print(analyze_themes(text).to_gkg())
result = analyze_themes(text)
assert result.mentions[0].text == "flooding"
```

```text
CRISISLEX_C06_WATER_SANITATION;NATURAL_DISASTER_FLOODING;
```

## Behavior

Nonempty output contains `CODE;` entries. Each label appears once, in first-match order. Matching uses case-insensitive token phrases. Overlapping phrases and aliases can emit several labels. An unmatched body produces `""`.

`analyze_themes` retains each matched phrase and its original offsets. Reuse its `to_gkg()` and `to_gkg(enhanced=True)` methods for both theme fields.

Prepare dictionaries through [Installation and setup](../../get-started/installation-and-setup.md). Standalone analyzers use `local-resources/` by default. Load another profile once and pass `lexicon=`. Compose `Resources(theme_lexicon=lexicon, resources_dir=path)` for record generation.

## Options

### Rules

Load edited JSON with `load_theme_lexicon(path)` or `ThemeLexicon.from_json(path)`. The [theme-rule schema](https://github.com/octo-gone/gdelt-regkg/blob/master/src/gdelt_regkg/resources/schemas/theme-rules.schema.json) uses `name` and `rules`. Each rule declares a literal `expression`, output `labels`, a unique `id` and a `status`. Only `enabled` rules execute.

| Optional property | Behavior |
| --- | --- |
| `aliases` | Additional phrases producing the same labels |
| `requires_all` | At least one phrase from every group must occur in the document |
| `exclude_any` | Any matching phrase suppresses the rule throughout the document |

Conditions do not change mention offsets. List parent labels explicitly when they should also be emitted.

## Limitations

Phrase rules do not provide automatic inflection, taxonomy expansion or grammatical negation handling. Some rules match topic proxies. The supported vocabulary covers only part of GDELT’s theme inventory, and the standard field deduplicates codes that native rows may repeat.

## Related

[Enhanced themes](enhanced-themes.md) · [Installation and setup](../../get-started/installation-and-setup.md) · [Custom rules](../../guides/resources.md#resource-selection) · [Current agreement](../../evaluation/results.md#results) · [Theme inventory](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md#theme-dictionary)

[GKG field reference](README.md)
