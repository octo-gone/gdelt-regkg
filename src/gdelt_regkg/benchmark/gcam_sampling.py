"""Explicit GCAM cohorts, body-length matching and reproducible sampling."""

import random

from . import parsers
from .metrics import quantile


class GCAMSelection:
    def __init__(self, context):
        self.context = context
        self.candidates = self.language_eligible = self.size_eligible = self.selected = 0
        self.ratios: list[float] = []
        self.within_ten = self.missing_word_counts = 0

    def pairs(self, name, language_resolver):
        options = self.context.options
        rng = random.Random(options.gcam_seed)
        reservoir: list[tuple] = []
        for left, right, reference, prediction in self.context.iter_parsed(
            name, parsers.gcam, include_rows=True
        ):
            self.candidates += 1
            languages = language_resolver(prediction, self.context)
            if (
                options.gcam_evaluation_language is not None
                and options.gcam_evaluation_language not in (languages or ["eng"])
            ):
                self.context.note(
                    "prediction", "gcam", "language_not_evaluated", options.gcam_evaluation_language
                )
                continue
            self.language_eligible += 1
            word_key = "nwc" if options.gcam_evaluation_language not in (None, "eng") else "wc"
            expected, actual = left.get(word_key, 0), right.get(word_key, 0)
            difference = None
            if expected > 0 and actual > 0:
                ratio = actual / expected
                self.ratios.append(ratio)
                difference = abs(actual - expected) / expected
                self.within_ten += difference <= 0.1
            else:
                self.missing_word_counts += 1
            if options.gcam_max_word_count_difference is not None and (
                difference is None or difference > options.gcam_max_word_count_difference
            ):
                self.context.note("selection", "gcam", "body_size_excluded")
                continue
            self.size_eligible += 1
            if options.gcam_sample_size is None:
                self.selected += 1
                yield left, right, reference, prediction, languages
            else:
                item = (reference, prediction, languages)
                if len(reservoir) < options.gcam_sample_size:
                    reservoir.append(item)
                elif (index := rng.randrange(self.size_eligible)) < options.gcam_sample_size:
                    reservoir[index] = item
        for reference, prediction, languages in reservoir:
            # Parse only selected row handles again, keeping large corpora on disk.
            left = parsers.gcam(reference.get(name))
            try:
                right = parsers.gcam(prediction.get(name))
            except (ValueError, ArithmeticError):
                right = {}
            self.selected += 1
            yield left, right, reference, prediction, languages

    def report(self):
        context = self.context
        context.table(
            "gcam-sampling",
            "GCAM",
            "article selection",
            {
                "candidate_documents": self.candidates,
                "language_eligible": self.language_eligible,
                "size_eligible": self.size_eligible,
                "selected_documents": self.selected,
                "missing_word_counts": self.missing_word_counts,
            },
            self.selected,
        )
        context.table(
            "gcam-sampling",
            "GCAM",
            "body-size agreement before selection",
            {
                "ratio_median": quantile(self.ratios, 0.5),
                "ratio_p10": quantile(self.ratios, 0.1),
                "ratio_p90": quantile(self.ratios, 0.9),
                "within_ten_percent": self.within_ten / len(self.ratios) if self.ratios else None,
                "paired_values": len(self.ratios),
            },
            self.language_eligible,
        )
