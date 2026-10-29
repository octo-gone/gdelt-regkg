import hashlib
import json
import os
import tempfile
import unittest
import warnings
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from support import make_record

from gdelt_regkg import IncompleteGKGWarning, OptionalDependencyError
from gdelt_regkg.fields.language import LanguageDetection, LanguageDetectionError
from gdelt_regkg.fields.metadata import format_translation_info
from gdelt_regkg.fields.ner import EntityMention, NERResult
from gdelt_regkg.fields.translation import (
    M2M100Translator,
    TranslationUnavailableError,
    _ModelReference,
    _resolve_model_reference,
    normalize_language,
    translate_text,
)
from gdelt_regkg.translation_cache import CachedTranslator

COMMIT = "55c2e61bbf05dfb8d7abccdc3fae6fc8512fd636"
OTHER_COMMIT = "ae6407352f7f86e328c0f0678d466fc4246e78b3"
REPOSITORY = "facebook/m2m100_418M"
REFERENCE = _ModelReference(REPOSITORY, None, COMMIT, REPOSITORY, "hub_resolve_revision")


def factory_dependencies():
    tokenizer = Mock()
    network = Mock(config=SimpleNamespace())  # Transformers no longer sets _commit_hash.
    network.to.return_value = network
    network.eval.return_value = network
    network.half.return_value = network
    transformers = SimpleNamespace(
        __version__="5.19.0",
        M2M100Tokenizer=Mock(from_pretrained=Mock(return_value=tokenizer)),
        M2M100ForConditionalGeneration=Mock(from_pretrained=Mock(return_value=network)),
    )
    dependencies = {
        "transformers": transformers,
        "torch": SimpleNamespace(__version__="fixture-torch"),
        "sentencepiece": SimpleNamespace(__version__="fixture-sp"),
        "huggingface_hub": SimpleNamespace(__version__="fixture-hub"),
    }
    return dependencies, network


