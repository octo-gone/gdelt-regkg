"""Independent statistical, parsing and one-to-one matching regression checks."""

import math
import random
import unittest

from gdelt_regkg.benchmark import BenchmarkOptions, parsers
from gdelt_regkg.benchmark.matching import assignment, match_by_key
from gdelt_regkg.benchmark.metrics import numeric_metrics, quantile, set_metrics
from gdelt_regkg.benchmark.model import BenchmarkReport, GKGRow, ScoreContext
from gdelt_regkg.benchmark.numeric import gcam


class BenchmarkMetricTests(unittest.TestCase):
    def test_gcam_streams_pairs_without_caching_parsed_dictionaries(self):
        pairs = [
            (GKGRow({"gcam": "wc:10,c2.1:2"}), GKGRow({"gcam": "wc:20,c2.1:4"})),
            (GKGRow({"gcam": "wc:10"}), GKGRow({"gcam": "wc:20,c2.1:2"})),
            (GKGRow({"gcam": "bad"}), GKGRow({"gcam": ""})),
        ]
        report = BenchmarkReport()
        context = ScoreContext(pairs, BenchmarkOptions(gcam_keys=frozenset({"c2.1"})), report)
        gcam(context, "gcam")
        self.assertEqual(context._parsed, {})
        self.assertEqual(sum(report.audit.values()), 1)
        rows = {(r.field, r.calculation): r for r in report.rows}
        counts = rows["GCAM / General Inquirer", "supported counts"]
        self.assertEqual(counts.documents, 2)
        self.assertEqual(counts.metrics["mae"], 2)
        self.assertEqual(counts.metrics["count_wape"], 2)
        self.assertEqual(counts.metrics["density_mae_pp"], 5)
        presence = rows["GCAM / General Inquirer", "supported presence"]
        self.assertAlmostEqual(presence.metrics["f1"], 2 / 3)

    def test_numeric_agreement_bias_ties_and_limits(self):
        result = numeric_metrics([(1, 2), (2, 4), (3, 6)])
        self.assertEqual(result["mae"], 2)
        self.assertAlmostEqual(result["rmse"], math.sqrt(14 / 3))
        self.assertEqual(result["bias"], 2)
        self.assertAlmostEqual(result["ccc"], 4 / 11)
        self.assertAlmostEqual(result["spearman"], 1)
        self.assertAlmostEqual(result["loa_lower"], 0.04)
        self.assertAlmostEqual(result["loa_upper"], 3.96)
        self.assertAlmostEqual(numeric_metrics([(1, 3), (2, 2), (3, 1)])["spearman"], -1)
        self.assertAlmostEqual(numeric_metrics([(1, 2), (1, 2), (3, 6)])["spearman"], 1)

    def test_undefined_numeric_metrics_are_not_perfect_scores(self):
        self.assertIsNone(numeric_metrics([])["mae"])
        self.assertIsNone(numeric_metrics([(1, 1)])["ccc"])
        self.assertIsNone(numeric_metrics([(1, 1), (1, 1)])["ccc"])
        self.assertIsNone(numeric_metrics([(1, 1), (1, 1)])["spearman"])

    def test_empty_sets_do_not_inflate_f1(self):
        result = set_metrics([(set(), set())] * 100)
        self.assertIsNone(result["f1"])
        self.assertEqual(result["exact_agreement"], 1)
        result = set_metrics([(set(), set())] * 100 + [({"A"}, set())])
        self.assertEqual(result["f1"], 0)

    def test_quantiles_interpolate_and_handle_empty_values(self):
        self.assertIsNone(quantile([], 0.5))
        self.assertEqual(quantile([0, 10], 0.9), 9)

    def test_matching_maximizes_cardinality_before_offset_distance(self):
        left = [parsers.Mention("A", 2), parsers.Mention("A", 4)]
        right = [parsers.Mention("A", 0), parsers.Mention("A", 3)]
        self.assertEqual(set(match_by_key(left, right, lambda v: v.identity, 2)), {(0, 0), (1, 1)})

    def test_assignment_agrees_with_bruteforce_on_small_graphs(self):
        rng = random.Random(19)
        for n in range(1, 4):
            for m in range(1, 4):
                for _ in range(12):
                    values = [[rng.choice([None, 0, 1, 2]) for _ in range(m)] for _ in range(n)]
                    possibilities = []

                    def search(row, used, pairs):
                        if row == n:
                            possibilities.append((-len(pairs), sum(values[i][j] for i, j in pairs)))
                            return
                        search(row + 1, used, pairs)
                        for column in range(m):
                            if column not in used and values[row][column] is not None:
                                search(row + 1, used | {column}, pairs + [(row, column)])

                    search(0, set(), [])
                    actual = assignment(list(range(n)), list(range(m)), lambda i, j: values[i][j])
                    self.assertEqual(
                        (-len(actual), sum(values[i][j] for i, j in actual)), min(possibilities)
                    )
                    self.assertEqual(len(actual), len({i for i, j in actual}))
                    self.assertEqual(len(actual), len({j for i, j in actual}))

    def test_dates_accept_both_separators_and_preserve_unknown_year(self):
        self.assertEqual(parsers.dates("3#10#13#2026#0"), parsers.dates("3,10,13,2026,0"))
        self.assertEqual(parsers.dates("4#2#29#0#5")[0].identity, (4, 2, 29, 0))
        with self.assertRaises(ValueError):
            parsers.dates("3#2#29#2025#0")

    def test_strict_parsers_reject_malformed_and_nonfinite_values(self):
        for parser, value in (
            (parsers.amounts, "NaN,people,0"),
            (parsers.gcam, "wc:1,c2.1:inf"),
            (parsers.gcam, "wc:1,wc:2"),
            (parsers.quotations, "0|0|said|hello"),
            (parsers.locations, "4#Paris#FR#A8#100#2#x"),
            (parsers.xml, '<!DOCTYPE x [<!ENTITY y "hello">]><A>&y;</A>'),
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parser(value)

    def test_options_reject_invalid_and_nonfinite_thresholds(self):
        for options in (
            {"offset_tolerance": -1},
            {"object_similarity": 1.1},
            {"number_tolerance": float("nan")},
            {"quote_similarity": float("nan")},
            {"tone_neutral": float("inf")},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                BenchmarkOptions(**options)


if __name__ == "__main__":
    unittest.main()
