"""New public API, optional dependency and SQLite ownership contracts."""

import hashlib
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import gdelt_regkg
from gdelt_regkg import (
    GKG_COLUMNS,
    GKGRecord,
    IncompleteGKGError,
    OptionalDependencyError,
    RecordMetadata,
    Resources,
    generate_gkg,
)
from gdelt_regkg.benchmark.corpus import PredictionOptions
from gdelt_regkg.benchmark.storage import BenchmarkStore
from gdelt_regkg.cli.inputs import BuildOptions
from gdelt_regkg.dependencies import require_dependency
from gdelt_regkg.fields.counts import CountRules
from gdelt_regkg.fields.gcam import GCAMLexicon
from gdelt_regkg.fields.language import LinguaDetector, _confirmation_backend
from gdelt_regkg.fields.locations import Gazetteer, Place
from gdelt_regkg.fields.ner import EntityMention, NERResult, SpacyNER
from gdelt_regkg.fields.themes import ThemeLexicon
from gdelt_regkg.fields.tone import ToneLexicon
from gdelt_regkg.fields.translation import M2M100Translator, TranslationResult
from gdelt_regkg.pipeline import OVERRIDABLE_COLUMNS
from gdelt_regkg.record import FIELD_NAMES
from gdelt_regkg.translation_cache import CachedTranslator


