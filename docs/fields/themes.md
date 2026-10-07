# Themes

`V1THEMES` stores topic labels matched in English article text. `extract_themes` uses the locally prepared theme profile, with 519 supported labels in the standard configuration.

## Example

```python
from gdelt_regkg import analyze_themes
from gdelt_regkg.fields import extract_themes

text = 'Heavy rain caused flooding.'
print(extract_themes(text))
result = analyze_themes(text)
assert result.mentions[0].text == "flooding"
```

```text
CRISISLEX_C06_WATER_SANITATION;NATURAL_DISASTER_FLOODING;
```

## Behavior

Nonempty output contains `CODE;` entries. Each label appears once, in first-match order. Matching uses case-insensitive token phrases; overlapping phrases and aliases can emit several labels. An unmatched body produces `""`.

`analyze_themes` retains each matched phrase and its original offsets. Reuse its `to_gkg()` and `to_gkg(enhanced=True)` methods for both theme fields.

Prepare dictionaries through [Installation and setup](../installation.md). Standalone analyzers use `local-resources/` by default; load another profile once and pass `lexicon=`. The generator accepts `theme_lexicon=` and `resources_dir=`.

## Options

### Rules

Load edited JSON with `load_theme_lexicon(path)` or `ThemeLexicon.from_json(path)`. The [theme-rule schema](../../src/gdelt_regkg/resources/schemas/theme-rules.schema.json) uses `name` and `rules`. Each rule declares a literal `expression`, output `labels`, a unique `id` and a `status`; only `enabled` rules execute.

| Optional property | Behavior |
| --- | --- |
| `aliases` | Additional phrases producing the same labels |
| `requires_all` | At least one phrase from every group must occur in the document |
| `exclude_any` | Any matching phrase suppresses the rule throughout the document |

Conditions do not change mention offsets. List parent labels explicitly when they should also be emitted.

## Limits

Phrase rules do not provide automatic inflection, taxonomy expansion or grammatical negation handling. Some rules match topic proxies. The supported vocabulary covers only part of GDELT’s theme inventory, and the standard field deduplicates codes that native rows may repeat.

## Related

[Enhanced themes](enhanced-themes.md) · [Installation and setup](../installation.md) · [Custom rules](../usage.md#custom-resources) · [Current agreement](../README.md#agreement-with-gdelt) · [Theme inventory](../../CHANGELOG.md#theme-dictionary)
