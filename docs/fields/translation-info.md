# Translation information

`V2.1TRANSLATIONINFO` records the original language and the engine used to translate an article into English. `format_translation_info` formats supplied provenance; local translation can produce that provenance automatically.

## Example

```python
from gdelt_regkg.fields import format_translation_info

print(format_translation_info("spa", "Example translation engine"))
assert format_translation_info() == ""
```

```text
srclc:spa;eng:Example translation engine
```

## Behavior

Supply both a lowercase three-letter ISO 639-2 code and a nonempty engine citation, or neither. The formatter checks the code’s shape; the translation backend also validates supported languages. Semicolons and control characters in citations become spaces, and whitespace is collapsed.

In `generate_gkg`, `source_language=` and `translation_engine=` format existing provenance and add `T` to the record ID. Alternatively, pass a translator through `translator=` and the source label through `input_language=` to translate before text extraction. Automatic translation supplies provenance; do not also supply it manually.

English text passes through without translation provenance. Titles, authors, identifiers and other supplied metadata retain their original values. Enhanced offsets refer to the English body analyzed; preserve that body with the output.

## Options

### Local translation

Local translation requires a CPU/CUDA PyTorch build and M2M100 418M weights, described in [non-English setup](../installation.md#non-english-articles). A loaded model can process multiple articles. This example uses already downloaded weights and a CUDA-capable installation.

```python
from gdelt_regkg import CachedTranslator, M2M100Translator, translate_text

backend = M2M100Translator.from_model(
    model="facebook/m2m100_418M",
    device="cuda",  # Use "cpu" with a CPU PyTorch build.
    allow_download=False,
    batch_size=4,
    num_beams=4,
)
translator = CachedTranslator(backend, "translations.sqlite")
body = (
    "El museo abrió una nueva exposición sobre instrumentos musicales. "
    "Los visitantes pueden escuchar grabaciones y participar en talleres "
    "para aprender cómo se producen los diferentes sonidos."
)
try:
    result = translate_text(
        body, language="spa", translator=translator, language_check="all"
    )
    print(result.text)
    assert result.source_language == "spa"
    assert result.translated
finally:
    translator.close()
```

Translation wording depends on the model; no fixed output is promised. CUDA uses FP16; CPU uses FP32. Consecutive sentences are packed and oversized spans split without truncating the body. `batch_size=` controls chunks per model call; `num_beams=` controls decoding. `translate_many(texts, source_language)` batches same-language bodies. Empty or output-limited translations that cannot be recovered raise errors.

Cache keys include engine identity, normalized source language and the original body. Call `close()` when finished. A custom backend exposes `engine` and implements `translate(text, source_language) -> str`.

### Language detection

Missing language labels are detected locally with Lingua. Regional aliases such as `es-ES` are normalized to `spa`; unsupported labels raise an error. `detect_language` returns the detected language independently of translation.

```python
from gdelt_regkg import detect_language

body = (
    "The museum opened a new exhibition about musical instruments. "
    "Visitors can listen to recordings and join workshops to learn how "
    "different sounds are produced."
)
print(detect_language(body).language)
```

```text
eng
```

The detector samples at most 6,000 characters from the beginning, middle and end, requires 40 alphabetic characters, and defaults to confidence ≥0.8 with a margin ≥0.2. Short or uncertain input raises `LanguageDetectionError`. Reuse `LinguaDetector(min_confidence=..., min_margin=...)` through `language_detector=` to change thresholds.

| `language_check` | Supplied-label handling |
| --- | --- |
| `"script"` (default) | Check the dominant alphabet; compatible labels remain |
| `"all"` | Also check languages sharing an alphabet |
| `"none"` | Trust the supplied label |

Confident corrections are exposed in `result.language_detection`; Lingua confirms proposed label changes with its full models. Set `detect_missing_language=False` to require a supplied label. These arguments also apply to the generator.

## Limits

M2M100 does not reproduce GDELT’s translation engine. Translation, mixed-language input and recognition after translation can change field agreement. Translate before computing NER/count-location spans; original-body offsets cannot be reused when the body changes.

## Related

[Complete pipeline](../installation.md#complete-pipeline-example) · [Record ID](record-id.md) · [Translation API](../usage.md#language-detection-and-translation) · [Current agreement](../README.md#agreement-with-gdelt)
