import importlib.util
import unittest
import warnings
from unittest.mock import Mock, patch

from gdelt_regkg import (
    EntityMention,
    IncompleteGKGWarning,
    NERResult,
    NERUnavailableError,
    SpacyNER,
    analyze_entities,
    generate_gkg,
)
from gdelt_regkg.fields import (
    extract_enhanced_organizations,
    extract_enhanced_persons,
    extract_location_mentions,
    extract_organizations,
    extract_persons,
)


class NERTests(unittest.TestCase):
    def sample(self):
        text = "Jane Doe met Acme in Paris. Jane Doe returned to Acme."
        mentions = []
        for name, label in (("Jane Doe", "PERSON"), ("Acme", "ORG"), ("Paris", "LOCATION")):
            start = text.find(name)
            while start >= 0:
                mentions.append(EntityMention(name, label, start, start + len(name)))
                start = text.find(name, start + len(name))
        return NERResult(text, tuple(reversed(mentions)), "fixture")

    def record(self, text, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            return generate_gkg(
                text,
                identifier="https://example.org/story",
                published_at=None,
                batch_time="20261002120000",
                sequence=1,
                **kwargs,
            )

    def test_legacy_names_and_repeated_enhanced_mentions(self):
        result = self.sample()
        self.assertEqual(result.to_gkg("PERSON"), "Jane Doe")
        self.assertEqual(result.to_gkg("PERSON", enhanced=True), "Jane Doe,0;Jane Doe,28")
        self.assertEqual(result.to_gkg("ORG"), "Acme")
        self.assertEqual(result.to_gkg("ORG", enhanced=True), "Acme,13;Acme,49")
        self.assertEqual([(m.text, m.start, m.end) for m in result.locations], [("Paris", 21, 26)])
        with self.assertRaises(NotImplementedError):
            result.to_gkg("LOCATION")

    def test_independent_functions_and_supplied_mentions(self):
        result = self.sample()
        recognizer = Mock(analyze=Mock(return_value=result))
        for function, expected in (
            (extract_persons, "Jane Doe"),
            (extract_enhanced_persons, "Jane Doe,0;Jane Doe,28"),
            (extract_organizations, "Acme"),
            (extract_enhanced_organizations, "Acme,13;Acme,49"),
        ):
            self.assertEqual(function(result.text, recognizer=recognizer), expected)
        self.assertEqual(
            extract_location_mentions(result.text, recognizer=recognizer), result.locations
        )
        supplied = analyze_entities(result.text, mentions=iter(result.mentions))
        self.assertEqual(supplied.mentions, result.mentions)
        with self.assertRaises(ValueError):
            analyze_entities(result.text, recognizer=recognizer, mentions=[])

    def test_unicode_offsets_and_whitespace_normalization(self):
        text = "\U0001f600 Zoë\nSmith works at R&D, Inc."
        person = "Zoë\nSmith"
        org = "R&D, Inc."
        result = analyze_entities(
            text,
            mentions=[
                EntityMention(
                    person, "PERSON", text.index(person), text.index(person) + len(person)
                ),
                EntityMention(org, "ORG", text.index(org), len(text)),
            ],
        )
        self.assertEqual(result.to_gkg("PERSON", enhanced=True), "Zoë Smith,2")
        self.assertEqual(result.to_gkg("ORG", enhanced=True), f"R&D Inc.,{text.index(org)}")
        self.assertEqual(analyze_entities("", mentions=[]).to_gkg("PERSON"), "")

    def test_invalid_offsets_and_backend_results(self):
        for start, end in ((-1, 2), (True, 2), (0, 0)):
            with self.assertRaises(ValueError):
                EntityMention("Jane", "PERSON", start, end)
        with self.assertRaises(ValueError):
            NERResult("Jane", (EntityMention("John", "PERSON", 0, 4),))
        with self.assertRaises(ValueError):
            NERResult("Jane", (EntityMention("Jane", "PERSON", 0, 8),))
        with self.assertRaises(ValueError):
            analyze_entities(
                "Jane", recognizer=Mock(analyze=Mock(return_value=NERResult("John", ())))
            )
        result = analyze_entities("A;B", mentions=[EntityMention("A;B", "ORG", 0, 3)])
        self.assertEqual(result.to_gkg("ORG"), "A B")
        self.assertEqual(result.to_gkg("ORG", enhanced=True), "A B,0")

    def test_pipeline_analyzes_once_and_preserves_overrides(self):
        result = self.sample()
        recognizer = Mock(analyze=Mock(return_value=result))
        record = self.record(result.text, ner=recognizer, field_values={"V1PERSONS": "Override"})
        recognizer.analyze.assert_called_once_with(result.text)
        self.assertEqual(record["V1PERSONS"], "Override")
        self.assertEqual(record["V2ENHANCEDPERSONS"], "Jane Doe,0;Jane Doe,28")
        self.assertEqual(record["V1ORGANIZATIONS"], "Acme")
        self.assertIn("#FR#", record["V1LOCATIONS"])
        self.assertEqual(len(record["V2ENHANCEDLOCATIONS"].split("#")), 9)
        overrides = {
            column: ""
            for column in (
                "V1PERSONS",
                "V2ENHANCEDPERSONS",
                "V1ORGANIZATIONS",
                "V2ENHANCEDORGANIZATIONS",
                "V1LOCATIONS",
                "V2ENHANCEDLOCATIONS",
                "V2.1ALLNAMES",
            )
        }
        recognizer.analyze.reset_mock()
        self.record(result.text, ner=recognizer, field_values=overrides)
        recognizer.analyze.assert_not_called()

    def test_pipeline_accepts_precomputed_result_and_propagates_failures(self):
        result = self.sample()
        self.assertEqual(self.record(result.text, ner=result)["V1PERSONS"], "Jane Doe")
        self.assertIsNone(self.record(result.text)["V1PERSONS"])
        with self.assertRaises(ValueError):
            self.record("Other text", ner=result)
        with self.assertRaisesRegex(RuntimeError, "model failed"):
            self.record(
                result.text, ner=Mock(analyze=Mock(side_effect=RuntimeError("model failed")))
            )

    def test_optional_backend_reports_missing_dependency(self):
        with patch.dict("sys.modules", {"spacy": None}):
            with self.assertRaises(NERUnavailableError):
                SpacyNER.from_model()

    def test_spacy_filters_prose_spans_and_trims_website_suffix(self):
        text = "Toyota Motor publishing website. " + " ".join(["Navigation"] * 15)
        end = text.index(".")
        start = end + 2
        first = text[:end]
        second = text[start:]
        entities = [
            Mock(text=first, label_="ORG", start_char=0, end_char=end),
            Mock(text=second, label_="ORG", start_char=start, end_char=len(text)),
        ]
        nlp = Mock(pipe_names=["ner"], meta={"lang": "en", "name": "fixture", "version": "1"})
        nlp.return_value = Mock(text=text, ents=entities)
        result = SpacyNER(nlp).analyze(text)
        self.assertEqual([m.text for m in result.organizations], ["Toyota Motor"])
        self.assertEqual(result.organizations[0].end, 12)
        self.assertEqual(result.to_gkg("ORG", enhanced=True), "Toyota Motor,0")
        self.assertEqual(len(SpacyNER(nlp, filter_spans=False).analyze(text).mentions), 2)

    @unittest.skipUnless(
        importlib.util.find_spec("spacy"), "optional spaCy dependency not installed"
    )
    def test_spacy_adapter_maps_labels_and_preserves_offsets(self):
        import spacy

        nlp = spacy.blank("en")
        ruler = nlp.add_pipe("entity_ruler")
        ruler.add_patterns(
            [
                {"label": label, "pattern": name}
                for label, name in (
                    ("PERSON", "Jane Doe"),
                    ("ORG", "Acme"),
                    ("GPE", "Paris"),
                    ("LOC", "Alps"),
                    ("FAC", "Central Station"),
                    ("PRODUCT", "Widget"),
                )
            ]
        )
        result = analyze_entities(
            "Jane Doe met Acme in Paris near the Alps and Central Station. Widget.",
            recognizer=SpacyNER(nlp),
        )
        self.assertEqual([m.text for m in result.locations], ["Paris", "Alps", "Central Station"])
        self.assertEqual([m.source_label for m in result.locations], ["GPE", "LOC", "FAC"])
        self.assertEqual(len(result.mentions), 5)
        self.assertEqual(result.persons[0].start, 0)
        with self.assertRaises(ValueError):
            SpacyNER(spacy.blank("en"))
        with patch("spacy.load", side_effect=OSError("not installed")):
            with self.assertRaises(NERUnavailableError):
                SpacyNER.from_model("missing")