class TranslationTests(unittest.TestCase):
    def test_model_load_without_torch_explains_backend_selection(self):
        with patch.dict("sys.modules", {"torch": None, "transformers": None}):
            with self.assertRaisesRegex(OptionalDependencyError, "PyTorch.*installed separately"):
                M2M100Translator.from_model(allow_download=True)

    def test_english_extraction_without_torch(self):
        text = "Flooding killed 12 people on June 5, 2025."
        with patch.dict("sys.modules", {"torch": None, "transformers": None}):
            record = make_record(
                text,
                identifier="https://example.org/story",
                batch_time="20250605001500",
                sequence=1,
                ner=NERResult(text, ()),
                sharing_image="",
                related_images=[],
                social_image_embeds=[],
                social_video_embeds=[],
                extras={},
                strict=True,
            )
        self.assertTrue(record["V1COUNTS"])
        self.assertTrue(record["V1.5TONE"])
        self.assertTrue(record["V2.1ENHANCEDDATES"])
        self.assertTrue(record["V2GCAM"])
        self.assertEqual(len(record), 27)
        self.assertTrue(all((value is not None for value in record.values())))

    def test_ner_receives_translated_text_and_offsets(self):
        translated = "President Jane Smith visited the White House."
        mentions = tuple(
            (
                EntityMention(
                    name, label, translated.index(name), translated.index(name) + len(name)
                )
                for name, label in (("Jane Smith", "PERSON"), ("White House", "ORG"))
            )
        )
        recognizer = Mock(analyze=Mock(return_value=NERResult(translated, mentions)))
        backend = Mock(engine="Local fixture", translate=Mock(return_value=translated))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            record = make_record(
                "متن",
                input_language="Urdu",
                translator=backend,
                ner=recognizer,
                identifier="https://example.org/story",
                batch_time="20260110001500",
                sequence=1,
            )
        recognizer.analyze.assert_called_once_with(translated)
        self.assertEqual(record["V1PERSONS"], "Jane Smith")
        self.assertEqual(record["V1ORGANIZATIONS"], "White House")
        self.assertEqual(record["V2ENHANCEDPERSONS"], f"Jane Smith,{translated.index('Jane')}")
        self.assertEqual(
            record["V2ENHANCEDORGANIZATIONS"], f"White House,{translated.index('White')}"
        )

    def test_missing_language_detection_and_english_bypass(self):
        backend = Mock(engine="Fixture", translate=Mock(return_value="English translation"))
        detector = Mock(detect=Mock(return_value=LanguageDetection("eng", 0.99, 0.9, "fixture")))
        result = translate_text(
            "An English article", translator=backend, language_detector=detector
        )
        self.assertFalse(result.translated)
        self.assertEqual(result.text, "An English article")
        self.assertEqual(result.language_detection.language, "eng")
        backend.translate.assert_not_called()
        detector.detect.return_value = LanguageDetection("urd", 0.98, 0.9, "fixture")
        result = translate_text(
            "Original", language="  ", translator=backend, language_detector=detector
        )
        backend.translate.assert_called_once_with("Original", "urd")
        self.assertTrue(result.translated)
        detector.detect.reset_mock()
        translate_text(
            "Supplied English", language="en", translator=backend, language_detector=detector
        )
        detector.detect.assert_not_called()
        with self.assertRaises(ValueError):
            translate_text("Original", translator=backend, detect_missing_language=False)
        detector.detect.side_effect = LanguageDetectionError("Uncertain language")
        with self.assertRaises(LanguageDetectionError):
            translate_text("Ambiguous", translator=backend, language_detector=detector)

    def test_engine_separators_are_normalized_without_changing_cache_identity(self):
        engine = "M2M100 facebook/m2m100_418M@local; transformers 4.57.6; chunk384 beam4"
        backend = Mock(engine=engine, translate=Mock(return_value="Flooding killed 12 people."))
        result = translate_text("Original", language="ur", translator=backend)
        expected = engine.replace(";", "")
        self.assertEqual(result.engine, expected)
        self.assertEqual(backend.engine, engine)
        self.assertEqual(format_translation_info("urd", engine), f"srclc:urd;eng:{expected}")
        self.assertEqual(
            format_translation_info("urd", "Engine;\nversion\t1\x00"),
            "srclc:urd;eng:Engine version 1",
        )
        with self.assertRaises(ValueError):
            format_translation_info("urd", ";\n\t")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            record = make_record(
                "Original",
                input_language="ur",
                translator=backend,
                identifier="https://example.org",
                batch_time="20250615011500",
                sequence=1,
            )
        self.assertEqual(record["V2.1TRANSLATIONINFO"], f"srclc:urd;eng:{expected}")
        self.assertEqual(record["GKGRECORDID"], "20250615011500-T1")

    def test_multilingual_normalization(self):
        groups = {
            "urd": ("ur", "UR", "Urdu", "ur_PK", "ur-PK", "urPK", "urdArab", "urd_Arab"),
            "ara": ("AR", "Arabic", "ar-SA", "arb_Arab"),
            "zho": ("zh", "Chinese", "zh-cn", "zh_Hant", "zhHant", "zhoHans"),
            "jpn": ("ja", "JAPANESE", "ja_JP", "jpn"),
            "rus": ("ru", "Russian", "ruRU", "rus"),
            "fra": ("fr", "French", "fre", "fr-FR"),
            "deu": ("de", "German", "ger", "deDE"),
            "eng": ("en", "EN-US", "English", "eng_Latn"),
        }
        for expected, values in groups.items():
            for value in values:
                with self.subTest(value=value):
                    self.assertEqual(normalize_language(value), expected)
        for value in (None, "", "und", "unknown", "enough", "zz", "JapaneseSomething"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_language(value)

    def test_english_bypass_and_output_validation(self):
        backend = Mock(
            engine="Test model", translate=Mock(return_value="Twelve people were killed.")
        )
        result = translate_text("Original body", language="Urdu", translator=backend)
        backend.translate.assert_called_once_with("Original body", "urd")
        self.assertTrue(result.translated)
        self.assertEqual(result.original_text, "Original body")
        english = translate_text("English body", language="EN-us", translator=backend)
        self.assertFalse(english.translated)
        self.assertIsNone(english.engine)
        self.assertEqual(backend.translate.call_count, 1)
        backend.translate.return_value = ""
        with self.assertRaises(ValueError):
            translate_text("Original", language="ur", translator=backend)

    def test_pipeline_uses_translated_content_and_metadata(self):
        translated = 'Flooding killed 12 people. Jane said "We need help."'
        backend = Mock(engine="Local fixture", translate=Mock(return_value=translated))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            common = dict(
                identifier="https://example.org/article", batch_time="20250615011500", sequence=1
            )
            record = make_record("متن", input_language="Urdu", translator=backend, **common)
            baseline = make_record(translated, **common)
            for column in (
                "V1COUNTS",
                "V2.1COUNTS",
                "V1THEMES",
                "V2ENHANCEDTHEMES",
                "V1.5TONE",
                "V2.1QUOTATIONS",
            ):
                self.assertEqual(record[column], baseline[column])
            self.assertEqual(record["GKGRECORDID"], "20250615011500-T1")
            self.assertEqual(record["V2.1TRANSLATIONINFO"], "srclc:urd;eng:Local fixture")
            english = make_record(translated, input_language="en", translator=backend, **common)
            self.assertEqual(english["V2.1TRANSLATIONINFO"], "")
            self.assertEqual(english["GKGRECORDID"], baseline["GKGRECORDID"])
            with self.assertRaises(ValueError):
                make_record(
                    "متن",
                    input_language="ur",
                    translator=backend,
                    ner=NERResult("متن", ()),
                    **common,
                )
            with self.assertRaises(ValueError):
                make_record(
                    "متن",
                    input_language="ur",
                    translator=backend,
                    source_language="urd",
                    translation_engine="Existing",
                    **common,
                )

    def test_cache_normalized_language_engine_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.sqlite"
            backend = Mock(
                spec=["engine", "translate"],
                engine="v1",
                translate=Mock(return_value="Translated body"),
            )
            cache = CachedTranslator(backend, path)
            try:
                self.assertEqual(cache.translate("Original", "Urdu"), "Translated body")
                self.assertEqual(cache.translate("Original", "ur-PK"), "Translated body")
                self.assertEqual(backend.translate.call_count, 1)
            finally:
                cache.close()
            cache = CachedTranslator(backend, path)
            try:
                cache.translate("Original", "urd")
                self.assertEqual(backend.translate.call_count, 1)
            finally:
                cache.close()
            backend.engine = "v2"
            cache = CachedTranslator(backend, path)
            try:
                cache.translate("Original", "urd")
                self.assertEqual(backend.translate.call_count, 2)
            finally:
                cache.close()

    def test_adapter_does_not_truncate_long_input_and_detects_output_limit(self):
        class Inputs(dict):
            def to(self, device):
                return self

        tokenizer = Mock()
        tokenizer.lang_code_to_id = {"ur": 1}
        tokenizer.eos_token_id = 2
        tokenizer.encode.return_value = list(range(9))
        tokenizer.decode.side_effect = lambda ids, **kwargs: " ".join(map(str, ids))
        tokenizer.return_value = Inputs(input_ids=[1])
        tokenizer.get_lang_id.return_value = 5
        network = Mock(device="cpu")
        output = Mock()
        output.tolist.return_value = [4, 2]
        network.generate.return_value = [output]
        backend = M2M100Translator(
            tokenizer, network, engine="fixture", chunk_tokens=4, batch_size=1
        )
        torch = SimpleNamespace(inference_mode=nullcontext)
        with patch.dict("sys.modules", {"torch": torch}):
            backend.translate("Long sentence", "urd")
            self.assertEqual(network.generate.call_count, 3)
            chunks = [
                call.args[0]
                for call in tokenizer.decode.call_args_list
                if call.kwargs.get("skip_special_tokens") and call.args[0] != [4, 2]
            ]
            self.assertEqual(chunks, [list(range(4)), list(range(4, 8)), [8]])
            output.tolist.return_value = [4, 7]
            with self.assertRaisesRegex(ValueError, "output limit"):
                backend.translate("Long sentence", "urd")

    def test_generation_limits_override_inherited_lengths_and_apply_to_retries(self):
        class Inputs(dict):
            def to(self, device):
                return self

        tokenizer = Mock(eos_token_id=2, pad_token_id=0)
        tokenizer.return_value = Inputs(input_ids=[1])
        tokenizer.get_lang_id.return_value = 5
        tokenizer.decode.return_value = "Translated"
        network = Mock(device="cpu", generation_config=SimpleNamespace(max_length=200))
        network.generate.return_value = [Mock(tolist=Mock(return_value=[4, 2]))]
        backend = M2M100Translator(
            tokenizer,
            network,
            engine="fixture",
            num_beams=3,
            max_new_tokens=1023,
            min_new_tokens=0,
        )
        for retry, beams in ((False, 3), (True, 1)):
            with self.subTest(retry=retry):
                self.assertEqual(backend._generate(["Original"], retry=retry), ["Translated"])
                kwargs = network.generate.call_args.kwargs
                self.assertIsNone(kwargs["max_length"])
                self.assertEqual(kwargs["min_length"], 1)
                self.assertEqual(kwargs["max_new_tokens"], 1023)
                self.assertIsNone(kwargs["min_new_tokens"])
                self.assertEqual(kwargs["num_beams"], beams)
        self.assertEqual(network.generation_config.max_length, 200)
        network.generate.return_value = [Mock(tolist=Mock(return_value=[4, 7]))]
        with self.assertRaisesRegex(ValueError, "max_new_tokens=1023"):
            backend._generate(["Original"])

    def test_translation_options_fail_before_loading_models(self):
        invalid = {
            "chunk_tokens": (0, 513, 1.5, True),
            "batch_size": (0, -1, 1.5, True),
            "num_beams": (0, -1, 1.5, True),
            "max_new_tokens": (0, -1, 1.5, True),
            "min_new_tokens": (-1, 769, 1.5, True),
        }
        with patch("gdelt_regkg.fields.translation.require_dependency") as dependency:
            for name, values in invalid.items():
                for value in values:
                    with self.subTest(name=name, value=value):
                        options = {name: value}
                        with self.assertRaisesRegex(ValueError, name):
                            M2M100Translator(Mock(), Mock(), engine="fixture", **options)
                        with self.assertRaisesRegex(ValueError, name):
                            M2M100Translator.from_model(**options)
            dependency.assert_not_called()

    def test_factory_settings_separate_cached_translations(self):
        dependencies, _ = factory_dependencies()
        configurations = [
            {},
            {"max_new_tokens": 1023},
            {"min_new_tokens": 0},
            {"chunk_tokens": 256},
            {"num_beams": 2},
            {"batch_size": 1},
            {"device": "cuda:0"},
            {"device": "cuda:1"},
        ]
        engines = []
        identities = []
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "gdelt_regkg.fields.translation.require_dependency",
                side_effect=lambda name, extra: dependencies[name],
            ),
            patch(
                "gdelt_regkg.fields.translation._resolve_model_reference", return_value=REFERENCE
            ),
        ):
            for options in configurations:
                with self.subTest(options=options):
                    backend = M2M100Translator.from_model(**options)
                    for name, value in options.items():
                        if name != "device":
                            self.assertEqual(getattr(backend, name), value)
                    engines.append(backend.engine)
                    identities.append(backend.cache_identity)
                    backend.translate_many = Mock(return_value=["Translated"])
                    with CachedTranslator(
                        backend, Path(directory) / "translations.sqlite"
                    ) as cache:
                        self.assertEqual(cache.translate("Original", "fra"), "Translated")
                    # Batch size changes scheduling, so it can reuse the default translation.
                    self.assertEqual(
                        backend.translate_many.call_count,
                        0 if "batch_size" in options or options.get("device") == "cuda:1" else 1,
                    )
        self.assertEqual(set(engines), {f"{REPOSITORY}@{COMMIT[:12]}"})
        self.assertEqual(len(set(identities[:5])), 5)
        self.assertEqual(identities[0], identities[5])
        self.assertNotEqual(identities[0], identities[6])
        self.assertEqual(identities[6], identities[7])

    def test_translation_packs_sentences_and_batches_article_chunks(self):
        class Inputs(dict):
            def to(self, device):
                return self

        tokenizer = Mock(eos_token_id=2, pad_token_id=0, lang_code_to_id={"ur": 1})
        tokenizer.encode.side_effect = lambda text, **kwargs: (
            [10, 11] if text == "First." else [12, 13]
        )
        tokenizer.decode.side_effect = lambda ids, **kwargs: (
            "Packed sentence" if ids != [4, 2] else "Translated"
        )
        tokenizer.return_value = Inputs(input_ids=[1])
        network = Mock(device="cpu")
        output = Mock()
        output.tolist.return_value = [4, 2, 0]
        network.generate.return_value = [output, output]
        backend = M2M100Translator(
            tokenizer, network, engine="fixture", chunk_tokens=4, batch_size=2
        )
        with patch.dict("sys.modules", {"torch": SimpleNamespace(inference_mode=nullcontext)}):
            self.assertEqual(
                backend.translate_many(["First. Second.", "First. Second."], "urd"),
                ["Translated", "Translated"],
            )
        self.assertEqual(network.generate.call_count, 1)
        self.assertEqual(tokenizer.call_args.args[0], ["Packed sentence", "Packed sentence"])
        self.assertEqual(tokenizer.call_args.kwargs["padding"], True)

    def test_empty_translation_is_retried(self):
        tokenizer, network = (Mock(), Mock(device="cpu"))
        backend = M2M100Translator(tokenizer, network, engine="fixture")
        backend._generate = Mock(return_value=["Recovered English"])
        self.assertEqual(backend._retry_empty("Original body"), "Recovered English")
        backend._generate.assert_called_once_with(["Original body"], retry=True)
        backend._generate.reset_mock()
        self.assertEqual(backend._retry_empty("2025 / 123"), "2025 / 123")
        backend._generate.assert_not_called()

    def test_cache_batches_misses_and_preserves_duplicate_order(self):
        with tempfile.TemporaryDirectory() as directory:
            backend = Mock(
                spec=["engine", "translate_many"],
                engine="fixture",
                translate_many=Mock(return_value=["First English", "Second English"]),
            )
            cache = CachedTranslator(backend, Path(directory) / "cache.sqlite")
            try:
                self.assertEqual(
                    cache.translate_many(["First", "Second", "First"], "urd"),
                    ["First English", "Second English", "First English"],
                )
                backend.translate_many.assert_called_once_with(["First", "Second"], "urd")
                self.assertEqual(
                    cache.translate_many(["Second", "First"], "urd"),
                    ["Second English", "First English"],
                )
                self.assertEqual(backend.translate_many.call_count, 1)
            finally:
                cache.close()


