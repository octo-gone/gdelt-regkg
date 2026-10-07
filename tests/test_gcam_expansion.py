import gzip
import io
import json
import random
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

from gdelt_regkg.gcam import _load, _pattern_regex, analyze_gcam
from gdelt_regkg.scripts.build_gcam_expansion import (
    add_general_inquirer,
    add_roget,
    add_themes,
    add_wordnet_affect,
    add_wordnet_domains,
    add_wordnet_lexical,
    read_codebook,
)
from gdelt_regkg.themes import ThemeLexicon, ThemeRule
from gdelt_regkg.tone import tokenize_tone
from gdelt_regkg.utils import read_resource_json


class GCAMExpansionTests(unittest.TestCase):
    def test_indexed_wildcard_matching_preserves_legacy_priority_and_nonoverlap(self):
        terms = ["not bad*", "bad*", "badly", "not g?od", "*ful", "a *", "a b c", "a b"]
        lexicon = _load(
            {
                "name": "fixture",
                "dimensions": [
                    {"key": "c3.1", "patterns": terms},
                    {"key": "c3.2", "patterns": ["bad*", "not bad*", "g?od", "b* c"]},
                ],
            }
        )
        rng = random.Random(17)
        for _ in range(120):
            text = " ".join(
                rng.choices(["badly", "bad", "not", "good", "god", "grateful", "a", "b", "c"], k=25)
            )
            normalized = " ".join(tokenize_tone(text))
            result = analyze_gcam(text, lexicon=lexicon)
            for key, patterns in lexicon.patterns.items():
                self.assertEqual(
                    result.counts[key],
                    sum(1 for _ in _pattern_regex(patterns).finditer(normalized)),
                )

    def codebook(self, dimensions):
        return {
            "source_sha256": "fixture",
            "dimensions": {key: {"category": name} for key, name in dimensions.items()},
        }

    def baseline(self):
        return {
            "name": "authored-fixture",
            "dimensions": [
                {"key": "c2.21", "words": ["hand"]},
                {"key": "v26.1", "scores": {"good": 2}},
            ],
        }

    def wordnet(self, root):
        path = root / "wordnet.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for pos, lexname, word in [
                ("noun", 4, "child"),
                ("verb", 37, "love"),
                ("adj", 44, "amused(p)"),
                ("adv", 2, "happily"),
            ]:
                for name, raw in [
                    (
                        "data." + pos,
                        f"00000001 {lexname:02d} {pos[0]} 01 {word} 0 000 | authored\n".encode(),
                    ),
                    (pos + ".exc", b"children child\n" if pos == "noun" else b""),
                ]:
                    member = tarfile.TarInfo("dict/" + name)
                    member.size = len(raw)
                    archive.addfile(member, io.BytesIO(raw))
        return path

    def test_case_distinctions_tags_and_source_columns(self):
        codebook = self.codebook(
            {
                "c2.63": "FOOD",
                "c2.72": "Food",
                "c2.21": "Bodypt",
                "c2.75": "H4",
                "c2.119": "Noun",
                "c2.12": "Acad",
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "inq.txt"
            source.write_text(
                "Entry\tSource\tFood\tBodyPt\tAcadem\tOthtags\tDefined\n"
                "HAND#1\tH4\t\tBodyPt\tAcadem\tNoun\t\n"
                "APPLE\tH4\tFood\t\t\tNoun\t\n",
                encoding="utf-8",
            )
            result = add_general_inquirer(self.baseline(), source, codebook)
            counts = analyze_gcam("hand apple", lexicon=_load(result)).counts
            self.assertNotIn("c2.63", counts)
            self.assertEqual(counts["c2.72"], 1)
            self.assertEqual(counts["c2.21"], 1)
            self.assertEqual(counts["c2.75"], 2)
            self.assertEqual(counts["c2.119"], 2)
            self.assertEqual(counts["c2.12"], 1)

    def test_lemmatization_phrase_overlap_and_repeated_occurrences(self):
        lexicon = _load(
            {
                "name": "fixture",
                "exceptions": {"children": ["child"], "saw": ["see"]},
                "dimensions": [
                    {
                        "key": "c9.1",
                        "patterns": ["child", "child care"],
                        "lemmatization": "wordnet",
                    },
                    {"key": "c9.2", "words": ["see", "saw"], "lemmatization": "wordnet"},
                    {"key": "c9.3", "words": ["hospital"], "lemmatization": "wordnet"},
                    {"key": "c2.21", "words": ["child"]},
                ],
            }
        )
        counts = analyze_gcam("children care children saw hospitals child", lexicon=lexicon).counts
        self.assertEqual(counts, {"c9.1": 3, "c9.2": 1, "c9.3": 1, "c2.21": 1})
        with self.assertRaises(ValueError):
            _load(
                {
                    "name": "bad",
                    "dimensions": [
                        {"key": "c9.1", "patterns": ["child*"], "lemmatization": "wordnet"}
                    ],
                }
            )

    def test_roget_maps_full_paths_instead_of_printed_category_numbers(self):
        path1, path2 = "CLASS/1 GROUP/9 RELATION", "CLASS/1 GROUP/10 IRRELATION"
        codebook = self.codebook({"c9.1": path2, "c9.15": path1})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "roget.zip"
            with zipfile.ZipFile(source, "w") as archive:
                archive.writestr(
                    "ROGET.CAT",
                    "CLASS\n\t1 GROUP\n\t\t9 RELATION\n\t\t\tCHILD_CARE (1)\n"
                    "\t\t10 IRRELATION\n\t\t\tHAND (1)\n",
                )
            result = add_roget(self.baseline(), source, self.wordnet(root), codebook)
            counts = analyze_gcam("children care hand", lexicon=_load(result)).counts
            self.assertEqual(counts["c9.15"], 1)
            self.assertEqual(counts["c9.1"], 1)
            codebook["dimensions"]["c9.1"]["category"] = "wrong-path"
            with self.assertRaisesRegex(ValueError, "category paths"):
                add_roget(self.baseline(), source, self.wordnet(root), codebook)

    def test_wordnet_offsets_lexnames_hierarchy_and_missing_synsets(self):
        codebook = self.codebook(
            {
                "c17.3": "ADJ/PPL",
                "c17.5": "NOUN/ACT",
                "c15.1": "joy",
                "c15.2": "emotion",
                "c16.1": "health",
                "c16.2": "sport",
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            wn = self.wordnet(root)
            annotations = root / "annotations.zip"
            with zipfile.ZipFile(annotations, "w") as archive:
                archive.writestr(
                    "wn-domains-3.2-20070223",
                    "00000001-n health\n00000001-s health\n99999999-n sport\n",
                )
                archive.writestr(
                    "a-hierarchy.xml",
                    '<categ-list><categ name="emotion"/><categ name="joy" isa="emotion"/></categ-list>',
                )
                archive.writestr(
                    "a-synsets.xml",
                    '<syn-list><noun-syn-list><noun-syn id="n#00000001" categ="joy"/></noun-syn-list>'
                    '<adj-syn-list><adj-syn id="a#00000001" noun-id="n#00000001"/></adj-syn-list></syn-list>',
                )
            result = add_wordnet_lexical(self.baseline(), wn, codebook)
            result = add_wordnet_affect(result, annotations, wn, codebook, propagate_hierarchy=True)
            result = add_wordnet_domains(result, annotations, wn, codebook)
            counts = analyze_gcam("children amused", lexicon=_load(result)).counts
            self.assertEqual(counts["c17.3"], 1)
            self.assertEqual(counts["c17.5"], 1)
            self.assertEqual(counts["c15.1"], 2)
            self.assertEqual(counts["c15.2"], 2)
            self.assertEqual(counts["c16.1"], 2)
            self.assertNotIn("c16.2", counts)
            self.assertEqual(result["sources"]["wordnet-domains-3.2"]["missing_synsets"], 1)

    def test_theme_context_guards_repeats_and_span_deduplication(self):
        codebook = self.codebook({"c18.3": "PROTEST", "c18.4": "unsupported"})
        theme = ThemeLexicon(
            "fixture",
            (
                ThemeRule("PROTEST", "strike", requires_all=(("protest",),)),
                ThemeRule("PROTEST", "strike", requires_all=(("protest",),)),
            ),
        )
        result = add_themes(self.baseline(), codebook, theme)
        lexicon = _load(json.loads(json.dumps(result)))
        self.assertEqual(analyze_gcam("strike strike", lexicon=lexicon).counts["c18.3"], 0)
        self.assertEqual(analyze_gcam("protest strike strike", lexicon=lexicon).counts["c18.3"], 2)
        self.assertNotIn("c18.4", lexicon.dimensions)

    def test_local_codebook_counts_c_and_v_as_one_dimension(self):
        book = read_codebook()
        self.assertEqual(len(book["dimensions"]), 2989)
        self.assertEqual(len({key[1:] for key in book["dimensions"]}), 2888)

    def test_expanded_local_profile_preserves_previous_counts_and_scores(self):
        previous = _load(read_resource_json("lexicons", "gcam.v2.json"))
        payload = read_resource_json("lexicons", "gcam.v3.json.gz")
        expanded = _load(payload)
        self.assertEqual(len(expanded.dimensions), 809)
        for key, words in previous.dimensions.items():
            self.assertEqual(expanded.dimensions[key], words)
        self.assertEqual(expanded.weighted_dimensions, previous.weighted_dimensions)
        self.assertEqual(
            {key.split(".")[0] for key in expanded.dimensions},
            {"c2", "c15", "c16", "c17", "c18", "c26"},
        )
        text = "Good and bad people lost a hand. Hospitals feared a protest."
        old, new = analyze_gcam(text, lexicon=previous), analyze_gcam(text, lexicon=expanded)
        self.assertEqual(new.values, old.values)
        self.assertTrue(all(new.counts[k] == v for k, v in old.counts.items()))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json.gz"
            path.write_bytes(gzip.compress(json.dumps(payload).encode()))
            from gdelt_regkg.gcam import GCAMLexicon

            self.assertEqual(GCAMLexicon.from_json(path).name, expanded.name)


if __name__ == "__main__":
    unittest.main()
