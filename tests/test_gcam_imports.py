"""Authored source fixtures for English GCAM dictionary converters."""

import csv
import gzip
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from gdelt_regkg.builders.gcam_expansion import gcam_coverage
from gdelt_regkg.builders.gcam_formats import read_cat, xlsx_rows
from gdelt_regkg.builders.gcam_imports import (
    add_central_bank,
    add_count_dictionary,
    add_experimental_themes,
    add_general_inquirer_legacy,
    add_lexicoder_topics,
    add_loughran_mcdonald,
    add_ml_senticon,
    add_opinion_observer,
    add_sentiwordnet,
    add_sentiwords,
    add_subjectivity,
    add_weighted_table,
    add_wordnet_affect_v1,
)
from gdelt_regkg.cli import main
from gdelt_regkg.cli.gcam import GCAMOptions
from gdelt_regkg.cli.inputs import BuildOptions, resolve_inputs
from gdelt_regkg.cli.profiles import compile_profiles
from gdelt_regkg.cli.sources import download_source
from gdelt_regkg.fields.gcam import _load, analyze_gcam


class EnglishGCAMImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.baseline = {"name": "authored", "dimensions": []}

    def book(self, categories):
        return {
            "source_sha256": "fixture",
            "dimensions": {
                key: {"category": name, "language": "eng", "dictionary": "authored"}
                for key, name in categories.items()
            },
        }

    def file(self, name, text):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_cat_paths_typos_exclusions_and_missing_category(self):
        path = self.root / "body.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("body.cat", "BARRIER TOTAL\n\tCONTAINEERS\n\t\tBAG* (1)\n")
            z.writestr("body.exc", "BAGPIPE*\n")
        book = self.book(
            {"c13.1": "BARRIER TOTAL/CONTAINERS", "c13.6": "BARRIER TOTAL/SPECIAL ANIMALS"}
        )
        profile = add_count_dictionary(self.baseline, path, book, "body-boundary")
        result = analyze_gcam("bag bags bagpipes", lexicon=_load(profile))
        self.assertEqual(result.to_gkg(), "wc:3,c13.1:2")
        self.assertEqual(
            profile["sources"]["body-boundary"]["unmapped_categories"],
            {"c13.6": "BARRIER TOTAL/SPECIAL ANIMALS"},
        )
        bad = self.file("bad.cat", "GROUP\n\tword (2)\n")
        with self.assertRaises(ValueError):
            read_cat(bad)
        typo = self.file("typo.cat", "GROUP\n\tbad*(source (1)\n\tgood (1)\n")
        self.assertEqual(read_cat(typo)[2], ["bad*(source"])

    def test_general_inquirer_gap_case_distinctions_and_baseline_preservation(self):
        source = self.file(
            "inqdict.txt",
            "Entryword Source Pos FOOD Food\n"
            "APPLE H4 FOOD Pos | definition\n"
            "MEAL H4 Food | definition\n",
        )
        baseline = {"name": "legacy", "dimensions": [{"key": "c2.72", "words": ["meal"]}]}
        book = self.book({"c2.63": "FOOD", "c2.72": "Food", "c2.155": "Pos"})
        profile = add_general_inquirer_legacy(baseline, source, book)
        self.assertEqual(
            analyze_gcam("apple meal", lexicon=_load(profile)).counts,
            {"c2.63": 1, "c2.72": 1, "c2.155": 1},
        )
        self.assertEqual(baseline["dimensions"], [{"key": "c2.72", "words": ["meal"]}])

    def test_sentiwords_distinct_pos_records_repetitions_and_zero_scores(self):
        source = self.file(
            "SentiWords_1.0.txt", "# authored\ngood#a\t0.8\ngood#a\t0.8\ngood#n\t0.2\nflat#n\t0\n"
        )
        book = self.book({"c11.1": "Polarity", "v11.1": "Polarity (Scored Value)"})
        lexicon = _load(add_sentiwords(self.baseline, source, book))
        self.assertEqual(lexicon.weighted_dimensions["v11.1"]["good"], 0.5)
        result = analyze_gcam("good good flat unknown", lexicon=lexicon)
        self.assertEqual(result.counts["c11.1"], 3)
        self.assertAlmostEqual(result.values["v11.1"], 1 / 3)
        self.assertEqual(analyze_gcam("flat", lexicon=lexicon).to_gkg(), "wc:1,c11.1:1,v11.1:0")

    def test_sentiwordnet_senses_and_comment_footer(self):
        source = self.file(
            "SentiWordNet_3.0.0.txt",
            "# authored\n"
            "a\t00000001\t0.8\t0\tgood#1\tfixture\n"
            "n\t00000002\t0.2\t0.4\tgood#2\tfixture\n\t\t\t\t#\t\n",
        )
        book = self.book(
            {
                "c10.1": "Positive",
                "v10.1": "Positive (Scored Value)",
                "c10.2": "Negative",
                "v10.2": "Negative (Scored Value)",
            }
        )
        result = analyze_gcam("good", lexicon=_load(add_sentiwordnet(self.baseline, source, book)))
        self.assertEqual(result.counts, {"c10.1": 1, "c10.2": 1})
        self.assertEqual(result.values, {"v10.1": 0.5, "v10.2": 0.2})

    def test_liwc_categories_are_mapped_by_names_not_source_numbers(self):
        source = self.file("mfd.dic", "%\n55 care.virtue\n1 care.vice\n%\nsafe* 55\nhurt 1\n")
        book = self.book({"c25.1": "HarmVirtue", "c25.2": "HarmVice"})
        lexicon = _load(add_count_dictionary(self.baseline, source, book, "moral-foundations"))
        self.assertEqual(
            analyze_gcam("safely hurt", lexicon=lexicon).counts, {"c25.1": 1, "c25.2": 1}
        )
        invalid = self.file("bad.dic", "%\n1 affect\n%\nword 2\n")
        with self.assertRaises(ValueError):
            add_count_dictionary(self.baseline, invalid, book, "liwc")

    def test_lexicoder_xml_preserves_explicit_boundaries_and_stems(self):
        source = self.file(
            "policy_agendas_english.lcd",
            '<dictionary><cnode name="healthcare">'
            '<pnode name=" ALLERG"/><pnode name=" HEALTH "/>'
            "</cnode></dictionary>",
        )
        book = self.book({"c4.3": "HEALTHCARE"})
        lexicon = _load(add_lexicoder_topics(self.baseline, source, book))
        self.assertEqual(
            analyze_gcam("allergies health unhealthy", lexicon=lexicon).counts["c4.3"], 2
        )

    def test_liwc_2007_abbreviations_and_non_gcam_categories(self):
        source = self.file(
            "LIWC2007.dic",
            "%\n90 preps\n80 relig\n70 tentat\n60 filler\n%\n"
            "under 90\nprayer 80\nperhaps 70\numm 60\n",
        )
        book = self.book({"c5.46": "Prep", "c5.3": "Religion", "c5.26": "Tentative"})
        profile = add_count_dictionary(self.baseline, source, book, "liwc")
        result = analyze_gcam("under prayer perhaps umm", lexicon=_load(profile))
        self.assertEqual(result.counts, {"c5.46": 1, "c5.3": 1, "c5.26": 1})
        self.assertEqual(
            profile["sources"]["liwc"]["category_aliases"],
            {"preps": "Prep", "relig": "Religion", "tentat": "Tentative"},
        )

    def test_mpqa_stems_strength_polarity_and_union_of_pos_records(self):
        source = self.file(
            "clues.tff",
            "type=strongsubj len=1 word1=joy pos1=adj stemmed1=y priorpolarity=positive\n"
            "type=strongsubj len=1 word1=joy pos1=noun stemmed1=y priorpolarity=positive\n",
        )
        book = self.book(
            {"c12.1": "strongsubj", "c12.5": "strongsubjtonepositive", "c12.9": "tonepositive"}
        )
        result = analyze_gcam(
            "joyful joy", lexicon=_load(add_subjectivity(self.baseline, source, book))
        )
        self.assertEqual(set(result.counts.values()), {2})

    def test_mpqa_retains_clues_with_documented_source_normalizations(self):
        text = (
            "type=weaksubj len=1 word1=calm pos1=adj stemmed1=n "
            "polarity=negative priorpolarity=weakneg\n"
            "type=strongsubj len=1 word1=pervasive pos1=adj stemmed1=n m priorpolarity=negative\n"
            "type=strongsubj len=1 word1=pervasive pos1=noun stemmed1=n m priorpolarity=negative\n"
            "type=strongsubj len=1 word1=uncertain pos1=adj stemmed1=1 priorpolarity=negative\n"
        )
        source = self.file("clues.tff", text)
        book = self.book(
            {
                "c12.1": "strongsubj",
                "c12.3": "strongsubjtonenegative",
                "c12.7": "tonenegative",
                "c12.10": "weaksubj",
                "c12.12": "weaksubjtonenegative",
            }
        )
        profile = add_subjectivity(self.baseline, source, book)
        result = analyze_gcam("calm pervasive pervasive uncertain", lexicon=_load(profile))
        self.assertEqual(
            result.counts,
            {"c12.1": 2, "c12.3": 2, "c12.7": 3, "c12.10": 1, "c12.12": 1},
        )
        changes = profile["sources"]["subjectivity"]["normalizations"]
        self.assertEqual([change["line"] for change in changes], [1, 2, 3])
        self.assertEqual(changes[0]["normalized"], "negative")
        self.assertEqual(changes[1]["removed_tokens"], ["m"])
        self.assertEqual(
            profile["sources"]["subjectivity"]["skipped_entries"],
            [{"line": 4, "word": "uncertain", "reason": "unrecognized stemmed1=1"}],
        )
        self.assertEqual(source.read_text(encoding="utf-8"), text)
        for invalid in (
            text.replace("polarity=negative priorpolarity=weakneg", "priorpolarity=weakneg"),
            text.replace(" m priorpolarity", " mystery priorpolarity"),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                add_subjectivity(self.baseline, self.file("bad.tff", invalid), book)

    def test_loughran_removed_entries_and_opinion_comments(self):
        source = self.file(
            "lm.csv",
            "Word,Litigious,Strong_Modal,Weak_Modal,Negative,Positive,Uncertainty\n"
            "GAIN,0,0,0,0,2011,0\nOLD,0,0,0,0,-2020,0\n",
        )
        book = self.book({"c6.5": "Positive"})
        lexicon = _load(add_loughran_mcdonald(self.baseline, source, book))
        self.assertEqual(analyze_gcam("gain old", lexicon=lexicon).counts["c6.5"], 1)
        path = self.root / "opinion.zip"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("negative-words.txt", "; comment\nbad\n")
            z.writestr("positive-words.txt", "; comment\ngood\n")
        lexicon = _load(
            add_opinion_observer(
                self.baseline, path, self.book({"c7.1": "Negative", "c7.2": "Positive"})
            )
        )
        self.assertEqual(analyze_gcam("bad good", lexicon=lexicon).counts, {"c7.1": 1, "c7.2": 1})

    def test_emfd_value_only_and_hedonometer_complete_english_list(self):
        source = self.file("emfd.csv", "word,care_p,care_sent\ncare,0.8,-0.5\nflat,0,0\n")
        book = self.book({"c42.1": "moralwordcount", "v42.2": "care_p", "v42.7": "care_sent"})
        lexicon = _load(add_weighted_table(self.baseline, source, book, "emfd"))
        self.assertEqual(
            analyze_gcam("flat", lexicon=lexicon).to_gkg(), "wc:1,c42.1:1,v42.2:0,v42.7:0"
        )
        profile = {
            "meta": {"total_count": 1},
            "objects": [{"word": "joy", "happs": 8, "wordlist": {"title": "labMT-en-v1"}}],
        }
        source = self.file("labmt.json", json.dumps(profile))
        book = self.book({"c21.1": "Happiness", "v21.1": "Happiness (Scored Value)"})
        lexicon = _load(add_weighted_table(self.baseline, source, book, "hedonometer"))
        self.assertEqual(analyze_gcam("joy", lexicon=lexicon).values["v21.1"], 8)
        profile["meta"]["total_count"] = 2
        source.write_text(json.dumps(profile))
        with self.assertRaises(ValueError):
            add_weighted_table(self.baseline, source, book, "hedonometer")

    def test_wordnet_v1_uses_original_offsets_and_direct_labels(self):
        source = self.file(
            "wn-affect-labels-1.0.txt", "n#00000001|core|emo|cog\nn#99999999|core|emo\n"
        )
        wordnet = self.root / "wordnet.tar.gz"
        with tarfile.open(wordnet, "w:gz") as z:
            for pos, letter in (("noun", "n"), ("verb", "v"), ("adj", "a"), ("adv", "r")):
                for suffix, raw in (
                    ("data." + pos, f"00000001 04 {letter} 01 joy 0 000 | fixture\n".encode()),
                    (pos + ".exc", b"joys joy\n"),
                ):
                    info = tarfile.TarInfo(suffix)
                    info.size = len(raw)
                    z.addfile(info, io.BytesIO(raw))
        book = self.book({"c14.3": "Cognitive State", "c14.5": "Emotion"})
        profile = add_wordnet_affect_v1(self.baseline, source.parent, wordnet, book)
        self.assertEqual(profile["sources"]["wordnet-affect-1.0"]["missing_synsets"], 1)
        self.assertEqual(
            analyze_gcam("joys", lexicon=_load(profile)).counts, {"c14.3": 1, "c14.5": 1}
        )

    def test_experimental_themes_have_document_guards_and_preserve_baseline(self):
        book = self.book(
            {"c18.1": "EXISTING", "c18.40": "FOOD_STAPLE", "c18.339": "TAX_WORLDBIRDS"}
        )
        baseline = {
            "name": "base",
            "dimensions": [{"key": "c18.1", "theme": "EXISTING"}],
            "theme_rules": [{"theme": "EXISTING", "phrase": "hospital"}],
        }
        profile = add_experimental_themes(baseline, book)
        lexicon = _load(profile)
        self.assertEqual(
            analyze_gcam("Eagles won. Rice spoke at the hospital.", lexicon=lexicon).counts,
            {"c18.1": 1, "c18.40": 0, "c18.339": 0},
        )
        positive = analyze_gcam(
            "Bird conservation protects eagles. The food harvest includes rice.", lexicon=lexicon
        )
        self.assertEqual(positive.counts["c18.40"], 1)
        self.assertEqual(positive.counts["c18.339"], 1)
        self.assertEqual(len(baseline["theme_rules"]), 1)
        self.assertEqual(profile["sources"]["themes-authored"]["approximation"], "authored-rules")
        coverage = gcam_coverage(profile, book)
        self.assertEqual(coverage["compiled_dimensions"], 3)
        self.assertEqual(coverage["supported_dimensions"], 1)
        repeated = add_experimental_themes(profile, book)
        self.assertEqual(gcam_coverage(repeated, book)["supported_dimensions"], 1)

    def test_weighted_cat_heading_keeps_special_animals_separate(self):
        source = self.file(
            "bodtyp.cat",
            "BARRIER TOTAL\n\tSHELL ANIMAL\n\t\tTURTL* (1)\n\tSPECIAL ANIMALS (1)\n\t\tALLIGATOR* (1)\n\t\tBADGE (1)\n\t\tBADGERS (1)\n\t\tBEAVER* (1)\n",
        )
        book = self.book(
            {"c13.5": "BARRIER TOTAL/SHELL ANIMAL", "c13.6": "BARRIER TOTAL/SPECIAL ANIMALS"}
        )
        profile = add_count_dictionary(self.baseline, source, book, "body-boundary")
        result = analyze_gcam("alligator badgers beavers turtles", lexicon=_load(profile))
        self.assertEqual(result.counts, {"c13.5": 1, "c13.6": 3})

    def test_mpqa_download_requires_explicit_opt_in(self):
        entry = {
            "opt_in_flag": "--download-mpqa",
            "instructions": "GPL-3.0 mirror",
            "url": "https://example.invalid/lexicon",
            "sha256": "unused",
        }
        with (
            patch("gdelt_regkg.cli.sources.urlopen") as fetch,
            self.assertRaisesRegex(ValueError, "download-mpqa"),
        ):
            download_source(self.root / "mpqa.zip", entry)
        fetch.assert_not_called()

    def test_mpqa_opt_in_download_verifies_bytes(self):
        raw = b"authored download fixture"
        entry = {
            "opt_in_flag": "--download-mpqa",
            "instructions": "GPL-3.0 mirror",
            "url": "https://example.invalid/lexicon",
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        path = self.root / "mpqa.zip"
        with patch("gdelt_regkg.cli.sources.urlopen", return_value=io.BytesIO(raw)):
            download_source(path, entry, allow_opt_in=True)
        self.assertEqual(path.read_bytes(), raw)

    def test_mpqa_flag_adds_component_and_authorizes_only_that_download(self):
        baseline = self.file("base.json", json.dumps(self.baseline))
        codebook = self.file("codebook.txt", "authored")

        def acquire(path, entry, **kwargs):
            self.assertTrue(kwargs["allow_opt_in"])
            Path(path).write_bytes(b"authored")

        recipe = {
            "sources": {
                "subjectivity": {
                    "filename": "mpqa.zip",
                    "manual": True,
                    "instructions": "authored fixture",
                }
            }
        }
        with patch("gdelt_regkg.cli.inputs.download_source", side_effect=acquire) as fetch:
            inputs = resolve_inputs(
                self.root / "out",
                BuildOptions(
                    targets=("gcam",),
                    gcam=GCAMOptions(baseline=baseline),
                    sources={"codebook": codebook},
                    sources_dir=self.root,
                    download_mpqa=True,
                    recipe=recipe,
                ),
            )
        self.assertIn("subjectivity", inputs.gcam.components)
        fetch.assert_called_once()

    def test_manual_source_message_never_downloads(self):
        with (
            patch("gdelt_regkg.cli.sources.urlopen") as fetch,
            self.assertRaisesRegex(ValueError, "licensed"),
        ):
            download_source(
                self.root / "LIWC2007.dic",
                {"manual": True, "instructions": "Obtain licensed input."},
            )
        fetch.assert_not_called()

    def test_source_json_rejects_unknown_crosswalk_and_coverage_pairs_keys(self):
        source = self.file("time.json", json.dumps({"categories": {"Time": ["today"]}}))
        book = self.book({"c39.1": "Time", "c42.1": "moralwordcount", "v42.2": "care_p"})
        profile = add_count_dictionary(self.baseline, source, book, "time")
        profile["dimensions"].append({"key": "v42.2", "scores": {"care": 1}, "emit_count": False})
        inventory = gcam_coverage(profile, book)
        self.assertEqual(inventory["supported_dimensions"], 2)
        self.assertEqual(inventory["native_dimensions"], 3)
        source.write_text(json.dumps({"categories": {"invented": ["today"]}}))
        with self.assertRaisesRegex(ValueError, "Unmapped"):
            add_count_dictionary(self.baseline, source, book, "time")

    def test_ml_senticon_xml_routes_layers_and_rejects_nonenglish(self):
        source = self.file(
            "senticon.en.xml",
            '<senticon lang="en"><layer level="2">'
            '<positive><lemma pos="a" pol="0.6">good</lemma></positive>'
            '<negative><lemma pos="a" pol="-0.7">bad</lemma></negative>'
            "</layer></senticon>",
        )
        book = self.book(
            {
                "c20.3": "Level2Positive",
                "v20.3": "Level2Positive (Scored Value)",
                "c20.4": "Level2Negative",
                "v20.4": "Level2Negative (Scored Value)",
            }
        )
        result = analyze_gcam(
            "good bad", lexicon=_load(add_ml_senticon(self.baseline, source, book))
        )
        self.assertEqual(result.values, {"v20.3": 0.6, "v20.4": -0.7})
        source.write_text(source.read_text().replace('lang="en"', 'lang="es"'))
        with self.assertRaisesRegex(ValueError, "English"):
            add_ml_senticon(self.baseline, source, book)

    def test_cli_incremental_build_replaces_component_and_emits_coverage(self):
        baseline = self.file(
            "base.json",
            json.dumps(
                {
                    "name": "base",
                    "dimensions": [
                        {"key": "c7.1", "words": ["obsolete"]},
                        {"key": "c7.3", "words": ["stale"]},
                    ],
                }
            ),
        )
        book = self.file(
            "codebook.txt",
            "Variable\tDictionaryID\tDimensionID\tType\tLanguageCode\tDictionaryHumanName\tDimensionHumanName\n"
            "c7.1\t7\t1\tWORDCOUNT\teng\tOpinion\tNegative\n"
            "c7.2\t7\t2\tWORDCOUNT\teng\tOpinion\tPositive\n",
        )
        source = self.root / "opinion"
        source.mkdir()
        (source / "negative-words.txt").write_text("bad\n")
        (source / "positive-words.txt").write_text("good\n")
        output = self.root / "out"
        inputs = resolve_inputs(
            output,
            BuildOptions(
                targets=("gcam",),
                gcam=GCAMOptions(baseline=baseline, additions=("opinion-observer",)),
                sources={"codebook": book, "opinion-observer": source},
            ),
        )
        artifacts, selections = compile_profiles(inputs)
        self.assertEqual(selections["gcam"], "gcam.custom.json.gz")
        self.assertEqual({d["key"] for d in artifacts[0].payload["dimensions"]}, {"c7.1", "c7.2"})
        coverage = next(a.payload for a in artifacts if a.path == "gcam/coverage.custom.json")
        self.assertEqual(coverage["supported_dimensions"], 2)
        self.assertFalse(output.exists())

    def test_xlsx_literals_sparse_cells_and_formula_rejection(self):
        path = self.root / "dictionary.xlsx"
        main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

        def workbook(formula=""):
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(
                    "xl/workbook.xml",
                    f'<workbook xmlns="{main}" xmlns:r="{rel}"><sheets><sheet name="Dictionary" r:id="rId1"/></sheets></workbook>',
                )
                z.writestr(
                    "xl/_rels/workbook.xml.rels",
                    '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
                )
                z.writestr(
                    "xl/sharedStrings.xml", f'<sst xmlns="{main}"><si><t>Word</t></si></sst>'
                )
                z.writestr(
                    "xl/worksheets/sheet1.xml",
                    f'<worksheet xmlns="{main}"><sheetData><row><c r="A1" t="s"><v>0</v></c><c r="C1"><v>1</v>{formula}</c></row></sheetData></worksheet>',
                )

        workbook()
        self.assertEqual(xlsx_rows(path, "Dictionary"), [{"A": "Word", "C": "1"}])
        workbook("<f>1+1</f>")
        with self.assertRaisesRegex(ValueError, "formulas"):
            xlsx_rows(path, "Dictionary")