class RevisionResolutionTests(unittest.TestCase):
    def test_branches_tags_and_default_use_resolved_field_and_context(self):
        # Model a ResolvedRevision whose string value is still a mutable ref.
        class Resolved(str):
            resolved = COMMIT

        resolver = Mock(return_value=Resolved("main"))
        hub = SimpleNamespace(HfApi=Mock(return_value=SimpleNamespace(resolve_revision=resolver)))
        errors = SimpleNamespace(RevisionResolutionError=OSError)
        with patch(
            "gdelt_regkg.fields.translation.require_dependency",
            side_effect=lambda name, extra: errors if name.endswith(".errors") else hub,
        ):
            for revision in (None, "main", "release-tag"):
                for allow_download in (False, True):
                    with self.subTest(revision=revision, allow_download=allow_download):
                        reference = _resolve_model_reference(
                            REPOSITORY,
                            revision=revision,
                            allow_download=allow_download,
                            cache_dir="cache",
                            token=False,
                        )
                        self.assertEqual(reference.resolved_revision, COMMIT)
                        self.assertEqual(reference.requested_revision, revision)
                        resolver.assert_called_with(
                            REPOSITORY,
                            revision=revision,
                            local_files_only=not allow_download,
                            cache_dir="cache",
                            token=False,
                        )

    def test_explicit_commit_needs_no_hub_resolution(self):
        with patch("gdelt_regkg.fields.translation.require_dependency") as dependency:
            reference = _resolve_model_reference(REPOSITORY, revision=OTHER_COMMIT)
        self.assertEqual(reference.resolved_revision, OTHER_COMMIT)
        self.assertEqual(reference.resolution_method, "explicit_commit")
        dependency.assert_not_called()

    def test_config_fallback_selects_requested_snapshot_without_resolving_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "models--facebook--m2m100_418M"
            configs = {}
            for revision, commit in (("main", COMMIT), ("old-tag", OTHER_COMMIT)):
                config = root / "snapshots" / commit / "config.json"
                config.parent.mkdir(parents=True)
                config.write_text("{}", encoding="utf-8")
                configs[revision] = str(config)
            download = Mock(side_effect=lambda *a, **kw: configs[kw["revision"] or "main"])
            hub = SimpleNamespace(
                HfApi=Mock(return_value=SimpleNamespace()), hf_hub_download=download
            )
            with (
                patch(
                    "gdelt_regkg.fields.translation.require_dependency",
                    return_value=hub,
                ),
                patch.object(
                    Path, "resolve", side_effect=AssertionError("must keep snapshot path")
                ),
            ):
                for revision, commit in ((None, COMMIT), ("old-tag", OTHER_COMMIT)):
                    reference = _resolve_model_reference(REPOSITORY, revision=revision)
                    self.assertEqual(reference.resolved_revision, commit)
                    self.assertEqual(reference.resolution_method, "hub_config_snapshot")
                    self.assertTrue(download.call_args.kwargs["local_files_only"])
                download.side_effect = FileNotFoundError("missing offline ref")
                with self.assertRaises(OSError):
                    _resolve_model_reference(REPOSITORY, revision="uncached")

    def test_invalid_or_missing_resolution_fails_without_guessing(self):
        class ResolutionError(Exception):
            pass

        resolver = Mock()
        hub = SimpleNamespace(
            HfApi=Mock(return_value=SimpleNamespace(resolve_revision=resolver)),
            RevisionResolutionError=ResolutionError,
        )
        with patch("gdelt_regkg.fields.translation.require_dependency", return_value=hub):
            for value in ("main", "local", COMMIT[:12], None):
                resolver.return_value = SimpleNamespace(resolved=value)
                with (
                    self.subTest(value=value),
                    self.assertRaisesRegex(OSError, "full model commit"),
                ):
                    _resolve_model_reference(REPOSITORY)
            resolver.side_effect = ResolutionError("missing offline ref")
            with self.assertRaisesRegex(OSError, "Cannot resolve"):
                _resolve_model_reference(REPOSITORY)
            resolver.side_effect = TypeError("programming error")
            with self.assertRaisesRegex(TypeError, "programming error"):
                _resolve_model_reference(REPOSITORY)

    def test_local_content_identity_uses_names_and_bytes_without_path_or_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            references = []
            for name in ("first", "second"):
                root = Path(directory) / name
                root.mkdir()
                for filename, content in {
                    "config.json": "{}",
                    "generation_config.json": "{}",
                    "pytorch_model.bin.index.json": '{"weight_map": {"a": "shard.bin"}}',
                    "shard.bin": "fixture weights",
                    "sentencepiece.bpe.model": "fixture tokenizer",
                }.items():
                    path = root / filename
                    path.write_text(content, encoding="utf-8")
                    os.utime(path, (100 if name == "first" else 200,) * 2)
                references.append(_resolve_model_reference(root))
            self.assertEqual(references[0].resolved_revision, references[1].resolved_revision)
            self.assertEqual(references[0].identity_kind, "local_sha256")
            root = Path(directory) / "second"
            for filename in ("shard.bin", "sentencepiece.bpe.model", "config.json"):
                with self.subTest(filename=filename):
                    path = root / filename
                    original = path.read_bytes()
                    path.write_bytes(b"changed")
                    self.assertNotEqual(
                        references[0].resolved_revision,
                        _resolve_model_reference(root).resolved_revision,
                    )
                    path.write_bytes(original)
            (root / "shard.bin").rename(root / "other-shard.bin")
            self.assertNotEqual(
                references[0].resolved_revision, _resolve_model_reference(root).resolved_revision
            )


