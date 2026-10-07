import io
import unittest
import warnings
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from gdelt_regkg import (
    GKG_COLUMNS,
    IncompleteGKGWarning,
    fields,
    generate_gkg,
    serialize_gkg,
    write_gkg,
)


class FieldTests(unittest.TestCase):
    def test_dates_and_local_record_ids(self):
        instant = datetime(2026, 10, 1, 12, tzinfo=timezone(timedelta(hours=3)))
        self.assertEqual(fields.format_date(instant), "20261001090000")
        self.assertEqual(fields.format_date(None), "0")
        self.assertEqual(fields.format_record_id(instant, 5, translated=True), "20261001090000-T5")
        for value in ("20260230000000", "20261001", True, float("nan")):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                fields.format_date(value)
        for sequence in (0, -1, 1.5, True):
            with self.subTest(sequence=sequence), self.assertRaises(ValueError):
                fields.format_record_id(instant, sequence)

    def test_source_and_translation(self):
        self.assertEqual(
            fields.source_common_name("https://NEWS.example.org:443/a"), "news.example.org"
        )
        self.assertEqual(
            fields.source_common_name("offline citation", name="Print Daily"), "Print Daily"
        )
        self.assertEqual(fields.format_source_collection(5), "5")
        with self.assertRaises(ValueError):
            fields.format_source_collection(7)
        self.assertEqual(fields.format_translation_info(), "")
        self.assertEqual(
            fields.format_translation_info("fra", "Example engine"), "srclc:fra;eng:Example engine"
        )
        self.assertEqual(
            fields.format_related_images(["https://example.org/a;b?x=1;2#part"]),
            "https://example.org/a%3Bb?x=1%3B2#part",
        )
        with self.assertRaises(ValueError):
            fields.format_translation_info("fra")
        with self.assertRaises(ValueError):
            fields.document_identifier("url\tbroken")

    def test_supplied_media_urls_and_missing_metadata(self):
        url = "https://example.org/photo.jpg?a=1&b=2"
        self.assertEqual(fields.format_sharing_image(url), url)
        self.assertEqual(fields.format_sharing_image(""), "")
        self.assertIsNone(fields.format_sharing_image(None))
        for value in (
            "/photo.jpg",
            "javascript:bad",
            "<meta property='og:image'>",
            "https://example.org/a b",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                fields.format_sharing_image(value)
        for formatter in (
            fields.format_related_images,
            fields.format_social_image_embeds,
            fields.format_social_video_embeds,
        ):
            with self.subTest(formatter=formatter.__name__):
                self.assertIsNone(formatter(None))
                self.assertEqual(formatter([]), "")
                self.assertEqual(formatter(u for u in (url, url)), f"{url};{url}")
                with self.assertRaises(TypeError):
                    formatter(url)
                self.assertEqual(
                    formatter(["https://example.org/a;b"]), "https://example.org/a%3Bb"
                )

    def test_locations_accept_precomputed_spans(self):
        from gdelt_regkg import EntityMention, NERResult

        text = "Jane spoke in London."
        ner = NERResult(text, (EntityMention("London", "LOCATION", 14, 20),))
        self.assertIn("#UK#", fields.extract_locations(text, ner=ner))


class PipelineTests(unittest.TestCase):
    def record(self, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            return generate_gkg(
                "Example text.",
                identifier="https://example.org/a",
                batch_time="20261001091500",
                sequence=1,
                **kwargs,
            )

    def test_wire_order_and_empty_trailing_fields(self):
        record = self.record()
        self.assertEqual(len(record), 27)
        self.assertEqual(list(record), GKG_COLUMNS)
        self.assertEqual(record["GKGRECORDID"], "20261001091500-1")
        self.assertEqual(record["V2.1DATE"], "20261001091500")
        with self.assertRaises(ValueError):
            serialize_gkg(record)
        line = serialize_gkg(record, allow_incomplete=True)
        cells = line.removesuffix("\n").split("\t")
        self.assertEqual(len(cells), 27)
        self.assertEqual(
            cells[:5],
            ["20261001091500-1", "20261001091500", "1", "example.org", "https://example.org/a"],
        )
        self.assertEqual(cells[-1], "")
        stream = io.StringIO()
        self.assertEqual(write_gkg(iter([record, record]), stream, allow_incomplete=True), 2)
        self.assertEqual(stream.getvalue(), line * 2)

    def test_precise_publication_time_is_separate_from_batch_date(self):
        first = self.record(published_at="20261001090023")
        second = self.record(published_at="20261001091459")
        self.assertEqual(first["V2.1DATE"], second["V2.1DATE"])
        self.assertEqual(first["V2.1DATE"], "20261001091500")
        self.assertEqual(
            first["V2EXTRASXML"],
            "<PAGE_PRECISEPUBTIMESTAMP>20261001090023</PAGE_PRECISEPUBTIMESTAMP>",
        )
        extras = {"PAGE_TITLE": "Title", "PAGE_PRECISEPUBTIMESTAMP": "20261001085959"}
        record = self.record(published_at="20261001090023", extras=extras)
        self.assertIn(
            "<PAGE_PRECISEPUBTIMESTAMP>20261001085959</PAGE_PRECISEPUBTIMESTAMP>",
            record["V2EXTRASXML"],
        )
        self.assertEqual(len(extras), 2)
        self.assertIsNone(self.record(published_at="0")["V2EXTRASXML"])
        overridden = self.record(published_at="20261001090023", field_values={"V2EXTRASXML": ""})
        self.assertEqual(overridden["V2EXTRASXML"], "")

    def test_overrides_and_strict_mode(self):
        record = self.record(field_values={"V1PERSONS": "Jane"})
        self.assertEqual(record["V1PERSONS"], "Jane")
        self.assertIsNone(record["V2ENHANCEDPERSONS"])
        with self.assertRaises(NotImplementedError):
            self.record(strict=True)
        supplied = {column: "" for column, value in record.items() if value is None}
        supplied["V1PERSONS"] = "Jane"
        complete = self.record(field_values=supplied, strict=True)
        self.assertNotIn(None, complete.values())
        self.assertIn("Jane", serialize_gkg(complete))
        with self.assertRaises(ValueError):
            self.record(field_values={"TYPO": "x"})

    def test_warning_and_real_errors(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            generate_gkg(
                "",
                identifier="https://example.org",
                published_at=None,
                batch_time="20261001091500",
                sequence=1,
            )
        self.assertEqual(len(caught), 1)
        self.assertIs(caught[0].category, IncompleteGKGWarning)
        with patch.object(fields, "extract_tone", side_effect=RuntimeError("model failed")):
            with self.assertRaisesRegex(RuntimeError, "model failed"):
                self.record()

    def test_prepared_media_metadata_and_override_precedence(self):
        record = self.record(
            sharing_image="https://example.org/photo.jpg",
            related_images=iter(["https://example.org/one.jpg", "https://example.org/two.jpg"]),
            social_image_embeds=[],
            social_video_embeds=["https://vimeo.com/123"],
            extras={"PAGE_TITLE": "Supplied title"},
        )
        self.assertEqual(record["V2.1SHARINGIMAGE"], "https://example.org/photo.jpg")
        self.assertEqual(
            record["V2.1RELATEDIMAGES"], "https://example.org/one.jpg;https://example.org/two.jpg"
        )
        self.assertEqual(record["V2.1SOCIALIMAGEEMBEDS"], "")
        self.assertEqual(record["V2.1SOCIALVIDEOEMBEDS"], "https://vimeo.com/123")
        self.assertEqual(record["V2EXTRASXML"], "<PAGE_TITLE>Supplied title</PAGE_TITLE>")
        with patch.object(fields, "format_sharing_image", side_effect=RuntimeError("called")):
            self.assertEqual(
                self.record(field_values={"V2.1SHARINGIMAGE": ""})["V2.1SHARINGIMAGE"], ""
            )

    def test_translation_and_invalid_serialization(self):
        record = self.record(source_language="fra", translation_engine="Example")
        self.assertEqual(record["GKGRECORDID"], "20261001091500-T1")
        record["V1PERSONS"] = "bad\nname"
        with self.assertRaises(ValueError):
            serialize_gkg(record, allow_incomplete=True)
        del record["V1PERSONS"]
        with self.assertRaises(ValueError):
            serialize_gkg(record, allow_incomplete=True)


if __name__ == "__main__":
    unittest.main()
