import importlib.util
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gdelt_regkg import LanguageDetection, LanguageDetectionError, LinguaDetector, detect_language
from gdelt_regkg.language import script_mismatch, verify_language


class LanguageTests(unittest.TestCase):
    def test_proposed_corrections_require_confirmation(self):
        text = (
            "The government announced new measures to improve public transport throughout the city."
        )
        detector, _ = self.detector()
        proposed = LanguageDetection("swe", 1, 1, "lingua/low-accuracy")
        confirmed = LanguageDetection("eng", 0.99, 0.98, "lingua/high-accuracy-confirmation")
        with (
            patch.object(detector, "detect", return_value=proposed),
            patch.object(detector, "confirm", return_value=confirmed) as confirm,
        ):
            self.assertEqual(
                verify_language(text, "eng", check="all", detector=detector), confirmed
            )
            confirm.assert_called_once_with(text, "eng", "swe")
        with (
            patch.object(detector, "detect", return_value=proposed),
            patch.object(detector, "confirm", side_effect=LanguageDetectionError("Uncertain")),
        ):
            self.assertIsNone(verify_language(text, "eng", check="all", detector=detector))

    @unittest.skipUnless(
        importlib.util.find_spec("lingua"), "Optional Lingua dependency not installed"
    )
    def test_full_confirmation_preserves_english_and_accepts_real_corrections(self):
        detector = LinguaDetector()
        english = "On AirGordie’s Midday Gossip - Lakeland Police to bring banned Cop TrainingBy Gordie DanielsJune 17, 2025 at 7:51 am EDT\nGordie’s Midday Gossip - Tampa is a staycation destinationBy Gordie DanielsJune 17, 2025 at 6:43 am EDT"
        self.assertEqual(
            verify_language(english, "eng", check="all", detector=detector).language, "eng"
        )
        self.assertEqual(detector.confirm(english, "eng", "dan").language, "eng")
        spanish = "El gobierno anunció nuevas medidas para mejorar el transporte público en toda la ciudad. Los funcionarios explicaron que los cambios ayudarán a los vecinos a viajar con seguridad y llegar a sus trabajos a tiempo."
        arabic = "أعلنت الحكومة عن إجراءات جديدة لتحسين النقل العام في المدينة ومساعدة السكان على الوصول إلى أماكن عملهم بأمان."
        self.assertEqual(
            verify_language(spanish, "eng", check="all", detector=detector).language, "spa"
        )
        self.assertEqual(verify_language(arabic, "eng", detector=detector).language, "ara")

    def test_script_conflicts_and_same_alphabet_verification(self):
        arabic = "أعلنت الحكومة عن إجراءات جديدة لتحسين النقل العام في المدينة ومساعدة السكان على الوصول إلى أماكن عملهم بأمان."
        self.assertTrue(script_mismatch(arabic, "eng"))
        self.assertFalse(script_mismatch(arabic, "ara"))
        english = (
            "The government announced new measures to improve public transport throughout the city."
        )
        self.assertTrue(script_mismatch(english, "ara"))
        detector = Mock(detect=Mock(return_value=LanguageDetection("ara", 1, 1, "fixture")))
        self.assertEqual(verify_language(arabic, "eng", detector=detector).language, "ara")
        detector.detect.reset_mock()
        self.assertIsNone(verify_language(english, "eng", detector=detector))
        detector.detect.assert_not_called()
        verify_language(english, "eng", check="all", detector=detector)
        detector.detect.assert_called_once()
        detector.detect.side_effect = LanguageDetectionError("Uncertain")
        self.assertIsNone(verify_language(english, "eng", check="all", detector=detector))
        with self.assertRaises(LanguageDetectionError):
            verify_language(arabic, "eng", detector=detector)

    def detector(self, confidence=0.99, second=0.01):
        builder = Mock()
        builder.with_low_accuracy_mode.return_value = builder
        backend = builder.build.return_value
        backend.compute_language_confidence_values.return_value = [
            SimpleNamespace(
                language=SimpleNamespace(iso_code_639_3=SimpleNamespace(name="ENG")),
                value=confidence,
            ),
            SimpleNamespace(value=second),
        ]
        with patch.dict(
            "sys.modules",
            {
                "lingua": SimpleNamespace(
                    LanguageDetectorBuilder=Mock(
                        from_all_spoken_languages=Mock(return_value=builder)
                    )
                )
            },
        ):
            detector = LinguaDetector()
        return detector, backend

    def test_confidence_margin_short_text_and_bounded_sample(self):
        detector, backend = self.detector()
        result = detect_language(
            "This is a sufficiently long English article about the latest local news.",
            detector=detector,
        )
        self.assertEqual(result.language, "eng")
        self.assertAlmostEqual(result.margin, 0.98)
        for text in ("", "123456789", "Hello"):
            with self.assertRaises(LanguageDetectionError):
                detect_language(text, detector=detector)
        body = "start " * 2000 + "middle " * 2000 + "end " * 2000
        detect_language(body, detector=detector)
        sample = backend.compute_language_confidence_values.call_args.args[0]
        self.assertLessEqual(len(sample), 6002)
        self.assertIn("start", sample)
        self.assertIn("middle", sample)
        self.assertIn("end", sample)
        for confidence, second in ((0.6, 0.2), (0.85, 0.75)):
            detector, _ = self.detector(confidence, second)
            with self.assertRaises(LanguageDetectionError):
                detector.detect(
                    "A sufficiently long English article with enough alphabetic characters."
                )

    @unittest.skipUnless(
        importlib.util.find_spec("lingua"), "Optional Lingua dependency not installed"
    )
    def test_local_detector_recognizes_english_and_urdu(self):
        detector = LinguaDetector()
        texts = {
            "eng": "The government announced new measures to improve public transport across the city. Officials said the changes would help residents travel safely and reach their workplaces on time.",
            "urd": "حکومت نے شہر میں عوامی نقل و حمل کو بہتر بنانے کے لیے نئے اقدامات کا اعلان کیا ہے۔ حکام کا کہنا ہے کہ ان تبدیلیوں سے شہریوں کو محفوظ سفر کرنے اور وقت پر اپنے کام کی جگہوں تک پہنچنے میں مدد ملے گی۔",
        }
        for language, text in texts.items():
            with self.subTest(language=language):
                self.assertEqual(detector.detect(text).language, language)
