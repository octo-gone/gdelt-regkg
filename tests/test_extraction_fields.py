import importlib.util
import unittest
import warnings
from decimal import Decimal
from unittest.mock import Mock

from gdelt_regkg import (
    EntityMention,
    Gazetteer,
    GCAMLexicon,
    IncompleteGKGWarning,
    NameMention,
    NERResult,
    Place,
    SpacyNER,
    analyze_amounts,
    analyze_dates,
    analyze_gcam,
    analyze_locations,
    analyze_names,
    default_gazetteer,
    default_gcam_lexicon,
    fields,
    generate_gkg,
    serialize_gkg,
)


def ner_places(text, *names):
    mentions = []
    for name in names:
        cursor = 0
        while (start := text.find(name, cursor)) >= 0:
            mentions.append(EntityMention(name, "LOCATION", start, start + len(name)))
            cursor = start + len(name)
    return NERResult(text, tuple(mentions))


class DatesTests(unittest.TestCase):
    def test_resolutions_repetitions_and_unicode_offsets(self):
        text = "😀 In 2020, in March 2021, on February 29, 2024 and 29 February; 2024-02-29."
        result = analyze_dates(text)
        self.assertEqual(
            [(m.resolution, m.month, m.day, m.year) for m in result.mentions],
            [(1, 0, 0, 2020), (2, 3, 0, 2021), (3, 2, 29, 2024), (4, 2, 29, 0), (3, 2, 29, 2024)],
        )
        self.assertEqual(result.mentions[0].start, text.index("2020"))
        self.assertTrue(all(text[m.start : m.end] == m.text for m in result.mentions))
        self.assertEqual(fields.extract_enhanced_dates(text), result.to_gkg())

    def test_invalid_dates_ambiguous_numeric_and_no_inferred_year(self):
        result = analyze_dates("February 30, 2025 and 2023-02-29 and 02/03/2025.")
        self.assertEqual(result.mentions, ())
        self.assertEqual(
            [m.reason for m in result.issues],
            ["invalid-calendar-date", "invalid-calendar-date", "ambiguous-numeric-date"],
        )
        self.assertEqual(analyze_dates("02/03/2025", numeric_order="dmy").to_gkg(), "3#3#2#2025#0")
        self.assertEqual(analyze_dates("02/03/2025", numeric_order="mdy").to_gkg(), "3#2#3#2025#0")
        self.assertEqual(analyze_dates("31/12/2025").to_gkg(), "3#12#31#2025#0")
        self.assertEqual(analyze_dates("June 5th").to_gkg(), "4#6#5#0#0")
        self.assertEqual(analyze_dates("yesterday in June").to_gkg(), "")
        self.assertEqual(analyze_dates("$2025 and 2025 people and v2.2025").mentions, ())


class AmountsTests(unittest.TestCase):
    def test_currency_decimals_magnitudes_and_textual_numbers(self):
        text = "😀 We spent $1.25 billion; sent twenty-five trucks and two million displaced civilians; bought 1,345 houses and paid USD 25m and € 12.50."
        result = analyze_amounts(text)
        self.assertEqual(
            [(m.amount, m.object_type) for m in result.mentions],
            [
                (Decimal("1250000000"), "dollars"),
                (Decimal(25), "trucks"),
                (Decimal(2000000), "displaced civilians"),
                (Decimal(1345), "houses"),
                (Decimal(25000000), "dollars"),
                (Decimal("12.50"), "euros"),
            ],
        )
        self.assertEqual(result.mentions[0].start, text.index("$"))
        self.assertEqual(fields.extract_amounts(text), result.to_gkg())
        self.assertIn("12.5,euros,", result.to_gkg())

    def test_dates_percentages_versions_and_unquantified_amounts(self):
        text = "On May 5, 2024, 2025-03-04, and 02/03/2025 it rose 45%, 10 percent and 15 per cent; v2.3.1 at 10:30. Hundreds of people went, and one of them spoke."
        self.assertEqual(analyze_amounts(text).mentions, ())
        self.assertEqual(analyze_amounts("2025 people").mentions[0].amount, Decimal(2025))
        self.assertEqual(
            analyze_amounts("one hundred and twenty houses").mentions[0].amount, Decimal(120)
        )
        self.assertEqual(
            analyze_amounts("two billion three million dollars").mentions[0].amount,
            Decimal(2003000000),
        )
        self.assertEqual(
            analyze_amounts("-1.25 million dollars").mentions[0].amount, Decimal(-1250000)
        )
        self.assertEqual(analyze_amounts("12 were sent").to_gkg(), "12,,0")


