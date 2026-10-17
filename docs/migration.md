# Migration guide

Version 2.0 uses structured field analyzers, explicit metadata and resource composition. See the [release history](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md#200) for the complete change list.

## Upgrade to 2.0

Replace `extract_*` convenience functions with structured analyzers and explicit `.to_gkg()` serialization. Import analyzers from their owning field modules.

```python
# Standalone fields: replace extract_counts(text).
from gdelt_regkg.fields.counts import analyze_counts

text = "12 people were killed."
cell = analyze_counts(text).to_gkg()
enhanced_cell = analyze_counts(text).to_gkg(enhanced=True)
```

The translation example requires previously downloaded M2M100 weights, the English NER model and prepared resources from [installation](installation.md).

```python
from gdelt_regkg import RecordMetadata, Resources, generate_gkg
from gdelt_regkg.fields.ner import SpacyNER
from gdelt_regkg.fields.translation import M2M100Translator, translate_text

source_body = "Des inondations ont tué 12 personnes à Londres."
backend = M2M100Translator.from_model(device="cpu", allow_download=False)
metadata = RecordMetadata(
    identifier="https://example.org/story",
    batch_time="20261001091500",
    sequence=1,
    sharing_image="",
    related_images=[],
    social_image_embeds=[],
    social_video_embeds=[],
    extras={},
)
resources = Resources(resources_dir="local-resources", recognizer=SpacyNER.from_model())
result = translate_text(source_body, language="fra", translator=backend)
record = generate_gkg(
    result.text,
    RecordMetadata.from_translation(result, metadata),
    resources,
    overrides={"V1THEMES": "CUSTOM;"},
    strict=True,
)
row = record.to_row()
mapping = record.to_mapping()
# Save result.text with this record: enhanced offsets refer to this body.
```

The cache example reuses the backend and source body above:

```python
from gdelt_regkg.translation_cache import CachedTranslator

with CachedTranslator(backend, "translations.sqlite", timeout=60) as cached:
    result = translate_text(source_body, language="fra", translator=cached)
```

See [installation](installation.md) for feature extras and explicit CPU/CUDA setup, [resources](guides/resources.md) for composition, and [performance](guides/performance.md) for batching and connection ownership.
