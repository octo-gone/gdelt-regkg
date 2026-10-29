# Translation information

`V2.1TRANSLATIONINFO` records the original language and the engine used to translate an article into English. `format_translation_info` formats supplied language and engine values. Local translation can populate these values automatically.

## Requirements

Formatting supplied language and engine values requires only the core package. Automatic detection and translation require the [language backends and model weights](../../guides/translation.md#setup).

## Example

```python
from gdelt_regkg.fields.metadata import format_translation_info

print(format_translation_info("spa", "Example translation engine"))
assert format_translation_info() == ""
```

```text
srclc:spa;eng:Example translation engine
```

## Behavior

Supply both a lowercase three-letter ISO 639-2 code and a nonempty engine citation, or neither. The formatter checks the code’s shape. The translation backend also validates supported languages. Semicolons and control characters in citations become spaces, and whitespace is collapsed.

M2M100 citations contain the repository and a 12-character commit prefix, for example `srclc:fra;eng:facebook/m2m100_418M@55c2e61bbf05`. Local model citations use `<directory-name>@sha256:<12-character-prefix>`. Full revisions and inference settings are available in the translator's `translation_profile`; `cache_identity` identifies the configuration for caching. See [model identity](../../guides/translation.md#model-identity).

Translate first with `translate_text`, then pass `result.text` to the generator and copy the source language and engine using `RecordMetadata.from_translation(result, metadata)`. English input passes through without translation metadata. Translated records receive the `T` record-ID marker.

Enhanced offsets refer to the English body analyzed, `result.text`, rather than `result.original_text`. Preserve that body with the output. Metadata titles, authors and identifiers retain their original values.

## Options

### Local translation

Use `translate_text` with a loaded backend, then populate metadata through `RecordMetadata.from_translation`. English input passes through unchanged. Regional labels such as `es-ES` normalize to `spa`. Unsupported labels fail. A custom backend supplies an engine identity and `translate(text, source_language)`.

Follow [Translation](../../guides/translation.md) for runnable detection, translation and record-generation examples. The [Performance](../../guides/performance.md) guide covers batching and persistent caching.

### Language detection

Missing labels are detected locally with Lingua. Long bodies are sampled at their beginning, middle and end. Detection exposes confidence and margin. Permissive detection returns the best available candidate, while strict detection rejects weak evidence. No candidate raises `LanguageDetectionError` in either mode.

Verification of a supplied label is conservative by default. It requires confident evidence, and Lingua confirms proposed corrections with its full models. Custom detectors control their own thresholds. Corrections are available in `result.language_detection`. Set `detect_missing_language=False` to require a supplied label.

## Limitations

M2M100 does not reproduce GDELT’s translation engine. Translation, mixed-language input and recognition after translation can change field agreement. Translate before computing NER/count-location spans. Original-body offsets cannot be reused when the body changes.

## Related

[Complete pipeline](../../guides/translation.md#complete-pipeline-example) · [Record ID](record-id.md) · [Translation API](../../guides/translation.md#language-detection-and-translation) · [Current agreement](../../evaluation/results.md#results)

[GKG field reference](README.md)
