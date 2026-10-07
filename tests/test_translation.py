import tempfile
import unittest
import warnings
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gdelt_regkg import (
    CachedTranslator,
    EntityMention,
    IncompleteGKGWarning,
    LanguageDetection,
    LanguageDetectionError,
    M2M100Translator,
    NERResult,
    TranslationUnavailableError,
    generate_gkg,
    normalize_language,
    translate_text,
)


class TranslationTests(unittest.TestCase):
    def test_model_load_without_torch_explains_backend_selection(self):
        with patch.dict("sys.modules", {"torch": None, "transformers": None}):
            with self.assertRaisesRegex(TranslationUnavailableError, "CPU/CUDA.*installation.md"):
                M2M100Translator.from_model(allow_download=True)

    def test_english_extraction_without_torch(self):
        text = "Flooding killed 12 people on June 5, 2025."
        with patch.dict("sys.modules", {"torch": None, "transformers": None}):
            record = generate_gkg(
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
        self.assertTrue(all(value is not None for value in record.values()))

    def test_ner_receives_translated_text_and_offsets(self):
        translated = "President Jane Smith visited the White House."
        mentions = tuple(
            EntityMention(name, label, translated.index(name), translated.index(name) + len(name))
            for name, label in (("Jane Smith", "PERSON"), ("White House", "ORG"))
        )
        recognizer = Mock(analyze=Mock(return_value=NERResult(translated, mentions)))
        backend = Mock(engine="Local fixture", translate=Mock(return_value=translated))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            record = generate_gkg(
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
        from gdelt_regkg.fields import format_translation_info

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
            record = generate_gkg(
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

    def test_pipeline_uses_translated_content_and_provenance(self):
        translated = 'Flooding killed 12 people. Jane said "We need help."'
        backend = Mock(engine="Local fixture", translate=Mock(return_value=translated))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            common = dict(
                identifier="https://example.org/article", batch_time="20250615011500", sequence=1
            )
            record = generate_gkg("متن", input_language="Urdu", translator=backend, **common)
            baseline = generate_gkg(translated, **common)
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
            english = generate_gkg(translated, input_language="en", translator=backend, **common)
            self.assertEqual(english["V2.1TRANSLATIONINFO"], "")
            self.assertEqual(english["GKGRECORDID"], baseline["GKGRECORDID"])
            with self.assertRaises(ValueError):
                generate_gkg(
                    "متن",
                    input_language="ur",
                    translator=backend,
                    ner=NERResult("متن", ()),
                    **common,
                )
            with self.assertRaises(ValueError):
                generate_gkg(
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
            backend = Mock(engine="v1", translate=Mock(return_value="Translated body"))
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
        tokenizer, network = Mock(), Mock(device="cpu")
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


if __name__ == "__main__":
    unittest.main()