class PublicContractTests(unittest.TestCase):
    def setUp(self):
        self.metadata = RecordMetadata(
            "https://example.org",
            "20250102120000",
            7,
            sharing_image="",
            related_images=[],
            social_image_embeds=[],
            social_video_embeds=[],
            extras={},
        )
        self.resources = Resources(
            count_rules=CountRules(
                name="test",
                triggers={"killed": "KILL"},
                active_triggers=("killed",),
                object_nouns=("people",),
                auxiliaries=("were",),
                unsafe_phrases=(),
                unsafe_suffixes=(),
                bad_object_words=(),
            ),
            tone_lexicon=ToneLexicon(
                "test", frozenset({"good"}), frozenset(), frozenset(), frozenset()
            ),
            theme_lexicon=ThemeLexicon.from_mapping({"NEWS": ["news"]}),
            gcam_lexicon=GCAMLexicon("test", {"c1.1": frozenset({"news"})}),
            gazetteer=Gazetteer("empty", ()),
        )

    def test_columns_follow_dataclass_and_canonical_wire_contract(self):
        canonical = (
            "GKGRECORDID V2.1DATE V2SOURCECOLLECTIONIDENTIFIER V2SOURCECOMMONNAME "
            "V2DOCUMENTIDENTIFIER V1COUNTS V2.1COUNTS V1THEMES V2ENHANCEDTHEMES "
            "V1LOCATIONS V2ENHANCEDLOCATIONS V1PERSONS V2ENHANCEDPERSONS "
            "V1ORGANIZATIONS V2ENHANCEDORGANIZATIONS V1.5TONE V2.1ENHANCEDDATES "
            "V2GCAM V2.1SHARINGIMAGE V2.1RELATEDIMAGES V2.1SOCIALIMAGEEMBEDS "
            "V2.1SOCIALVIDEOEMBEDS V2.1QUOTATIONS V2.1ALLNAMES V2.1AMOUNTS "
            "V2.1TRANSLATIONINFO V2EXTRASXML"
        ).split()
        self.assertEqual(GKG_COLUMNS, canonical)
        self.assertEqual(len(set(GKG_COLUMNS)), 27)
        self.assertEqual([f.metadata["column"] for f in fields(GKGRecord)], canonical)
        self.assertEqual(tuple(f.name for f in fields(GKGRecord)), FIELD_NAMES)

    def test_count_geography_survives_location_cell_overrides(self):
        text = "12 people were killed in London."
        place = Place("3", "London", "UK", "UKENG", "51.5", "-0.1", "london")
        resources = replace(self.resources, gazetteer=Gazetteer("test", (place,)))
        ner = NERResult(text, (EntityMention("London", "LOCATION", 25, 31),))
        original = generate_gkg(text, self.metadata, resources, ner_result=ner, strict=True)
        overridden = generate_gkg(
            text,
            self.metadata,
            resources,
            ner_result=ner,
            overrides={"V1LOCATIONS": "", "V2ENHANCEDLOCATIONS": ""},
            strict=True,
        )
        self.assertIn("#London#UK#", original.counts)
        self.assertEqual(overridden.counts, original.counts)
        self.assertEqual(overridden.enhanced_counts, original.enhanced_counts)
        self.assertEqual(overridden.locations, "")
        self.assertEqual(overridden.enhanced_locations, "")

    def test_translation_metadata_copy_english_and_conflicts(self):
        result = TranslationResult("original", "English body", "fra", "fixture")
        metadata = RecordMetadata.from_translation(result, self.metadata)
        self.assertIsNone(self.metadata.source_language)
        self.assertEqual(
            (metadata.source_language, metadata.translation_engine), ("fra", "fixture")
        )
        self.assertEqual(metadata.to_mapping()["GKGRECORDID"], "20250102120000-T7")
        self.assertEqual(RecordMetadata.from_translation(result, metadata), metadata)
        with self.assertRaises(ValueError):
            RecordMetadata.from_translation(
                result, replace(self.metadata, source_language="urd", translation_engine="other")
            )
        english = RecordMetadata.from_translation(
            TranslationResult("body", "body", "eng", None), self.metadata
        )
        self.assertEqual(english.to_mapping()["GKGRECORDID"], "20250102120000-7")
        with self.assertRaises(ValueError):
            RecordMetadata.from_translation(
                TranslationResult("body", "body", "eng", None), metadata
            )

    def test_record_is_frozen_and_precomputed_ner_wins(self):
        recognizer = Mock(analyze=Mock(side_effect=AssertionError("must use supplied result")))
        record = generate_gkg(
            "Good news",
            self.metadata,
            replace(self.resources, recognizer=recognizer),
            ner_result=NERResult("Good news", ()),
            strict=True,
        )
        self.assertIsInstance(record, GKGRecord)
        self.assertEqual(record.to_row(), tuple(record.to_mapping().values()))
        with self.assertRaises(FrozenInstanceError):
            record.tone = "changed"
        with self.assertRaises(ValueError):
            generate_gkg("other", self.metadata, self.resources, ner_result=NERResult("body", ()))

    def test_fully_overridden_fields_load_no_resources_or_model(self):
        record = generate_gkg(
            "body",
            self.metadata,
            Resources(
                resources_dir="missing-resource-directory",
                recognizer=Mock(analyze=Mock(side_effect=AssertionError("unused"))),
            ),
            overrides=dict.fromkeys(OVERRIDABLE_COLUMNS, ""),
            strict=True,
        )
        self.assertEqual(len(record.to_row()), 27)

    def test_incomplete_and_extractor_errors_are_distinct(self):
        with self.assertRaises(IncompleteGKGError):
            generate_gkg("body", self.metadata, self.resources, strict=True)
        with patch(
            "gdelt_regkg.pipeline.analyze_tone", side_effect=NotImplementedError("backend failure")
        ):
            with self.assertRaisesRegex(NotImplementedError, "backend failure"):
                generate_gkg("body", self.metadata, self.resources)

    def test_removed_api_is_absent_and_options_are_frozen(self):
        self.assertFalse(hasattr(gdelt_regkg, "ExtractionConfig"))
        self.assertFalse(hasattr(gdelt_regkg, "analyze_tone"))
        from gdelt_regkg import fields as field_modules

        self.assertFalse(hasattr(field_modules, "extract_tone"))
        with self.assertRaises(TypeError):
            generate_gkg("body", self.metadata, translator=object())
        build = BuildOptions(targets=["tone"])
        self.assertEqual(build.targets, ("tone",))
        with self.assertRaises(FrozenInstanceError):
            build.use = "v1"
        with self.assertRaises(ValueError):
            PredictionOptions(fields=("tone",), batch_size=True)