class TranslationIdentityTests(unittest.TestCase):
    def setUp(self):
        self.dependencies, self.network = factory_dependencies()
        dependency = patch(
            "gdelt_regkg.fields.translation.require_dependency",
            side_effect=lambda name, extra: self.dependencies[name],
        )
        dependency.start()
        self.addCleanup(dependency.stop)

    def factory(self, reference=REFERENCE, **options):
        with patch(
            "gdelt_regkg.fields.translation._resolve_model_reference", return_value=reference
        ):
            return M2M100Translator.from_model(**options)

    def test_factory_pins_both_loaders_and_exports_short_citation(self):
        backend = self.factory(cache_dir="cache", token=False)
        for loader in (
            self.dependencies["transformers"].M2M100Tokenizer,
            self.dependencies["transformers"].M2M100ForConditionalGeneration,
        ):
            loader.from_pretrained.assert_called_once_with(
                REPOSITORY, local_files_only=True, revision=COMMIT, cache_dir="cache", token=False
            )
        self.assertEqual(backend.engine, f"{REPOSITORY}@{COMMIT[:12]}")
        self.assertIn(COMMIT, backend.cache_identity)
        profile = backend.translation_profile
        self.assertEqual(profile["model"]["resolved_revision"], COMMIT)
        self.assertEqual(profile["tokenizer"]["resolved_revision"], COMMIT)
        self.assertEqual(profile["revision_resolution"], "hub_resolve_revision")
        self.assertIsNone(profile["requested_revision"])
        self.assertIn("torch", profile["dependencies"])
        json.dumps(profile)
        backend.translate = Mock(return_value="English body")
        result = translate_text("Original", language="fr", translator=backend)
        self.assertEqual(result.engine, backend.engine)
        self.assertEqual(
            format_translation_info(result.source_language, result.engine),
            f"srclc:fra;eng:{REPOSITORY}@{COMMIT[:12]}",
        )
        with CachedTranslator(backend, ":memory:") as cached:
            self.assertEqual(cached.engine, backend.engine)
            self.assertEqual(cached.cache_identity, backend.cache_identity)
            self.assertIs(cached.translation_profile, profile)
            cached.translator.batch_size = 1
            self.assertEqual(backend.batch_size, 1)

    def test_default_offline_factory_resolves_once_before_both_loads(self):
        class Resolved(str):
            resolved = COMMIT

        events = []
        resolver = Mock(side_effect=lambda *a, **kw: events.append("resolve") or Resolved("main"))
        self.dependencies["huggingface_hub"].HfApi = Mock(
            return_value=SimpleNamespace(resolve_revision=resolver)
        )
        self.dependencies["huggingface_hub.errors"] = SimpleNamespace(
            RevisionResolutionError=OSError
        )
        transformers = self.dependencies["transformers"]
        tokenizer = transformers.M2M100Tokenizer.from_pretrained.return_value
        transformers.M2M100Tokenizer.from_pretrained.side_effect = (
            lambda *a, **kw: events.append("tokenizer") or tokenizer
        )
        transformers.M2M100ForConditionalGeneration.from_pretrained.side_effect = (
            lambda *a, **kw: events.append("model") or self.network
        )
        backend = M2M100Translator.from_model()
        self.assertEqual(events, ["resolve", "tokenizer", "model"])
        resolver.assert_called_once_with(
            REPOSITORY, revision=None, local_files_only=True, cache_dir=None, token=None
        )
        for loader in (
            transformers.M2M100Tokenizer,
            transformers.M2M100ForConditionalGeneration,
        ):
            self.assertEqual(loader.from_pretrained.call_args.kwargs["revision"], COMMIT)
        self.assertEqual(backend.translation_profile["model"]["resolved_revision"], COMMIT)

    def test_hub_snapshot_and_repository_share_full_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "models--facebook--m2m100_418M" / "snapshots" / COMMIT
            snapshot.mkdir(parents=True)
            reference = _resolve_model_reference(snapshot)
            self.assertEqual(reference.model_identifier, REPOSITORY)
            self.assertEqual(reference.resolved_revision, COMMIT)
            snapshot_backend = self.factory(reference)
            repository_backend = self.factory()
            self.assertEqual(snapshot_backend.cache_identity, repository_backend.cache_identity)
            self.assertEqual(snapshot_backend.engine, repository_backend.engine)

    def test_local_names_and_runtime_versions_are_provenance_not_cache_identity(self):
        identity = "a" * 64
        first = _ModelReference("first", None, identity, "unused", "manifest", "local_sha256")
        second = _ModelReference("second", None, identity, "unused", "manifest", "local_sha256")
        backend = self.factory(first)
        self.dependencies["torch"].__version__ = "another-runtime"
        other = self.factory(second)
        self.assertEqual(backend.engine, "first@sha256:" + identity[:12])
        self.assertEqual(backend.cache_identity, other.cache_identity)
        self.assertNotIn("unused", json.dumps(backend.translation_profile))
        self.assertNotEqual(backend.translation_profile, other.translation_profile)

    def test_model_tokenizer_and_transformers_identity_separate_results(self):
        backend = self.factory()
        different = self.factory(
            _ModelReference(REPOSITORY, "old", OTHER_COMMIT, REPOSITORY, "explicit_commit")
        )
        self.assertNotEqual(backend.cache_identity, different.cache_identity)
        self.dependencies["transformers"].__version__ = "another-transformers"
        self.assertNotEqual(backend.cache_identity, self.factory().cache_identity)

    def test_factory_missing_revision_preserves_helpful_error_without_loading(self):
        with patch(
            "gdelt_regkg.fields.translation._resolve_model_reference",
            side_effect=OSError("missing revision"),
        ):
            with self.assertRaisesRegex(TranslationUnavailableError, "allow_download=True"):
                M2M100Translator.from_model()
        self.dependencies["transformers"].M2M100Tokenizer.from_pretrained.assert_not_called()

    def test_factory_cache_ignores_engine_keys_and_preserves_their_rows(self):
        backend = self.factory()
        backend.translate_many = Mock(return_value=["New inference"])
        prefix = f"M2M100 {REPOSITORY}@{COMMIT}; transformers 5.19.0; chunk384 beam4 "
        labels = [
            prefix + "new1-768 packed-v2 fp32",
            prefix + "packed-v2 fp32",
            prefix.replace(COMMIT, "local") + "new1-768 packed-v2 fp32",
        ]
        for label in labels:
            with self.subTest(label=label), CachedTranslator(backend, ":memory:") as cache:
                key = hashlib.sha256(
                    ("translation-v2\0" + label + "\0fra\0Original").encode("utf-8")
                ).hexdigest()
                cache.connection.execute(
                    "INSERT INTO translations VALUES (?, ?)", (key, "Previous result")
                )
                cache.connection.commit()
                self.assertEqual(cache.translate("Original", "fra"), "New inference")
                self.assertEqual(
                    cache.connection.execute(
                        "SELECT body FROM translations WHERE key = ?", (key,)
                    ).fetchone(),
                    ("Previous result",),
                )
        self.assertEqual(backend.translate_many.call_count, len(labels))

    def test_display_changes_do_not_invalidate_cache_and_invalid_identities_fail(self):
        backend = Mock(
            spec=["engine", "translate", "cache_identity"],
            engine="display one",
            cache_identity="full configuration",
            translate=Mock(return_value="English"),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.sqlite"
            with CachedTranslator(backend, path) as cache:
                self.assertEqual(cache.translate("Original", "fr"), "English")
            backend.engine = "display two"
            with CachedTranslator(backend, path) as cache:
                self.assertEqual(cache.engine, "display two")
                self.assertEqual(cache.translate("Original", "fra"), "English")
            self.assertEqual(backend.translate.call_count, 1)
        for invalid in ("", " ", 1, False, Mock()):
            with self.subTest(invalid=invalid):
                backend.cache_identity = invalid
                with self.assertRaisesRegex(ValueError, "cache_identity"):
                    CachedTranslator(backend, ":memory:")
                with self.assertRaisesRegex(ValueError, "cache_identity"):
                    M2M100Translator(Mock(), Mock(), engine="citation", cache_identity=invalid)
        direct = M2M100Translator(Mock(), Mock(), engine="old identity")
        self.assertEqual(direct.cache_identity, "old identity")
        self.assertIsNone(direct.translation_profile)
        with CachedTranslator(direct, ":memory:") as cache:
            self.assertEqual(cache.cache_identity, "old identity")


if __name__ == "__main__":
    unittest.main()