class LocationsTests(unittest.TestCase):
    def gazetteer(self):
        return Gazetteer(
            "fixture",
            (
                Place("1", "France", "FR", "FR", "46", "2", "FR"),
                Place(
                    "2", "Texas, United States", "US", "TX", "31", "-100", "TX", aliases=("Texas",)
                ),
                Place(
                    "4",
                    "Paris, Ile-De-France, France",
                    "FR",
                    "FR11",
                    "48.85",
                    "2.35",
                    "-1456928",
                    "123",
                    ("Paris",),
                ),
                Place(
                    "3",
                    "Paris, Texas, United States",
                    "US",
                    "TX",
                    "33.66",
                    "-95.55",
                    "1364810",
                    "321",
                    ("Paris",),
                ),
            ),
        )

    def test_context_resolution_wire_layout_and_duplicate_mentions(self):
        text = "😀 Paris, France. Paris in France. Atlantis."
        result = analyze_locations(
            text, ner=ner_places(text, "Paris", "France", "Atlantis"), gazetteer=self.gazetteer()
        )
        self.assertEqual([m.place.country_code for m in result.mentions], ["FR", "FR", "FR", "FR"])
        self.assertEqual(len(result.to_gkg().split(";")), 2)
        self.assertEqual(len(result.to_gkg(enhanced=True).split(";")), 4)
        first = result.to_gkg(enhanced=True).split(";")[0].split("#")
        self.assertEqual(len(first), 9)
        self.assertEqual(first[4], "123")
        self.assertEqual(first[-1], "2")
        self.assertEqual(result.issues[0].reason, "unknown-place")
        self.assertEqual(len(result.count_locations[0].components()), 7)
        self.assertEqual(
            fields.extract_locations(
                text, ner=ner_places(text, "Paris", "France"), gazetteer=self.gazetteer()
            ),
            result.to_gkg(),
        )

    def test_ambiguity_state_context_and_combined_spans(self):
        self.assertEqual(
            analyze_locations("Paris", ner=ner_places("Paris", "Paris"), gazetteer=self.gazetteer())
            .issues[0]
            .reason,
            "ambiguous-place",
        )
        text = "Paris, Texas"
        result = analyze_locations(text, ner=ner_places(text, text), gazetteer=self.gazetteer())
        self.assertEqual(result.mentions[0].place.country_code, "US")
        self.assertEqual([m.text for m in result.mentions], ["Paris", "Texas"])
        with self.assertRaises(ValueError):
            analyze_locations("Other text", ner=ner_places("Paris", "Paris"))
        self.assertIs(default_gazetteer(), default_gazetteer())
        self.assertGreater(len(default_gazetteer().places), 10000)


class NamesAndGCAMTests(unittest.TestCase):
    def test_names_keep_singletons_broad_categories_and_surface_spans(self):
        text = "Acme and World Cup and Acme"
        ner = NERResult(
            text,
            (),
            name_mentions=(
                NameMention("Acme", 0, 4, "ORG"),
                NameMention("World Cup", 9, 18, "EVENT"),
                NameMention("Acme", 23, 27, "ORG"),
            ),
        )
        self.assertEqual(analyze_names(text, ner=ner).to_gkg(), "Acme,0;World Cup,9;Acme,23")
        self.assertEqual(
            fields.extract_all_names(text, ner=ner), analyze_names(text, ner=ner).to_gkg()
        )
        with self.assertRaises(ValueError):
            NERResult("Other", (), name_mentions=(NameMention("Acme", 0, 4),))

    @unittest.skipUnless(importlib.util.find_spec("spacy"), "spaCy unavailable")
    def test_spacy_broad_categories_exclude_numeric_and_temporal_entities(self):
        import spacy

        nlp = spacy.blank("en")
        ruler = nlp.add_pipe("entity_ruler")
        ruler.add_patterns(
            [
                {"label": label, "pattern": name}
                for label, name in [
                    ("EVENT", "World Cup"),
                    ("LAW", "Affordable Care Act"),
                    ("PRODUCT", "Widget"),
                    ("DATE", "Tuesday"),
                    ("MONEY", "$20"),
                ]
            ]
        )
        result = SpacyNER(nlp).analyze("World Cup, Affordable Care Act, Widget on Tuesday for $20.")
        self.assertEqual(
            [m.text for m in result.all_names], ["World Cup", "Affordable Care Act", "Widget"]
        )
        self.assertEqual(result.mentions, ())

    def test_gcam_sparse_raw_counts_and_unsupported_dimensions(self):
        lexicon = GCAMLexicon(
            "fixture", {"c2.21": frozenset({"hand"}), "c2.74": frozenset({"goal"})}
        )
        result = analyze_gcam("Hand hand goal unknown.", lexicon=lexicon)
        self.assertEqual(result.to_gkg(), "wc:4,c2.21:2,c2.74:1")
        self.assertEqual(analyze_gcam("unknown", lexicon=lexicon).to_gkg(), "wc:1")
        self.assertEqual(analyze_gcam("", lexicon=lexicon).to_gkg(), "wc:0")
        self.assertEqual(fields.extract_gcam("hand", lexicon=lexicon), "wc:1,c2.21:1")
        self.assertEqual(len(default_gcam_lexicon().dimensions), 809)
        with self.assertRaises(ValueError):
            GCAMLexicon("bad", {"v2.21": frozenset({"hand"})})
        with self.assertRaises(TypeError):
            GCAMLexicon("bad", {"c2.21": "hand"})