class OptionalDependencyTests(unittest.TestCase):
    def test_each_feature_has_the_same_error_contract(self):
        for module, extra in (
            ("spacy", "ner"),
            ("lingua", "lang"),
            ("transformers", "translate"),
            ("sentencepiece", "translate"),
            ("scipy", "benchmark"),
        ):
            with self.subTest(module=module), patch.dict("sys.modules", {module: None}):
                with self.assertRaisesRegex(
                    OptionalDependencyError, rf"install gdelt-regkg\[{extra}\]"
                ) as caught:
                    require_dependency(module, extra)
                self.assertIsInstance(caught.exception.__cause__, ImportError)
                self.assertNotIn("CPU/CUDA", str(caught.exception))
                self.assertNotIn("installation.md", str(caught.exception))

    def test_compute_backends_have_separate_installation_instructions(self):
        for module, command in (
            ("torch", "pip install torch --index-url https://download.pytorch.org/whl/cpu"),
            ("cupy", 'pip install "cupy-cuda12x[ctk]"'),
        ):
            with self.subTest(module=module), patch.dict("sys.modules", {module: None}):
                with self.assertRaises(OptionalDependencyError) as caught:
                    require_dependency(module, "translate" if module == "torch" else "ner")
                self.assertIn("installed separately", str(caught.exception))
                self.assertIn(command, str(caught.exception))
                self.assertNotIn("installation.md", str(caught.exception))

    def test_primary_and_secondary_lazy_imports(self):
        with patch.dict("sys.modules", {"spacy": None}):
            with self.assertRaises(OptionalDependencyError):
                SpacyNER.from_model()
        with patch.dict("sys.modules", {"lingua": None}):
            with self.assertRaises(OptionalDependencyError):
                LinguaDetector()
            _confirmation_backend.cache_clear()
            with self.assertRaises(OptionalDependencyError):
                _confirmation_backend("fra", "eng")
        with patch.dict("sys.modules", {"torch": SimpleNamespace(), "transformers": None}):
            with self.assertRaisesRegex(OptionalDependencyError, r"gdelt-regkg\[translate\]"):
                M2M100Translator.from_model()

    def test_direct_benchmark_api_reports_missing_extra(self):
        from gdelt_regkg.benchmark.metrics import numeric_metrics

        with patch.dict("sys.modules", {"scipy.stats": None}):
            with self.assertRaisesRegex(OptionalDependencyError, r"gdelt-regkg\[benchmark\]"):
                numeric_metrics([(1, 2)])


class SQLiteContractTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "translations.sqlite"

    @staticmethod
    def backend():
        return Mock(
            spec=["engine", "translate", "close"],
            engine="fixture",
            translate=Mock(side_effect=lambda text, language: "English " + text),
        )

    def test_scalar_batch_equivalence_and_english_bypass_in_both_orders(self):
        for batch_first in (False, True):
            backend = self.backend()
            with CachedTranslator(backend, ":memory:") as cache:
                methods = [
                    lambda: cache.translate("English", "eng"),
                    lambda: cache.translate_many(["English"], "en")[0],
                ]
                if batch_first:
                    methods.reverse()
                self.assertEqual([call() for call in methods], ["English", "English"])
                backend.translate.assert_not_called()
                self.assertEqual(cache.translate("body", "fr"), "English body")
                self.assertEqual(
                    cache.translate_many(["body", "other", "body"], "fra"),
                    ["English body", "English other", "English body"],
                )
                self.assertEqual(backend.translate.call_count, 2)

    def test_namespace_bypasses_old_entries(self):
        backend = self.backend()
        with CachedTranslator(backend, self.path) as cache:
            old_key = hashlib.sha256("fixture\0fra\0body".encode()).hexdigest()
            cache.connection.execute(
                "INSERT INTO translations VALUES (?, ?)", (old_key, "old incorrect output")
            )
            cache.connection.commit()
            self.assertEqual(cache.translate("body", "fra"), "English body")

    def test_wal_timeout_ownership_close_and_rollback(self):
        backend = self.backend()
        cache = CachedTranslator(backend, self.path, timeout=0.025)
        connection = cache.connection
        self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], 25)
        connection.execute("INSERT INTO translations VALUES ('pending', 'discard')")
        cache.close()
        cache.close()
        backend.close.assert_not_called()
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")
        with CachedTranslator(backend, self.path) as reopened:
            self.assertEqual(
                reopened.connection.execute("SELECT COUNT(*) FROM translations").fetchone()[0], 0
            )
        with self.assertRaises(RuntimeError):
            cache.translate("body", "fra")

    def test_context_failure_and_invalid_output_do_not_persist(self):
        with self.assertRaisesRegex(RuntimeError, "failure"):
            with CachedTranslator(self.backend(), self.path) as cache:
                connection = cache.connection
                connection.execute("INSERT INTO translations VALUES ('pending', 'discard')")
                raise RuntimeError("failure")
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")
        invalid = Mock(
            spec=["engine", "translate_many"],
            engine="fixture",
            translate_many=Mock(return_value=[""]),
        )
        with CachedTranslator(invalid, self.path) as cache:
            with self.assertRaises(ValueError):
                cache.translate_many(["body"], "fra")
            self.assertEqual(
                cache.connection.execute("SELECT COUNT(*) FROM translations").fetchone()[0], 0
            )

    def test_independent_thread_connections_can_share_a_cache(self):
        with CachedTranslator(self.backend(), self.path):
            pass

        def worker(index):
            with CachedTranslator(self.backend(), self.path) as cache:
                return [cache.translate(f"body-{index}-{i}", "fra") for i in range(5)]

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, range(2)))
        self.assertEqual(len(results), 2)
        with CachedTranslator(self.backend(), self.path) as cache:
            self.assertEqual(
                cache.connection.execute("SELECT COUNT(*) FROM translations").fetchone()[0], 10
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                with self.assertRaises(sqlite3.ProgrammingError):
                    pool.submit(cache.connection.execute, "SELECT 1").result()

    def test_write_timeout_and_benchmark_lock_cleanup(self):
        with (
            CachedTranslator(self.backend(), self.path, timeout=0.01) as first,
            CachedTranslator(self.backend(), self.path, timeout=0.01) as second,
        ):
            first.connection.execute("BEGIN IMMEDIATE")
            with self.assertRaises(sqlite3.OperationalError):
                second.translate("body", "fra")
            self.assertFalse(second.connection.in_transaction)
            first.connection.rollback()
            self.assertEqual(second.translate("body", "fra"), "English body")
        path = self.path.with_name("benchmark.sqlite")
        with self.assertRaisesRegex(RuntimeError, "failure"):
            with BenchmarkStore(path, timeout=0.025) as store:
                connection = store.db
                self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], "wal")
                self.assertEqual(connection.execute("PRAGMA busy_timeout").fetchone()[0], 25)
                raise RuntimeError("failure")
        store.close()
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")
        with BenchmarkStore(path):
            pass

    def test_invalid_timeouts_and_native_memory_journal(self):
        for timeout in (-1, float("nan"), True):
            with self.assertRaises(ValueError):
                CachedTranslator(self.backend(), ":memory:", timeout=timeout)
        with CachedTranslator(self.backend(), ":memory:") as cache:
            self.assertEqual(
                cache.connection.execute("PRAGMA journal_mode").fetchone()[0], "memory"
            )

    def test_benchmark_reentry_and_foreign_database_are_safe(self):
        path = self.path.with_name("benchmark.sqlite")
        with BenchmarkStore(path) as store:
            with self.assertRaisesRegex(RuntimeError, "already open"):
                store.__enter__()
            self.assertEqual(store.db.execute("SELECT 1").fetchone()[0], 1)
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("CREATE TABLE owned_data(value TEXT)")
            connection.commit()
            before = connection.execute("PRAGMA journal_mode").fetchone()[0]
        with self.assertRaises(ValueError):
            with BenchmarkStore(self.path):
                pass
        with closing(sqlite3.connect(self.path)) as connection:
            self.assertEqual(connection.execute("PRAGMA journal_mode").fetchone()[0], before)
