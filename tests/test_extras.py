import unittest
import warnings
from unittest.mock import patch
from xml.etree.ElementTree import fromstring

from gdelt_regkg import (
    Citation,
    IncompleteGKGWarning,
    citation_elements,
    format_extras_xml,
    generate_gkg,
    serialize_gkg,
)
from gdelt_regkg.fields import extract_extras_xml


class ExtrasTests(unittest.TestCase):
    def record(self, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            return generate_gkg(
                "Article text",
                identifier="https://example.org/article",
                published_at=None,
                batch_time="20261001091500",
                sequence=1,
                **kwargs,
            )

    def test_missing_and_explicitly_empty_metadata(self):
        self.assertIsNone(extract_extras_xml(None))
        self.assertEqual(extract_extras_xml({}), "")
        self.assertEqual(format_extras_xml(citation_elements([])), "")
        self.assertIsNone(self.record()["V2EXTRASXML"])
        self.assertEqual(self.record(extras={})["V2EXTRASXML"], "")
        self.assertIsNone(self.record(source_collection=5)["V2EXTRASXML"])

    def test_all_reference_fields_and_author_order(self):
        citation = Citation(
            authors=("Doe, Jane", "John Smith", "Smith, John, Jr."),
            title="Title",
            book_title="Book",
            date="2024",
            journal="Journal",
            volume="3",
            issue="2",
            pages="10-20",
            institution="Institute",
            publisher="Publisher",
            location="City",
            marker="Doe et al., 2024",
        )
        root = fromstring(format_extras_xml(citation_elements([citation])))
        self.assertEqual(root.tag, "CITEDREFERENCESLIST")
        node = root.find("CITATION")
        self.assertEqual(
            [a.text for a in node.findall("AUTHORS/AUTHOR")],
            ["Jane Doe", "John Smith", "Smith, John, Jr."],
        )
        expected = {
            "TITLE": "Title",
            "BOOKTITLE": "Book",
            "DATE": "2024",
            "JOURNAL": "Journal",
            "VOLUME": "3",
            "ISSUE": "2",
            "PAGES": "10-20",
            "INSTITUTION": "Institute",
            "PUBLISHER": "Publisher",
            "LOCATION": "City",
            "MARKER": "Doe et al., 2024",
        }
        self.assertEqual(
            {child.tag: child.text for child in node if child.tag != "AUTHORS"}, expected
        )

    def test_escaping_newlines_and_tsv_round_trip(self):
        title = 'A & B < C "study"\nnext\tpart\rend'
        citation = Citation(title=title)
        cell = format_extras_xml(citation_elements([citation]))
        self.assertFalse(any(char in cell for char in "\t\r\n"))
        self.assertEqual(fromstring(cell).findtext("CITATION/TITLE"), title)
        record = self.record(extras=citation_elements([citation]))
        cells = serialize_gkg(record, allow_incomplete=True).removesuffix("\n").split("\t")
        self.assertEqual(len(cells), 27)
        self.assertEqual(cells[-1], cell)

    def test_partial_references_duplicates_and_generators(self):
        first = Citation(title="First", date=" ")
        last = Citation(authors=["Doe, Jane"])
        cell = format_extras_xml(citation_elements(c for c in (first, first, last)))
        root = fromstring(cell)
        self.assertEqual(len(root), 3)
        self.assertEqual([node.findtext("TITLE") for node in root], ["First", "First", None])
        self.assertIsNone(root[0].find("DATE"))
        self.assertIsNone(root[0].find("AUTHORS"))

    def test_invalid_metadata_and_inputs(self):
        for kwargs in (
            {},
            {"title": "\x00"},
            {"title": "\ud800"},
            {"title": 2024},
            {"authors": "Jane Doe"},
            {"authors": ("",)},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises((TypeError, ValueError)):
                Citation(**kwargs)
        with self.assertRaises(TypeError):
            citation_elements([{"title": "Unconverted mapping"}])
        with self.assertRaises(TypeError):
            extract_extras_xml("Article text")

    def test_arbitrary_page_elements_are_rootless_and_caller_supplied(self):
        elements = {
            "PAGE_LINKS": "https://example.org/story;https://x.com/ashermcs",
            "PAGE_AUTHORS": "@ashermcs",
            "PAGE_PRECISEPUBTIMESTAMP": "20250715114600",
            "PAGE_TITLE": "JAMB warns non-participants to keep off registration process",
            "PAGE_ALTURL_AMP": "https://example.org/amp/story",
            "CUSTOM_TOPIC": "example",
        }
        cell = format_extras_xml(elements)
        self.assertEqual(
            cell, "".join(f"<{name}>{value}</{name}>" for name, value in elements.items())
        )
        root = fromstring("<root>" + cell + "</root>")
        self.assertEqual([node.tag for node in root], list(elements))
        self.assertEqual(self.record(extras=elements)["V2EXTRASXML"], cell)

    def test_nested_repeated_empty_and_omitted_elements(self):
        elements = {
            "PAGE_TITLE": "Title",
            "CUSTOM": {"VALUE": ["one", "two"], "OMITTED": None},
            "EMPTY": "",
            "MISSING": None,
            **citation_elements([Citation(title="Reference")]),
        }
        root = fromstring("<root>" + format_extras_xml(elements) + "</root>")
        self.assertEqual([node.text for node in root.findall("CUSTOM/VALUE")], ["one", "two"])
        self.assertIsNone(root.find("MISSING"))
        self.assertIsNotNone(root.find("EMPTY"))
        self.assertEqual(root.findtext("CITEDREFERENCESLIST/CITATION/TITLE"), "Reference")

    def test_invalid_tags_and_unsupported_values(self):
        for name in ("1TAG", "BAD NAME", "<TAG>", "@attribute", "ns:tag"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                format_extras_xml({name: "text"})
        for value in (2024, True, object()):
            with self.subTest(value=value), self.assertRaises(TypeError):
                format_extras_xml({"TAG": value})
        with self.assertRaises(ValueError):
            format_extras_xml({"TAG": "\x00"})

    def test_pipeline_override_skips_formatter(self):
        with patch("gdelt_regkg.fields.extract_extras_xml", side_effect=RuntimeError("called")):
            record = self.record(
                extras={"UNUSED": "value"}, field_values={"V2EXTRASXML": "<CUSTOM>value</CUSTOM>"}
            )
        self.assertEqual(record["V2EXTRASXML"], "<CUSTOM>value</CUSTOM>")
