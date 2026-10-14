"""Exercise recipe selection, output labels and complete GCAM builds offline."""

import contextlib
import csv
import gzip
import io
import json
import tarfile
import unittest
import zipfile
from unittest.mock import patch

from jsonschema import Draft202012Validator
from test_cli import WorkspaceTests

from gdelt_regkg.builders.gcam_lexicon import CATEGORIES, LEXICODER_CATEGORIES
from gdelt_regkg.builders.themes import build_profile, merge_inputs, restore_crisislex
from gdelt_regkg.builders.tone import build_lexicon, revise_tone
from gdelt_regkg.cli import main
from gdelt_regkg.cli.gcam import GCAMOptions
from gdelt_regkg.cli.inputs import BuildOptions, required_sources, resolve_inputs
from gdelt_regkg.cli.validation import semantic_sha256
from gdelt_regkg.fields.gcam import _load, analyze_gcam, default_gcam_lexicon, read_gcam_json
from gdelt_regkg.fields.rule_inputs import THEME_SCHEMA
from gdelt_regkg.utils import read_resource_json


class RecipeTests(WorkspaceTests):
    def run_build(self, *arguments):
        with (
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
            patch(
                "gdelt_regkg.cli.sources.urlopen", side_effect=AssertionError("Unexpected network")
            ),
        ):
            main(["build", *map(str, arguments)])

    def test_counts_each_recipe_produces_only_one_profile(self):
        for recipe in ("best", "v1", "v2", "v3"):
            with self.subTest(recipe=recipe):
                output = self.root / recipe
                self.run_build("counts", "--use", recipe, "--suffix", "chosen", "--output", output)
                profiles = list((output / "lexicons").iterdir())
                self.assertEqual([p.name for p in profiles], ["counts.chosen.json"])
                version = "v3" if recipe == "best" else recipe
                self.assertEqual(
                    json.loads(profiles[0].read_text()),
                    read_resource_json("counts", f"rules.{version}.json"),
                )
                self.assertEqual(
                    json.loads((output / "defaults.json").read_text()),
                    {"counts": "counts.chosen.json"},
                )

    def test_suffix_does_not_select_recipe_or_change_payload(self):
        self.run_build("counts", "--output", self.root / "default")
        self.run_build("counts", "--suffix", "v1", "--output", self.root / "relabeled")
        self.assertEqual(
            (self.root / "default/lexicons/counts.v3.json").read_bytes(),
            (self.root / "relabeled/lexicons/counts.v1.json").read_bytes(),
        )

    def test_explicit_history_preserves_files_and_selects_last_requested(self):
        self.run_build("ner", "--output", self.root)
        for recipe in ("v1", "v2", "v3"):
            self.run_build("counts", "--use", recipe, "--output", self.root)
        self.assertEqual(
            {p.name for p in (self.root / "lexicons").iterdir()},
            {"names.v1.json", "counts.v1.json", "counts.v2.json", "counts.v3.json"},
        )
        self.assertEqual(
            json.loads((self.root / "defaults.json").read_text()),
            {"ner": "names.v1.json", "counts": "counts.v3.json"},
        )

    def test_invalid_selection_is_rejected_before_download_or_writes(self):
        for arguments in (
            (),
            ("counts", "--use", "unknown"),
            ("ner", "--use", "v3"),
            ("all", "--use", "v2"),
            ("all", "counts"),
            ("counts", "--suffix", "../escape"),
            ("counts", "--suffix", ""),
            ("counts", "--suffix", "bad:name"),
            ("locations", "--suffix", "test", "--gazetteer-filename", "locations.json"),
            ("gcam", "--use", "v1", "--gcam-baseline", "missing.json"),
        ):
            with (
                self.subTest(arguments=arguments),
                contextlib.redirect_stderr(io.StringIO()),
                patch("gdelt_regkg.cli.inputs.download_source") as download,
                self.assertRaises(SystemExit) as error,
            ):
                main(
                    [
                        "build",
                        *arguments,
                        "--sources-dir",
                        str(self.root),
                        "--download-sources",
                        "--output",
                        str(self.root / "out"),
                    ]
                )
            self.assertEqual(error.exception.code, 2)
            download.assert_not_called()
            self.assertFalse((self.root / "out").exists())

    def test_authored_recipe_requires_no_source_and_writes_one_profile(self):
        self.run_build("themes", "--use", "authored", "--suffix", "custom", "--output", self.root)
        self.assertEqual(
            [p.name for p in (self.root / "lexicons").iterdir()], ["themes.custom.json"]
        )
        self.assertEqual(
            json.loads((self.root / "lexicons/themes.custom.json").read_text())["sources"], []
        )

    def tone_revisions(self, source):
        baseline = build_lexicon(source)
        revisions = {}
        for version, category, word in ((2, "positive", "hope"), (3, "negative", "worry")):
            edits = {
                "base_source_sha256": baseline["source_sha256"],
                "base_dictionary_sha256": semantic_sha256(baseline),
                "metadata": {
                    "$schema": "../schemas/tone-lexicon.schema.json",
                    "name": f"fixture-tone-v{version}",
                    "source_sha256": baseline["source_sha256"],
                },
                "changes": {
                    key: {"add": [word] if key == category else []}
                    for key in ("positive", "negative", "activity", "self_group")
                },
            }
            revisions["tone", f"v{version}-edits.json"] = edits
            baseline = revise_tone(baseline, edits)
        return revisions

    def fixture_resource_reader(self, replacements):
        def read(*parts):
            if parts in replacements:
                return replacements[parts]
            return read_resource_json(*parts)

        return read

    def test_tone_recipe_replay_builds_only_the_requested_profile(self):
        source = self.fixture_sources()["general-inquirer"]
        revisions = self.tone_revisions(source)
        for recipe in ("v1", "v2", "v3"):
            output = self.root / recipe
            with patch(
                "gdelt_regkg.cli.profiles.read_resource_json",
                side_effect=self.fixture_resource_reader(revisions),
            ):
                self.run_build(
                    "tone",
                    "--use",
                    recipe,
                    "--source",
                    f"general-inquirer={source}",
                    "--output",
                    output,
                )
            self.assertEqual(
                [p.name for p in (output / "lexicons").iterdir()], [f"tone.{recipe}.json"]
            )
            payload = json.loads((output / f"lexicons/tone.{recipe}.json").read_text())
            self.assertEqual(payload["positive"], ["hand"] if recipe == "v1" else ["hand", "hope"])
            self.assertEqual(payload["negative"], ["hand", "worry"] if recipe == "v3" else ["hand"])

    def test_theme_recipe_replay_builds_only_the_requested_profile(self):
        source = self.root / "crisislex.txt"
        source.write_text("flood\n", encoding="utf-8")
        candidates = {
            "schema": THEME_SCHEMA,
            "name": "fixture-candidates",
            "sources": build_profile(crisislex=source, name="fixture")["sources"],
            "rules": [],
        }
        seed = {
            "schema": THEME_SCHEMA,
            "name": "fixture-seed",
            "sources": [],
            "rules": [
                {
                    "id": "seed",
                    "kind": "literal",
                    "expression": "rescue",
                    "labels": ["RESCUE"],
                    "status": "enabled",
                }
            ],
        }
        baseline = merge_inputs(
            [restore_crisislex(candidates, source), seed], name="gdelt-theme-candidates-v3"
        )
        baseline["$schema"] = "../schemas/theme-rules.schema.json"
        revision = {
            "schema": THEME_SCHEMA,
            "name": "fixture-themes-v3",
            "base_sha256": semantic_sha256(baseline),
            "evaluation": {},
            "rules": [
                {
                    "id": "revision",
                    "kind": "literal",
                    "expression": "evacuate",
                    "labels": ["EVACUATION"],
                    "status": "enabled",
                }
            ],
        }
        replacements = {
            ("themes", "themes-count-candidates-v2.json"): candidates,
            ("themes", "theme_seeds.json"): seed,
            ("themes", "revision.v3.json"): revision,
        }
        for recipe in ("v1", "v2", "v3"):
            output = self.root / recipe
            with patch(
                "gdelt_regkg.cli.profiles.read_resource_json",
                side_effect=self.fixture_resource_reader(replacements),
            ):
                self.run_build(
                    "themes", "--use", recipe, "--source", f"crisislex={source}", "--output", output
                )
            self.assertEqual(
                [p.name for p in (output / "lexicons").iterdir()], [f"themes.{recipe}.json"]
            )
            payload = json.loads((output / f"lexicons/themes.{recipe}.json").read_text())
            expected = {"flood"}
            if recipe != "v1":
                expected.add("rescue")
            if recipe == "v3":
                expected.add("evacuate")
            self.assertEqual({rule["expression"] for rule in payload["rules"]}, expected)

    def fixture_sources(self):
        source = self.root / "gi.tsv"
        headers = list(
            dict.fromkeys(
                [
                    "Entry",
                    "Source",
                    "Othtags",
                    "Positiv",
                    "Negativ",
                    "Active",
                    "Self",
                    "Our",
                    "You",
                    *CATEGORIES.values(),
                ]
            )
        )
        with source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers, delimiter="\t")
            writer.writeheader()
            writer.writerow(
                dict.fromkeys(headers, "HAND")
                | {"Entry": "HAND", "Source": "H4", "Othtags": "PRON"}
            )
        vader = self.root / "vader.tsv"
        vader.write_text("good\t2.0\nbad\t-2.0\n")
        lexicoder = self.root / "lexicoder.json"
        lexicoder.write_text(
            json.dumps(
                {
                    name: ["bad*" if "negative" in name else "good*"]
                    for name in LEXICODER_CATEGORIES.values()
                }
            )
        )
        wordnet = self.root / "wordnet.tar.gz"
        with tarfile.open(wordnet, "w:gz") as archive:
            for pos, number, word in (
                ("noun", 4, "child"),
                ("adj", 44, "amused(p)"),
                ("verb", 37, "love"),
                ("adv", 2, "happily"),
            ):
                for filename, raw in (
                    (
                        "data." + pos,
                        f"00000001 {number:02d} {pos[0]} 01 {word} 0 000 | fixture\n".encode(),
                    ),
                    (pos + ".exc", b"children child\n" if pos == "noun" else b""),
                ):
                    member = tarfile.TarInfo("dict/" + filename)
                    member.size = len(raw)
                    archive.addfile(member, io.BytesIO(raw))
        annotations = self.root / "annotations.zip"
        with zipfile.ZipFile(annotations, "w") as archive:
            archive.writestr("wn-domains-3.2-20070223", "00000001-n health\n00000001-s health\n")
            archive.writestr(
                "a-hierarchy.xml",
                '<categ-list><categ name="emotion"/><categ name="joy" isa="emotion"/></categ-list>',
            )
            archive.writestr(
                "a-synsets.xml",
                '<syn-list><noun-syn-list><noun-syn id="n#00000001" categ="joy"/></noun-syn-list><adj-syn-list><adj-syn id="a#00000001" noun-id="n#00000001"/></adj-syn-list></syn-list>',
            )
        roget = self.root / "roget.zip"
        with zipfile.ZipFile(roget, "w") as archive:
            archive.writestr(
                "ROGET.CAT", "CLASS\n\t1 GROUP\n\t\t9 RELATION\n\t\t\tCHILD_CARE (1)\n"
            )
        categories = CATEGORIES | {
            "c9.1": "CLASS/1 GROUP/9 RELATION",
            "c15.1": "joy",
            "c15.2": "emotion",
            "c16.1": "health",
            "c17.3": "ADJ/PPL",
            "c17.5": "NOUN/ACT",
            "c18.3": "PROTEST",
        }
        codebook = self.root / "codebook.tsv"
        with codebook.open("w", encoding="latin1", newline="") as stream:
            writer = csv.writer(stream, delimiter="\t")
            writer.writerow(
                [
                    "Variable",
                    "DictionaryID",
                    "DimensionID",
                    "DimensionHumanName",
                    "DictionaryHumanName",
                    "LanguageCode",
                    "Type",
                ]
            )
            for key, category in categories.items():
                family, dimension = key[1:].split(".")
                writer.writerow([key, family, dimension, category, "fixture", "eng", "count"])
        return {
            "general-inquirer": source,
            "vader": vader,
            "lexicoder": lexicoder,
            "wordnet-31": wordnet,
            "wordnet-20": wordnet,
            "wordnet-16": wordnet,
            "wordnet-annotations": annotations,
            "roget": roget,
            "codebook": codebook,
        }

    def source_args(self, sources):
        return [
            argument
            for name, path in sources.items()
            for argument in ("--source", f"{name}={path}")
        ]

    def test_gcam_v1_v2_resolve_only_their_inputs_and_emit_one_profile(self):
        sources = self.fixture_sources()
        for recipe, names in (("v1", ("general-inquirer",)), ("v2", ("general-inquirer", "vader"))):
            output = self.root / recipe
            selected = {name: sources[name] for name in names}
            self.run_build("gcam", "--use", recipe, *self.source_args(selected), "--output", output)
            filename = f"gcam.{recipe}.json"
            self.assertEqual([p.name for p in (output / "lexicons").iterdir()], [filename])
            self.assertFalse((output / "gcam").exists())
            lexicon = _load(read_gcam_json(output / "lexicons" / filename))
            self.assertEqual(bool(lexicon.weighted_dimensions), recipe == "v2")
            self.assertEqual(len(lexicon.dimensions), len(CATEGORIES) + (recipe == "v2"))

    def test_tone_v1_imports_custom_source_without_attempting_later_revisions(self):
        source = self.fixture_sources()["general-inquirer"]
        with patch(
            "gdelt_regkg.cli.profiles.revise_tone",
            side_effect=AssertionError("Unexpected revision"),
        ):
            self.run_build(
                "tone",
                "--use",
                "v1",
                "--source",
                f"general-inquirer={source}",
                "--suffix",
                "custom",
                "--output",
                self.root / "out",
            )
        self.assertEqual(
            [p.name for p in (self.root / "out/lexicons").iterdir()], ["tone.custom.json"]
        )
        profile = json.loads((self.root / "out/lexicons/tone.custom.json").read_text())
        self.assertEqual(profile["positive"], ["hand"])

    def test_all_explicitly_builds_one_profile_per_target_with_shared_suffix(self):
        sources = {
            name: path
            for name, path in self.fixture_sources().items()
            if name not in ("roget", "lexicoder")
        }
        archive = self.root / "reference.zip"
        with zipfile.ZipFile(archive, "w") as stream:
            stream.writestr("reference.csv", "")
        revisions = self.tone_revisions(sources["general-inquirer"])
        output = self.root / "out"
        with patch(
            "gdelt_regkg.cli.profiles.read_resource_json",
            side_effect=self.fixture_resource_reader(revisions),
        ):
            self.run_build(
                "all",
                "--authored-themes-only",
                *self.source_args(sources),
                "--gazetteer-archives",
                archive,
                "--suffix",
                "selected",
                "--output",
                output,
            )
        defaults = json.loads((output / "defaults.json").read_text())
        self.assertEqual(set(defaults), {"tone", "themes", "counts", "ner", "locations", "gcam"})
        self.assertEqual({p.name for p in (output / "lexicons").iterdir()}, set(defaults.values()))
        self.assertEqual(len(defaults), 6)
        self.assertTrue(all((".selected.json" in filename for filename in defaults.values())))

    def test_standard_and_full_gcam_with_real_converters_and_baseline_expansion(self):
        sources = self.fixture_sources()
        standard_sources = {
            key: value for key, value in sources.items() if key not in ("roget", "lexicoder")
        }
        standard = self.root / "standard"
        self.run_build(
            "gcam",
            "--authored-themes-only",
            *self.source_args(standard_sources),
            "--output",
            standard,
        )
        payload = read_gcam_json(standard / "lexicons/gcam.v3.json.gz")
        counts = analyze_gcam("children amused good hand", lexicon=_load(payload)).counts
        self.assertEqual(counts["c15.1"], 2)
        self.assertEqual(counts["c16.1"], 2)
        self.assertEqual(counts["c17.5"], 1)
        self.assertEqual(counts["c2.21"], 1)
        full = self.root / "full"
        self.run_build(
            "gcam",
            "--use",
            "full",
            "--authored-themes-only",
            *self.source_args(sources),
            "--output",
            full,
        )
        complete = read_gcam_json(full / "lexicons/gcam.full.json.gz")
        selected = default_gcam_lexicon(full)
        self.assertEqual(set(selected.dimensions), set(_load(complete).dimensions))
        self.assertTrue({"c3.1", "c9.1"} <= selected.dimensions.keys())
        Draft202012Validator(read_resource_json("schemas", "gcam-lexicon.schema.json")).validate(
            complete
        )
        self.assertEqual(
            {key.split(".")[0] for key in _load(complete).dimensions},
            {"c2", "c3", "c9", "c15", "c16", "c17", "c18", "c26"},
        )
        self.assertEqual([p.name for p in (full / "lexicons").iterdir()], ["gcam.full.json.gz"])
        additions = {
            name: sources[name] for name in ("roget", "lexicoder", "wordnet-31", "codebook")
        }
        self.run_build(
            "gcam",
            "--gcam-baseline",
            standard / "lexicons/gcam.v3.json.gz",
            "--gcam-add",
            "roget",
            "lexicoder",
            *self.source_args(additions),
            "--suffix",
            "full",
            "--output",
            standard,
        )
        expanded = read_gcam_json(standard / "lexicons/gcam.full.json.gz")
        self.assertEqual(
            sorted(expanded["dimensions"], key=lambda d: d["key"]),
            sorted(complete["dimensions"], key=lambda d: d["key"]),
        )
        self.assertEqual(
            json.loads((standard / "defaults.json").read_text()), {"gcam": "gcam.full.json.gz"}
        )

    def test_replacing_vader_and_lexicoder_preserves_other_baseline_dimensions(self):
        sources = self.fixture_sources()
        base = self.root / "baseline.json"
        base.write_text(
            json.dumps(
                {
                    "name": "fixture",
                    "dimensions": [
                        {"key": "c1.1", "words": ["keep"]},
                        {"key": "v26.1", "scores": {"old": 1}},
                        *({"key": key, "patterns": ["old"]} for key in LEXICODER_CATEGORIES),
                    ],
                }
            )
        )
        additions = {name: sources[name] for name in ("vader", "lexicoder")}
        self.run_build(
            "gcam",
            "--gcam-baseline",
            base,
            "--gcam-add",
            "vader",
            "lexicoder",
            *self.source_args(additions),
            "--suffix",
            "new",
            "--output",
            self.root / "out",
        )
        lexicon = _load(read_gcam_json(self.root / "out/lexicons/gcam.new.json.gz"))
        self.assertEqual(lexicon.dimensions["c1.1"], {"keep"})
        self.assertNotIn("old", lexicon.weighted_dimensions["v26.1"])
        self.assertEqual(lexicon.weighted_dimensions["v26.1"]["good"], 2)

    def test_affect_variant_flags_and_gzip_suffix(self):
        sources = self.fixture_sources()
        selected = {
            name: sources[name]
            for name in ("general-inquirer", "wordnet-annotations", "wordnet-16", "codebook")
        }
        self.run_build(
            "gcam",
            "--use",
            "v1",
            "--gcam-add",
            "wordnet-affect",
            "--affect-propagate-hierarchy",
            "--affect-nouns-only",
            *self.source_args(selected),
            "--suffix",
            "affect",
            "--output",
            self.root / "out",
        )
        payload = read_gcam_json(self.root / "out/lexicons/gcam.affect.json.gz")
        counts = analyze_gcam("children amused", lexicon=_load(payload)).counts
        self.assertEqual(counts["c15.1"], 1)
        self.assertEqual(counts["c15.2"], 1)
        self.assertTrue(payload["sources"]["wordnet-affect-1.1"]["nouns_only"])
        additions = {name: path for name, path in selected.items() if name != "general-inquirer"}
        self.run_build(
            "gcam",
            "--gcam-baseline",
            self.root / "out/lexicons/gcam.affect.json.gz",
            "--gcam-add",
            "wordnet-affect",
            *self.source_args(additions),
            "--suffix",
            "direct",
            "--output",
            self.root / "out",
        )
        direct = _load(read_gcam_json(self.root / "out/lexicons/gcam.direct.json.gz"))
        self.assertNotIn("c15.2", direct.dimensions)
        self.assertEqual(analyze_gcam("children amused", lexicon=direct).counts["c15.1"], 2)

    def test_custom_gazetteer_uses_suffix_and_name(self):
        archive = self.root / "reference.zip"
        cells = [""] * 27
        cells[10] = "4#Paris, France#FR#A8##48.85#2.35#-1456928#0"
        with zipfile.ZipFile(archive, "w") as stream:
            stream.writestr("reference.csv", "\t".join(cells) + "\n")
        self.run_build(
            "locations",
            "--gazetteer-archives",
            archive,
            "--gazetteer-name",
            "my-places",
            "--suffix",
            "custom",
            "--output",
            self.root / "out",
        )
        payload = json.loads(
            gzip.decompress((self.root / "out/lexicons/locations.custom.json.gz").read_bytes())
        )
        self.assertEqual(payload["name"], "my-places")
        self.assertEqual(payload["places"][0]["full_name"], "Paris, France")


if __name__ == "__main__":
    unittest.main()
