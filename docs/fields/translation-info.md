# Translation information

`V2.1TRANSLATIONINFO` records the original language and the engine used to translate an article into English. `format_translation_info` formats supplied provenance; local translation can produce that provenance automatically.

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

Local translation requires the `translate` extra, a separately installed PyTorch build, and M2M100 418M weights. Follow the [CPU or CUDA installation commands](../installation.md#non-english-articles); the extra does not install PyTorch. A loaded model can process multiple articles. This example uses already downloaded weights and a CUDA-capable installation.

```python
from gdelt_regkg.fields.translation import M2M100Translator
from gdelt_regkg.fields.translation import translate_text
from gdelt_regkg.translation_cache import CachedTranslator

backend = M2M100Translator.from_model(
    model="facebook/m2m100_418M", device="cuda", allow_download=False, batch_size=4, num_beams=4
)
translator = CachedTranslator(backend, "translations.sqlite")
body = "El museo abrió una nueva exposición sobre instrumentos musicales. Los visitantes pueden escuchar grabaciones y participar en talleres para aprender cómo se producen los diferentes sonidos."

try:
    result = translate_text(body, language="spa", translator=translator, language_check="all")
    print(result.text)
    assert result.source_language == "spa"
    assert result.translated
finally:
    translator.close()
```

```text
The museum opened a new exhibition on musical instruments. Visitors can listen to recordings and participate in workshops to learn how the different sounds are produced.
```

Translation wording depends on the model; no fixed output is promised. CUDA uses FP16; CPU uses FP32. Consecutive sentences are packed and oversized spans split without truncating the body. `batch_size=` controls chunks per model call; `num_beams=` controls decoding. `translate_many(texts, source_language)` batches same-language bodies. Empty or output-limited translations that cannot be recovered raise errors.

Cache keys include engine identity, normalized source language and the original body. Call `close()` when finished. A custom backend exposes `engine` and implements `translate(text, source_language) -> str`.

### Language detection

Missing language labels are detected locally with Lingua. Regional aliases such as `es-ES` are normalized to `spa`; unsupported labels raise an error. `detect_language` returns the detected language independently of translation.

```python
from gdelt_regkg.fields.language import detect_language

body = "The museum opened a new exhibition about musical instruments. Visitors can listen to recordings and join workshops to learn how different sounds are produced."
print(detect_language(body).language)
```

```text
eng
```

The detector samples the beginning, middle and end of long bodies. By default, it returns the best candidate with its `confidence` and `margin`, including for short or uncertain text; the caller decides whether to use it. If the backend finds no candidate, such as for empty or numeric-only text, it raises `LanguageDetectionError`.

Opt into automatic rejection with `LinguaDetector(strict=True)`. Strict checks default to at least 40 alphabetic characters, confidence ≥0.8 and a margin ≥0.2; configure them through `min_letters=`, `min_confidence=` and `min_margin=`. Short or uncertain input then raises `LanguageDetectionError`.

```python
from gdelt_regkg.fields.language import LinguaDetector, detect_language

detector = LinguaDetector(strict=True, min_letters=40, min_confidence=0.8, min_margin=0.2)
result = detect_language(body, detector=detector)
print(result.language, result.confidence, result.margin)
```

Pass that same detector through `translate_text(..., language_detector=detector)` to enforce the checks when detecting a missing source-language label. Without it, automatic translation uses the best candidate and exposes its scores in `result.language_detection`.

| `language_check` | Supplied-label handling |
| --- | --- |
| `"script"` (default) | Check the dominant alphabet; compatible labels remain |
| `"all"` | Also check languages sharing an alphabet |
| `"none"` | Trust the supplied label |

Verification of an already supplied label is conservative by default: it requires confident evidence and Lingua confirms proposed changes with its full models. A supplied custom detector controls its own thresholds. Corrections are exposed in `result.language_detection`. Set `detect_missing_language=False` to require a supplied label. These arguments apply to the explicit translation step.

## Limits

M2M100 does not reproduce GDELT’s translation engine. Translation, mixed-language input and recognition after translation can change field agreement. Translate before computing NER/count-location spans; original-body offsets cannot be reused when the body changes.

## Related

[Complete pipeline](../api-usage.md#complete-pipeline-example) · [Record ID](record-id.md) · [Translation API](../api-usage.md#language-detection-and-translation) · [Current agreement](../README.md#agreement-with-gdelt)
