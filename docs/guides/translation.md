# Detect and translate article bodies

Record generation analyzes prepared English text. Detect and translate non-English bodies first, then copy translation provenance into metadata. Install the [language and translation dependencies](../installation.md#non-english-articles) before using these examples.

## Language detection and translation

Language detection requires the `lang` extra and does not load a translation model:

```python
from gdelt_regkg.fields.language import detect_language

body = (
    "El museo abrió una nueva exposición sobre instrumentos musicales. "
    "Los visitantes pueden escuchar grabaciones y participar en talleres "
    "para aprender cómo se producen los diferentes sonidos."
)
detection = detect_language(body)
print(detection.language)
print(detection.confidence)
print(detection.margin)
```

```text
spa
1.0
1.0
```

The language is written in ISO 639-3. Confidence values depend on the input. By default, the detector returns its best candidate even for short or uncertain text. Inspect `confidence` and `margin` before accepting it.

To reject weak evidence, configure strict checks:

```python
from gdelt_regkg.fields.language import LinguaDetector, detect_language

detector = LinguaDetector(
    strict=True, min_letters=40, min_confidence=0.8, min_margin=0.2,
)
detection = detect_language(
    "Les visiteurs peuvent écouter des enregistrements et participer à des ateliers.",
    detector=detector,
)
print(detection.language)
```

```text
fra
```

Strict detection raises `LanguageDetectionError` when a threshold is not met. Empty or numeric-only input raises even with permissive detection. See [language interfaces](../reference/python-api.md#language-detection).

## Translate a body

This example requires a separately installed PyTorch build, the `translate,lang` extras and previously downloaded M2M100 weights:

```python
from gdelt_regkg.fields.translation import M2M100Translator, translate_text

backend = M2M100Translator.from_model(device="cpu", allow_download=False)
result = translate_text(
    "Les autorités ont annoncé de nouvelles mesures pour protéger les habitants.",
    translator=backend,
)
print(result.source_language)
print(result.text)
```

```text
fra
The authorities have announced new measures to protect the residents.
```

Use `allow_download=True` once to explicitly permit downloading model weights. Afterwards use `False` or a local snapshot directory. Model wording can vary. English bodies pass through unchanged. CUDA inference uses FP16; CPU uses FP32. Consecutive sentences are packed and oversized spans are split without truncating the body. `batch_size` controls chunks per model call and `num_beams` controls decoding; empty or output-limited translations that cannot be recovered raise errors.

Omitting `language=` detects a label with Lingua. When the language is known, supply it with `language="fra"`. Regional labels such as `es-ES` normalize to `spa`; unsupported labels fail. Supplied labels use `language_check="script"` by default; `"all"` verifies every supplied label and `"none"` trusts it. Custom translators expose an engine identity and `translate(text, source_language)`.

## Complete pipeline example

This example additionally requires the English NER model and standard resources from [quickstart](../quickstart.md#prerequisites). It saves the exact analyzed bodies alongside the rows so enhanced offsets remain usable.

```python
import json

from gdelt_regkg import RecordMetadata, Resources, generate_gkg, write_gkg
from gdelt_regkg.fields.ner import SpacyNER
from gdelt_regkg.fields.translation import M2M100Translator, translate_text

articles = [{
    "url": "https://example.org/story",
    "batch_time": "20261001091500",
    "language": "fra",
    "text": "Des inondations ont tué 12 personnes à Londres.",
}]
backend = M2M100Translator.from_model(device="cpu", allow_download=False)
resources = Resources(
    resources_dir="local-resources",
    recognizer=SpacyNER.from_model("en_core_web_sm"),
)
rows = []
with open("article-bodies.jsonl", "w", encoding="utf-8") as bodies:
    for sequence, article in enumerate(articles, 1):
        metadata = RecordMetadata(
            identifier=article["url"],
            batch_time=article["batch_time"],
            sequence=sequence,
            sharing_image="",
            related_images=[],
            social_image_embeds=[],
            social_video_embeds=[],
            extras={},
        )
        result = translate_text(
            article["text"], language=article.get("language"), translator=backend,
        )
        record = generate_gkg(
            result.text,
            RecordMetadata.from_translation(result, metadata),
            resources,
            strict=True,
        )
        rows.append(record)
        bodies.write(json.dumps({
            "record_id": record.recordid,
            "original_text": result.original_text,
            "text": result.text,
            "source_language": result.source_language,
        }, ensure_ascii=False) + "\n")
with open("articles.gkg.tsv", "w", encoding="utf-8", newline="") as stream:
    write_gkg(rows, stream)
```

The caller owns corpus iteration, sequence uniqueness and body storage. Missing language labels are detected automatically. `RecordMetadata.from_translation` returns a new metadata object and rejects conflicting provenance. Translated records receive the `T` marker in their IDs; English passthrough adds no translation provenance. Titles, media and identifiers are not translated.

> [!IMPORTANT]
> Enhanced offsets index the analyzed English body, `result.text`. Compute NER and count-location spans after translation and retain that exact body with the output. Offsets into `result.original_text` cannot be reused for translated text.

## Native-language GCAM

By default, GCAM analyzes English `result.text` and emits its word count as `wc`. With a v5 lexicon, also pass `gcam_original_text=result.original_text` to `generate_gkg` for translated bodies. The source language comes from translated metadata; GCAM selects matching native dictionaries and emits `nwc` for the original body. Other fields and enhanced offsets continue to use English text.

Standalone `analyze_gcam` accepts prepared English `text` plus `original_text=` and `original_language=`. Omit original-text inputs for English passthrough. Chinese native scoring requires Jieba through the `build` extra. See [GCAM translation behavior](../reference/fields/gcam.md#translation) and [resource profiles](resources.md#gcam-profiles-and-expansion).

For model reuse, batch translation and persistent caching, see [performance](performance.md).
