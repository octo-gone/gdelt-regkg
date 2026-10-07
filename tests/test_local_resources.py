"""Resource routing and custom extraction without external dictionaries."""

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from gdelt_regkg import (
    GCAMLexicon,
    NERResult,
    ResourceUnavailableError,
    ThemeLexicon,
    ToneLexicon,
    analyze_counts,
    default_gcam_lexicon,
    generate_gkg,
)
from gdelt_regkg.counts import default_count_rules
from gdelt_regkg.locations import Gazetteer, default_gazetteer
from gdelt_regkg.ner import default_name_rules
from gdelt_regkg.scripts.build_resources import build_resources, download_source, revise_tone
from gdelt_regkg.themes import default_theme_lexicon
from gdelt_regkg.tone import default_tone_lexicon
from gdelt_regkg.utils import packaged_resource_path, resource_directory, resource_path


class LocalResourceTests(unittest.TestCase):
    def test_environment_cannot_change_directory_selection(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict("os.environ", {"GDELT_REGKG_RESOURCES": directory}),
        ):
            self.assertEqual(resource_directory(), Path("local-resources").resolve())
            self.assertEqual(resource_directory(directory), Path(directory).resolve())

    def test_custom_theme_loading_is_independent_of_count_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lexicons").mkdir()
            (root / "defaults.json").write_text(
                json.dumps({"themes": "custom-theme.json", "counts": "counts.bad.json"}),
                encoding="utf-8",
            )
            (root / "lexicons/custom-theme.json").write_text(
                json.dumps({"name": "custom", "themes": {"TOPIC": ["arbitrary"]}}), encoding="utf-8"
            )
            (root / "lexicons/counts.bad.json").write_text("invalid JSON", encoding="utf-8")
            self.assertEqual(default_theme_lexicon(root).name, "custom")

    def test_missing_profiles_fail_even_after_another_default_was_cached(self):
        with tempfile.TemporaryDirectory() as directory:
            for loader in (
                default_tone_lexicon,
                default_theme_lexicon,
                default_gcam_lexicon,
                default_gazetteer,
            ):
                with (
                    self.subTest(loader=loader.__name__),
                    self.assertRaisesRegex(ResourceUnavailableError, "gdelt-regkg-build-resources"),
                ):
                    loader(resources_dir=directory)
            self.assertIn(
                "KILL#12#people",
                analyze_counts("12 people killed", rules=default_count_rules(directory)).to_gkg(),
            )
            self.assertEqual(
                default_name_rules(directory).apply("president jane smith", "PERSON"), "jane smith"
            )

    def test_defaults_follow_resource_directory_and_custom_filenames(self):
        profiles = []
        with tempfile.TemporaryDirectory() as directory:
            for name, word in (("first", "hope"), ("second", "joy")):
                root = Path(directory) / name
                (root / "lexicons").mkdir(parents=True)
                payload = {
                    "name": name,
                    "positive": [word],
                    "negative": [],
                    "activity": [],
                    "self_group": [],
                }
                (root / "lexicons/tone-custom.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )
                (root / "defaults.json").write_text(
                    json.dumps({"tone": "tone-custom.json"}), encoding="utf-8"
                )
                lexicon = default_tone_lexicon(root)
                self.assertIs(lexicon, default_tone_lexicon(root))
                profiles.append(lexicon)
            self.assertEqual([p.name for p in profiles], ["first", "second"])
            self.assertEqual(profiles[0].positive, frozenset({"hope"}))
            self.assertEqual(profiles[1].positive, frozenset({"joy"}))

    def test_complete_pipeline_accepts_custom_objects_without_profile_setup(self):
        text = "Good news."
        with (
            tempfile.TemporaryDirectory() as directory,
            patch(
                "urllib.request.urlopen", side_effect=AssertionError("Extraction must be offline")
            ),
        ):
            record = generate_gkg(
                text,
                identifier="https://arbitrary.example/story",
                batch_time="20250101120000",
                sequence=1,
                resources_dir=directory,
                ner=NERResult(text, ()),
                tone_lexicon=ToneLexicon(
                    "custom", frozenset({"good"}), frozenset(), frozenset(), frozenset()
                ),
                theme_lexicon=ThemeLexicon.from_mapping({"CUSTOM_TOPIC": ["news"]}),
                gcam_lexicon=GCAMLexicon("custom", {"c1.1": frozenset({"news"})}),
                gazetteer=Gazetteer("empty", ()),
                sharing_image="",
                related_images=[],
                social_image_embeds=[],
                social_video_embeds=[],
                extras={},
                strict=True,
            )
        self.assertEqual(len(record), 27)
        self.assertEqual(record["V1THEMES"], "CUSTOM_TOPIC;")
        self.assertEqual(record["V2GCAM"], "wc:2,c1.1:1")

    def test_pipeline_loads_profiles_from_explicit_directory(self):
        text = "Good news."
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build_resources(root, fields=("counts", "ner"))
            profiles = {
                "tone.json": {
                    "name": "custom-tone",
                    "positive": ["good"],
                    "negative": [],
                    "activity": [],
                    "self_group": [],
                },
                "themes.json": {"name": "custom-theme", "themes": {"NEWS": ["news"]}},
                "gcam.json": {
                    "name": "custom-gcam",
                    "dimensions": [{"key": "c1.1", "words": ["news"]}],
                },
                "places.json": {"name": "empty-places", "places": []},
            }
            for name, payload in profiles.items():
                (root / "lexicons" / name).write_text(json.dumps(payload), encoding="utf-8")
            (root / "defaults.json").write_text(
                json.dumps(
                    {
                        "tone": "tone.json",
                        "themes": "themes.json",
                        "gcam": "gcam.json",
                        "locations": "places.json",
                    }
                ),
                encoding="utf-8",
            )
            record = generate_gkg(
                text,
                identifier="https://example.org",
                batch_time="20250101120000",
                sequence=1,
                resources_dir=root,
                ner=NERResult(text, ()),
                sharing_image="",
                related_images=[],
                social_image_embeds=[],
                social_video_embeds=[],
                extras={},
                strict=True,
            )
        self.assertEqual(record["V1THEMES"], "NEWS;")
        self.assertEqual(record["V2GCAM"], "wc:2,c1.1:1")
        self.assertTrue(record["V1.5TONE"].startswith("50,50,0,"))

    def test_authored_profiles_build_without_sources_and_override_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            built = build_resources(
                directory, fields=("themes", "counts", "ner"), authored_themes_only=True
            )
            self.assertNotIn("themes.v3.json", built)
            self.assertEqual(built["themes.authored.json"]["sources"], [])
            self.assertNotIn("external_rule_ids", built["themes.authored.json"])
            self.assertEqual(
                resource_path("lexicons", "themes.authored.json", resources_dir=directory).parent,
                Path(directory) / "lexicons",
            )
            self.assertEqual(default_theme_lexicon(directory).name, "authored-themes-v3")
            self.assertIn(
                "KILL#12#people",
                analyze_counts("12 people killed", rules=default_count_rules(directory)).to_gkg(),
            )

    def test_source_free_package_has_no_external_snapshots(self):
        for name in (
            "tone.v1.json",
            "tone.v2.json",
            "tone.v3.json",
            "themes.v1.json",
            "themes.v2.json",
            "themes.v3.json",
            "gcam.v1.json",
            "gcam.v2.json",
            "gcam.v3.json.gz",
            "locations.v1.json.gz",
        ):
            self.assertFalse(packaged_resource_path("lexicons", name).is_file(), name)
        self.assertFalse(packaged_resource_path("gcam", "codebook.v1.json").is_file())

    def test_explicit_download_verifies_archive_and_member_without_installing_code(self):
        member = b"synthetic vocabulary\n"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("dictionary.txt", member)
        raw = buffer.getvalue()
        entry = {
            "url": "https://example.org/source.zip",
            "archive_member": "dictionary.txt",
            "archive_sha256": hashlib.sha256(raw).hexdigest(),
            "sha256": hashlib.sha256(member).hexdigest(),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dictionary.txt"
            with patch(
                "gdelt_regkg.scripts.build_resources.urlopen", return_value=io.BytesIO(raw)
            ) as fetch:
                download_source(path, entry)
                download_source(path, entry)
                self.assertEqual(fetch.call_count, 1)
            self.assertEqual(path.read_bytes(), member)
            path.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum"):
                download_source(path, entry)

    def test_changed_download_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            with patch(
                "gdelt_regkg.scripts.build_resources.urlopen",
                return_value=io.BytesIO(b"changed"),
            ):
                with self.assertRaisesRegex(ValueError, "checksum"):
                    download_source(path, {"url": "https://example.org/source", "sha256": "wrong"})
            self.assertFalse(path.exists())

    def test_hashed_tone_exclusions_require_the_matching_term(self):
        baseline = {
            "source_sha256": "source",
            "positive": ["hope"],
            "negative": [],
            "activity": [],
            "self_group": [],
        }
        revision = {
            "base_source_sha256": "source",
            "metadata": {"name": "custom"},
            "changes": {
                key: {"add": [], "remove_sha256": []}
                for key in ("positive", "negative", "activity", "self_group")
            },
        }
        revision["changes"]["positive"]["remove_sha256"] = [hashlib.sha256(b"hope").hexdigest()]
        self.assertEqual(revise_tone(baseline, revision)["positive"], [])
        baseline["positive"] = []
        with self.assertRaisesRegex(ValueError, "unknown positive term hash"):
            revise_tone(baseline, revision)


if __name__ == "__main__":
    unittest.main()
