# Batch inference and persistent caching

Reuse loaded dictionaries and NLP backends across articles. Install CPU or CUDA dependencies using [installation](../installation.md); device selection does not install a backend or model.

## Reuse resources

Construct `Resources` and load the recognizer outside article loops. Explicit resource objects override directory defaults and can be reused by standalone analyzers. Default compiled profiles are cached by resolved path; reload explicit objects or restart Python after editing a cached profile in place.

## Batch NER

```python
from gdelt_regkg.fields.ner import SpacyNER

texts = ["Flooding affected London.", "Volunteers arrived in Paris."]
recognizer = SpacyNER.from_model("en_core_web_sm")
for text, entities in zip(texts, recognizer.analyze_many(texts, batch_size=32)):
    assert entities.text == text
    print(entities.locations)
```

Supply each result as `ner_result=` to `generate_gkg` for that exact body. Precomputed NER takes precedence over the configured recognizer. See [overrides and precomputed NER](records.md#overrides-and-precomputed-ner).

## Batching and persistent caching

`M2M100Translator.translate_many(texts, source_language)` batches same-language bodies; internal chunking preserves long articles. Its factory defaults to a translation batch size of four.

For repeated translations, wrap a loaded backend with a persistent cache:

```python
from gdelt_regkg.fields.translation import M2M100Translator, translate_text
from gdelt_regkg.translation_cache import CachedTranslator

backend = M2M100Translator.from_model(device="cpu", allow_download=False)
source_body = "Des inondations ont touché plusieurs villes de la région."
another_body = "Les autorités ont annoncé de nouvelles mesures."
with CachedTranslator(backend, "translations.sqlite", timeout=60) as cached:
    translated = translate_text(source_body, language="fra", translator=cached)
    bodies = cached.translate_many([source_body, another_body], "fra")
print(translated.text)
print(bodies)
```

This example requires previously downloaded weights and the translation dependencies. Scalar and batch cache calls use identical language normalization, English passthrough and output validation. Cache keys include a format namespace, engine identity, normalized language and exact input body. The cache trusts its supplied language; use `translate_text` to verify labels before caching.

## Connection and workspace ownership

File-backed translation caches use WAL and configurable SQLite timeouts. Use a context manager or `close()`. Closure is idempotent, discards uncommitted work and does not close the wrapped translator. Successful cache operations commit explicitly.

> [!NOTE]
> Each cache instance owns a thread-affine connection. Create an instance inside each worker, thread or process. Independent translation caches may share a database; concurrent benchmark writers require separate workspaces.

The benchmark owns an exclusive workspace lock and defaults to `OUTPUT/benchmark.sqlite3`. Concurrent benchmark writers cannot share a workspace. `BenchmarkStore(path, timeout=5)` supports context management and `close()` with the same ownership rules. In-memory databases use SQLite's memory journal.

## GPU inference

For translation, select `device="cpu"` or `device="cuda:0"` when loading M2M100. Translation uses PyTorch; CuPy is unnecessary. For NER, call `spacy.require_gpu(0)` before loading the spaCy model, or `spacy.require_cpu()` for explicit CPU execution. Follow [GPU installation and checks](../installation.md#gpu-inference) first.

Benchmark corpus generation accepts `--device cpu`, `cuda` or `auto`, plus `--gpu-id`. The default is CPU. `cuda` requires successful initialization and computation; `auto` can fall back to CPU. Control NER/checkpoint batches with `--batch-size` and `--batch-chars`; a single long article remains intact. See [benchmark checkpoints and memory](benchmarking.md#checkpoints-and-memory).
