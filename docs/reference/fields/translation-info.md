# Translation information

`V2.1TRANSLATIONINFO` records the original language and the engine used to translate an article into English. `format_translation_info` formats supplied provenance; local translation can produce that provenance automatically.

## Requirements

Formatting supplied provenance requires only the core package. Automatic detection and translation require the [language backends and model weights](../../installation.md#non-english-articles).

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

Supply both a lowercase three-letter ISO 639-2 code and a nonempty engine citation, or neither. The formatter checks the code’s shape; the translation backend also validates supported languages. Semicolons and control characters in citations become spaces, and whitespace is collapsed.

Translate first with `translate_text`, then pass `result.text` to the generator and copy provenance using `RecordMetadata.from_translation(result, metadata)`. English passthrough adds no provenance. Non-English provenance retains the `T` record-ID marker.

Enhanced offsets refer to the English body analyzed, `result.text`, rather than `result.original_text`. Preserve that body with the output; metadata titles, authors and identifiers retain their original values.

## Options

### Local translation

Use `translate_text` with a loaded backend, then copy provenance through `RecordMetadata.from_translation`. English input passes through unchanged. Regional labels such as `es-ES` normalize to `spa`; unsupported labels fail. A custom backend supplies an engine identity and `translate(text, source_language)`.

Follow the [translation guide](../../guides/translation.md) for runnable detection, translation and record-generation examples. The [Python reference](../python-api.md#translation) lists label-verification and backend options; [performance](../../guides/performance.md) covers batching and persistent caching.

### Language detection

Missing labels are detected locally with Lingua. Long bodies are sampled at their beginning, middle and end. Detection exposes confidence and margin; permissive detection returns the best available candidate, while strict detection rejects weak evidence. No candidate raises `LanguageDetectionError` in either mode.

Verification of a supplied label is conservative by default. It requires confident evidence, and Lingua confirms proposed corrections with its full models. Custom detectors control their own thresholds; corrections are available in `result.language_detection`. Set `detect_missing_language=False` to require a supplied label. See [language detection](../python-api.md#language-detection) and the [translation options](../python-api.md#translation).

## Limitations

M2M100 does not reproduce GDELT’s translation engine. Translation, mixed-language input and recognition after translation can change field agreement. Translate before computing NER/count-location spans; original-body offsets cannot be reused when the body changes.

## Related

[Complete pipeline](../../guides/translation.md#complete-pipeline-example) · [Record ID](record-id.md) · [Translation API](../../guides/translation.md#language-detection-and-translation) · [Current agreement](../../evaluation/results.md#agreement-with-gdelt)

[Field index](README.md) · [Python API](../python-api.md)