class IntegrationTests(unittest.TestCase):
    def test_extraction_uses_translated_body_and_rejects_source_spans(self):
        text = "France sent 12 trucks on June 5, 2025."
        backend = Mock(engine="fixture", translate=Mock(return_value=text))
        recognizer = Mock(analyze=Mock(return_value=ner_places(text, "France")))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            record = generate_gkg(
                "Original source",
                input_language="fr",
                translator=backend,
                ner=recognizer,
                identifier="https://example.org/a",
                batch_time="20261001091500",
                sequence=1,
            )
        recognizer.analyze.assert_called_once_with(text)
        self.assertEqual(record["V2.1ALLNAMES"], "France,0")
        self.assertEqual(record["V2.1AMOUNTS"], "12,trucks,12")
        self.assertEqual(record["V2.1ENHANCEDDATES"], "3#6#5#2025#25")
        self.assertTrue(record["V2ENHANCEDLOCATIONS"].endswith("#0"))
        self.assertEqual(record["V2GCAM"], fields.extract_gcam(text))
        self.assertTrue(record["V2.1TRANSLATIONINFO"].startswith("srclc:fra"))
        lexicon = GCAMLexicon("translated-test", {}, {"v26.1": {"trucks": 1}})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            weighted = generate_gkg(
                "Original source",
                input_language="fr",
                translator=backend,
                ner=recognizer,
                gcam_lexicon=lexicon,
                identifier="https://example.org/a",
                batch_time="20261001091500",
                sequence=1,
            )
        self.assertIn("c26.1:1,v26.1:1", weighted["V2GCAM"])
        with self.assertRaises(ValueError):
            generate_gkg(
                "Original source",
                input_language="fr",
                translator=backend,
                ner=NERResult("Original source", ()),
                identifier="https://example.org/a",
                batch_time="20261001091500",
                sequence=1,
            )

    def test_full_row_shared_ner_count_geography_and_overrides(self):
        text = "Paris, France on June 5, 2025: 12 people were killed."
        recognizer = Mock(analyze=Mock(return_value=ner_places(text, "Paris", "France")))
        record = generate_gkg(
            text,
            identifier="https://example.org/a",
            batch_time="20261001091500",
            sequence=1,
            ner=recognizer,
            sharing_image="",
            related_images=[],
            social_image_embeds=[],
            social_video_embeds=[],
            extras={},
            strict=True,
        )
        recognizer.analyze.assert_called_once_with(text)
        self.assertTrue(all(isinstance(v, str) for v in record.values()))
        self.assertIn("#FR#", record["V1COUNTS"])
        self.assertEqual(len(serialize_gkg(record).rstrip("\n").split("\t")), 27)
        self.assertIn("12,people,", record["V2.1AMOUNTS"])
        self.assertEqual(record["V2.1ENHANCEDDATES"], f"3#6#5#2025#{text.index('June')}")
        self.assertTrue(record["V2GCAM"].startswith("wc:"))
        overrides = {
            column: "external"
            for column in (
                "V1LOCATIONS",
                "V2ENHANCEDLOCATIONS",
                "V2.1ENHANCEDDATES",
                "V2GCAM",
                "V2.1ALLNAMES",
                "V2.1AMOUNTS",
            )
        }
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            overridden = generate_gkg(
                text,
                identifier="https://example.org/a",
                batch_time="20261001091500",
                sequence=1,
                field_values=overrides,
            )
        self.assertTrue(all(overridden[k] == v for k, v in overrides.items()))


if __name__ == "__main__":
    unittest.main()
