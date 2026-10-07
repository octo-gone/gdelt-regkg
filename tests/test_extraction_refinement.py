"""Regression checks for name serialization, count labels, and original offsets."""

import unittest
from dataclasses import replace
from types import SimpleNamespace

from gdelt_regkg.counts import analyze_counts
from gdelt_regkg.ner import EntityMention, NameRules, NERResult, SpacyNER
from gdelt_regkg.rule_inputs import count_rules_from_input
from gdelt_regkg.themes import analyze_themes
from gdelt_regkg.utils import read_resource_json


class RefinementTests(unittest.TestCase):
    def test_name_filter_preserves_original_mentions_and_has_explicit_threshold(self):
        text = "Dr Jane Doe met Acme Bank and Fictional Club."
        mentions = tuple(
            EntityMention(name, label, text.index(name), text.index(name) + len(name))
            for name, label in [
                ("Dr Jane Doe", "PERSON"),
                ("Acme Bank", "ORG"),
                ("Fictional Club", "ORG"),
            ]
        )
        rules = NameRules(
            strip_person_titles=True,
            organization_weights={"w:bank": 2.0},
            organization_intercept=-1.0,
            organization_threshold=0.0,
        )
        result = NERResult(text, mentions, name_policy="gdelt-full-names", name_rules=rules)
        self.assertEqual(result.to_gkg("PERSON"), "jane doe")
        self.assertEqual(result.to_gkg("ORG"), "acme bank")
        self.assertEqual(result.mentions, mentions)
        self.assertEqual(result.to_gkg("PERSON", enhanced=True), "jane doe,0")
        with self.assertRaises(ValueError):
            NameRules(organization_weights={"x": float("nan")})

    def test_generic_count_object_cell_policy_keeps_source_mentions(self):
        payload = read_resource_json("lexicons", "counts.v2.json")
        payload["settings"]["empty_object_nouns"] = ["people"]
        result = analyze_counts("Three people were killed.", rules=count_rules_from_input(payload))
        self.assertTrue(all(m.object_type == "people" for m in result.mentions))
        self.assertIn("#3##", result.to_gkg())
        self.assertNotIn("#people#", result.to_gkg())

    def test_batched_ner_preserves_text_and_output_order(self):
        class Backend:
            meta = {"name": "fixture"}
            pipe_names = ["ner"]

            def __call__(self, text):
                return SimpleNamespace(text=text, ents=[])

            def pipe(self, texts, **kwargs):
                return (self(text) for text in texts)

        backend = SpacyNER(Backend())
        texts = ["First body.", "Second body."]
        self.assertEqual([r.text for r in backend.analyze_many(texts)], texts)
        with self.assertRaises(ValueError):
            list(backend.analyze_many(texts, batch_size=0))

    def test_full_names_preserve_mentions_and_original_enhanced_offsets(self):
        text = "😀 The White House met Robert F. Kennedy Jr.'s adviser. Kennedy spoke on CNN."
        names = [
            ("The White House", "ORG"),
            ("Robert F. Kennedy Jr.'s", "PERSON"),
            ("Kennedy", "PERSON"),
            ("CNN", "ORG"),
        ]
        mentions = tuple(
            EntityMention(name, label, text.index(name), text.index(name) + len(name))
            for name, label in names
        )
        surface = NERResult(text, mentions)
        refined = replace(surface, name_policy="gdelt-full-names")
        self.assertEqual(refined.mentions, surface.mentions)
        self.assertEqual(refined.to_gkg("PERSON"), "robert f kennedy jr")
        self.assertEqual(refined.to_gkg("ORG"), "white house")
        self.assertEqual(refined.to_gkg("ORG", enhanced=True), "white house,2")
        self.assertEqual(
            refined.to_gkg("PERSON", enhanced=True), f"robert f kennedy jr,{text.index('Robert')}"
        )
        self.assertEqual(replace(surface, name_policy="gdelt").to_gkg("ORG"), "white house;cnn")
        self.assertEqual(surface.to_gkg("ORG"), "The White House;CNN")

    def test_canonical_names_deduplicate_after_formatting(self):
        text = "The White House met White House."
        mentions = (
            EntityMention(text[:15], "ORG", 0, 15),
            EntityMention("White House", "ORG", 20, 31),
        )
        result = NERResult(text, mentions, name_policy="gdelt-full-names")
        self.assertEqual(result.to_gkg("ORG"), "white house")
        self.assertEqual(result.to_gkg("ORG", enhanced=True), "white house,0;white house,20")
        with self.assertRaises(ValueError):
            replace(result, name_policy="unknown")

    def test_count_label_calibration_does_not_turn_patient_totals_into_incidents(self):
        refined = count_rules_from_input(read_resource_json("lexicons", "counts.v2.json"))
        original = count_rules_from_input(read_resource_json("lexicons", "counts.v1.json"))
        self.assertEqual(
            analyze_counts("The trial enrolled 12 patients.", rules=refined).mentions, ()
        )
        self.assertTrue(analyze_counts("The trial enrolled 12 patients.", rules=original).mentions)
        counts = analyze_counts("Police arrested three suspects.", rules=refined)
        self.assertEqual(
            {m.count_type for m in counts.mentions},
            {"ARREST", "CRISISLEX_C07_SAFETY", "SOC_GENERALCRIME"},
        )
        self.assertEqual({m.number for m in counts.mentions}, {3})

    def test_optional_time_guard_rejects_durations_and_keeps_casualties(self):
        payload = read_resource_json("lexicons", "counts.v1.json")
        payload["settings"]["reject_time_objects"] = True
        rules = count_rules_from_input(payload)
        result = analyze_counts("Two people were injured two weeks ago.", rules=rules)
        self.assertEqual({m.number for m in result.mentions}, {2})
        self.assertEqual({m.start for m in result.mentions}, {0})
        self.assertEqual(analyze_counts("He was injured two weeks ago.", rules=rules).mentions, ())
        payload["settings"]["reject_time_objects"] = "yes"
        with self.assertRaises(TypeError):
            count_rules_from_input(payload)

    def test_theme_expansion_matches_taxonomy_terms_and_keeps_offsets(self):
        text = "😀 An economist discussed inflation and monetary policy."
        result = analyze_themes(text)
        codes = {m.theme for m in result.mentions}
        self.assertTrue({"TAX_FNCACT_ECONOMIST", "ECON_INFLATION", "WB_442_INFLATION"} <= codes)
        for mention in result.mentions:
            self.assertEqual(text[mention.start : mention.end], mention.text)
        self.assertNotIn(
            "ARMEDCONFLICT",
            {m.theme for m in analyze_themes("A midterm election in Pakistan.").mentions},
        )


if __name__ == "__main__":
    unittest.main()
