import unittest
import warnings

from gdelt_regkg import (
    IncompleteGKGWarning,
    QuotationMention,
    analyze_quotations,
    generate_gkg,
    serialize_gkg,
)
from gdelt_regkg.fields import extract_quotations


class QuotationTests(unittest.TestCase):
    def test_before_after_and_missing_verb(self):
        for text, quote, verb in (
            ('Jane said, "We are ready."', "We are ready.", "said"),
            ("“We are ready,” Jane added.", "We are ready,", "added"),
            ("The sign reads “No entry”.", "No entry", ""),
        ):
            result = analyze_quotations(text)
            self.assertEqual(len(result.mentions), 1)
            mention = result.mentions[0]
            self.assertEqual((mention.text, mention.verb), (quote, verb))
            self.assertEqual(text[mention.start : mention.end], quote)
            self.assertEqual(
                extract_quotations(text), f"{text.index(quote)}|{len(quote)}|{verb}|{quote}"
            )

    def test_repeated_quotes_and_original_unicode_offsets(self):
        text = "😀 “Ready,” she said. “Ready,” she said."
        result = analyze_quotations(text)
        self.assertEqual([m.start for m in result.mentions], [3, 22])
        self.assertEqual([m.verb for m in result.mentions], ["said", "said"])
        self.assertEqual(result.to_gkg(), "3|6|said|Ready,#22|6|said|Ready,")

    def test_apostrophes_nested_styles_and_escapes(self):
        text = "Don't stop. Jane said ‘We don’t agree with his “plan”.’"
        result = analyze_quotations(text)
        self.assertEqual(len(result.mentions), 1)
        self.assertEqual(result.mentions[0].text, "We don’t agree with his “plan”.")
        self.assertEqual(result.mentions[0].verb, "said")
        self.assertEqual(analyze_quotations("The workers' plans aren't final.").mentions, ())
        self.assertEqual(
            analyze_quotations('He said "A \\"word\\" matters."').mentions[0].text,
            'A \\"word\\" matters.',
        )
        self.assertEqual(
            analyze_quotations("He said 'We can't wait.'").mentions[0].text, "We can't wait."
        )

    def test_multiline_wire_preserves_span_length(self):
        text = "He said «  First\nsecond\tline  »."
        result = analyze_quotations(text)
        mention = result.mentions[0]
        self.assertEqual(mention.text, "First\nsecond\tline")
        self.assertEqual(mention.end - mention.start, len(mention.text))
        self.assertEqual(result.to_gkg(), f"{mention.start}|17|said|First second line")

    def test_separator_normalization_keeps_spans_and_diagnostics(self):
        result = analyze_quotations('He said "Use #tag". She said “a|b”. An “unfinished')
        self.assertEqual([m.text for m in result.mentions], ["Use #tag", "a|b"])
        self.assertEqual(
            [i.reason for i in result.issues],
            ["normalized_delimiter", "normalized_delimiter", "unclosed_quote"],
        )
        self.assertEqual(QuotationMention("a|b", 0, 3).to_gkg(), "0|3||a b")
        self.assertEqual(
            [entry.split("|")[-1] for entry in result.to_gkg().split("#")], ["Use tag", "a b"]
        )
        self.assertEqual(analyze_quotations('"#|"').issues[0].reason, "empty_after_normalization")
        self.assertEqual(extract_quotations("No quotations here."), "")
        self.assertEqual(extract_quotations('""'), "")
        with self.assertRaises(TypeError):
            analyze_quotations(None)

    def test_do_not_borrow_verbs_across_sentences_or_quotes(self):
        result = analyze_quotations("Jane said “Yes.” Bob left. The sign was “Open”.")
        self.assertEqual([m.verb for m in result.mentions], ["said", ""])
        result = analyze_quotations("“First” and “second,” Jane said.")
        self.assertEqual([m.verb for m in result.mentions], ["", "said"])

    def test_pipeline_output_and_override(self):
        text = 'Jane said, "Ready."'
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            record = generate_gkg(
                text,
                identifier="https://example.org/story",
                published_at=None,
                batch_time="20261002000000",
                sequence=1,
            )
            self.assertEqual(record["V2.1QUOTATIONS"], extract_quotations(text))
            self.assertEqual(
                len(serialize_gkg(record, allow_incomplete=True).rstrip("\n").split("\t")), 27
            )
            record = generate_gkg(
                text,
                identifier="https://example.org/story",
                published_at=None,
                batch_time="20261002000000",
                sequence=1,
                field_values={"V2.1QUOTATIONS": "external"},
            )
            self.assertEqual(record["V2.1QUOTATIONS"], "external")


if __name__ == "__main__":
    unittest.main()
