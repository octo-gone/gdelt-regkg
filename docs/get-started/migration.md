# Migration

Version 2.0 uses structured field analyzers, explicit metadata and resource composition. See the [release history](https://github.com/octo-gone/gdelt-regkg/blob/master/CHANGELOG.md#200) for the complete change list.

## Upgrade to 2.0

`generate_gkg` accepts article text, `RecordMetadata` and `Resources`, and returns an immutable `GKGRecord` with typed attributes. This changes are required:

- Replace `ExtractionConfig` with `Resources`, supplying dictionaries, rules, gazetteers and recognizers through that object.
- Move identity, timestamps, source, media and extra metadata into `RecordMetadata`.
- Rename `field_values=` to `overrides=`.
- Move translation out of `generate_gkg`.

Replace `extract_*` calls with structured analyzers imported from their field modules:

```python
from gdelt_regkg.fields.counts import analyze_counts

result = analyze_counts("12 people were killed.")
cell = result.to_gkg()
enhanced_cell = result.to_gkg(enhanced=True)
```

For translation use `translate_text` and `RecordMetadata.from_translation` for building translated record metadata.

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
    strict=True,
)
```

Other changes:

- Pass precomputed recognition through `ner_result=`. Its spans must describe the exact analyzed text.
- Update exception handling: extractor failures propagate; missing feature dependencies raise `OptionalDependencyError`.
- Library build and prediction workflows use `BuildOptions` and `PredictionOptions`.

See [Installation and setup](installation-and-setup.md) for feature extras and explicit CPU/CUDA setup, [Build resources](../guides/resources.md) for composition, and [Performance](../guides/performance.md) for batching and connection ownership.
