"""Compare dictionary revisions on date/source-separated live GKG benchmarks.

Fits bounded binary dictionary edits on training bodies, chooses components on
validation, then evaluates once on the final test date. Never fits on test rows.
Exports a ToneLexicon-compatible profile, metrics, split audit and token edits.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from gdelt_regkg.scripts.benchmark_tone import FIELDS, summarize
from gdelt_regkg.tone import ToneLexicon, baseline_tone_lexicon, tokenize_tone

CATEGORIES = ("positive", "negative", "activity", "self_group")
SCORE_KEYS = dict(
    zip(CATEGORIES, ("positive", "negative", "activity_density", "self_group_density"))
)
FIRST_PERSON = set(
    "i me my mine myself we us our ours ourselves i'm i've i'll i'd we're we've we'll we'd let's".split()
)
SECOND_PERSON = set("you your yours yourself yourselves you're you've you'll you'd".split())
THIRD_PERSON = set(
    "he him his himself she her hers herself it its itself they them their theirs themselves he's he'd he'll she's she'd she'll it's it'd it'll they're they've they'll they'd".split()
)
AUXILIARIES = set(
    "be am is are was were been being do does did done doing have has had having can could may might must shall should will would need needs needed get gets got gotten getting".split()
)
IRREGULAR = {
    "be": "am is are was were been being",
    "have": "has had having",
    "do": "does did done doing",
    "say": "says said saying",
    "make": "makes made making",
    "get": "gets got gotten getting",
    "go": "goes went gone going",
    "take": "takes took taken taking",
    "give": "gives gave given giving",
    "think": "thinks thought thinking",
    "know": "knows knew known knowing",
    "see": "sees saw seen seeing",
    "come": "comes came coming",
    "find": "finds found finding",
    "tell": "tells told telling",
    "feel": "feels felt feeling",
    "leave": "leaves left leaving",
    "keep": "keeps kept keeping",
    "lose": "loses lost losing",
    "win": "wins won winning",
    "run": "runs ran running",
    "hold": "holds held holding",
    "bring": "brings brought bringing",
    "buy": "buys bought buying",
    "sell": "sells sold selling",
    "pay": "pays paid paying",
    "meet": "meets met meeting",
    "build": "builds built building",
    "fight": "fights fought fighting",
    "lead": "leads led leading",
    "rise": "rises rose risen rising",
    "fall": "falls fell fallen falling",
    "write": "writes wrote written writing",
    "good": "better best",
    "bad": "worse worst",
}


def inflections(words):
    """Candidate spellings only; additions are restricted to observed training vocabulary."""
    result = set(words)
    for word in words:
        if not re.fullmatch("[a-z]{3,}", word):
            continue
        result.update((word + "s", word + "es", word + "ed", word + "ing"))
        if word.endswith("e"):
            result.update((word + "d", word[:-1] + "ing"))
        if word.endswith("y") and word[-2] not in "aeiou":
            result.update((word[:-1] + "ies", word[:-1] + "ied"))
        if word[-1] not in "aeiouwxy" and word[-2] in "aeiou" and word[-3] not in "aeiou":
            result.update((word + word[-1] + "ed", word + word[-1] + "ing"))
    for word in words:
        result.update(IRREGULAR.get(word, "").split())
    return result


def gi_verbs(path):
    result = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, delimiter="\t"):
            if not {"SUPV", "VERB"} & set(row["Othtags"].split()):
                continue
            word = re.sub(r"#\d+$", "", row["Entry"]).rstrip(">").casefold()
            if tokenize_tone(word) == [word]:
                result.add(word)
    return result


def source_reserved(source):
    return int(hashlib.sha256(source.encode()).hexdigest()[:8], 16) % 5 == 0


def fingerprint(tokens):
    """64-bit token SimHash for conservative near-duplicate exclusion (distance ≤3)."""
    bits = [0] * 64
    for word, count in Counter(tokens).items():
        hashed = int(hashlib.sha256(word.encode()).hexdigest()[:16], 16)
        weight = min(count, 3)
        for bit in range(64):
            bits[bit] += weight if hashed >> bit & 1 else -weight
    return sum(1 << bit for bit, value in enumerate(bits) if value > 0)


class DuplicateIndex:
    def __init__(self):
        self.exact = set()
        self.bands = defaultdict(set)

    def add(self, tokens):
        exact = hashlib.sha256(" ".join(tokens).encode()).hexdigest()
        if exact in self.exact:
            return "exact_duplicate"
        signature = fingerprint(tokens)
        candidates = set().union(
            *(self.bands[(i, signature >> (16 * i) & 65535)] for i in range(4))
        )
        if any((signature ^ other).bit_count() <= 3 for other in candidates):
            return "near_duplicate"
        self.exact.add(exact)
        for i in range(4):
            self.bands[(i, signature >> (16 * i) & 65535)].add(signature)
        return None


def prepare_rows(paths, train_dates, validation_date, test_date, check_language):
    all_rows, audit, counts = [], [], Counter[str]()
    detector = None
    if check_language:
        from gdelt_regkg.language import LinguaDetector

        detector = LinguaDetector()
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                counts["attempted"] += 1
                if row["status"] != "ok":
                    counts["fetch_or_extraction_failure"] += 1
                    continue
                day = row["batch"][:8]
                split = (
                    "train"
                    if day in train_dates
                    else "validation"
                    if day == validation_date
                    else "test"
                    if day == test_date
                    else "unused"
                )
                entry = {
                    "record_id": row["record_id"],
                    "url": row["url"],
                    "source": row["source"],
                    "date": day,
                    "split": split,
                }
                if split == "unused":
                    entry["excluded"] = "outside_split_dates"
                elif split != "test" and source_reserved(row["source"]):
                    entry["excluded"] = "source_reserved_for_test"
                if "excluded" not in entry and detector is not None:
                    try:
                        detection = detector.detect(row["text"])
                        entry["detected_language"] = detection.language
                        entry["language_confidence"] = detection.confidence
                        if detection.language != "eng":
                            entry["excluded"] = "non_english_body"
                    except ValueError as error:
                        entry["excluded"] = "uncertain_language"
                        entry["language_error"] = str(error)
                if "excluded" in entry:
                    counts[entry["excluded"]] += 1
                    audit.append(entry)
                    continue
                row = dict(row)
                row["split"] = split
                row["tokens"] = tokenize_tone(row["text"])
                row["counts"] = Counter(row["tokens"])
                row["source_reserved"] = source_reserved(row["source"])
                row["audit"] = entry
                all_rows.append(row)
    # Earlier splits take precedence; later copies cannot inform evaluation.
    order = {"train": 0, "validation": 1, "test": 2}
    index = DuplicateIndex()
    result = defaultdict(list)
    for row in sorted(all_rows, key=lambda r: (order[r["split"]], r["record_id"])):
        entry = row.pop("audit")
        duplicate = index.add(row["tokens"])
        if duplicate:
            entry["excluded"] = duplicate
            counts[duplicate] += 1
        else:
            result[row["split"]].append(row)
            counts[row["split"]] += 1
        audit.append(entry)
    return result, dict(counts), audit


def density(row, words):
    return 100 * sum(n for word, n in row["counts"].items() if word in words) / len(row["tokens"])


def category_mae(rows, words, category):
    return statistics.mean(
        abs(density(row, words) - row["original"][SCORE_KEYS[category]]) for row in rows
    )


def fit_edits(rows, base, candidates, category, *, penalty, min_documents=8, max_edits=100):
    """Greedy binary membership edits with an L1 cost for departing from the base."""
    current, base = set(base), set(base)
    postings: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for index, row in enumerate(rows):
        scale = 100 / len(row["tokens"])
        for word, count in row["counts"].items():
            if word in candidates:
                postings[word].append((index, count * scale))
    postings = {word: values for word, values in postings.items() if len(values) >= min_documents}
    residuals = [density(row, current) - row["original"][SCORE_KEYS[category]] for row in rows]
    history = []
    for _step in range(max_edits):
        best = None
        best_delta = -1e-10
        for word in sorted(postings):
            direction = -1 if word in current else 1
            was_changed = (word in current) != (word in base)
            delta = sum(
                abs(residuals[i] + direction * value) - abs(residuals[i])
                for i, value in postings[word]
            ) / len(rows)
            delta += penalty * (-1 if was_changed else 1)
            if delta < best_delta:
                best, best_delta = word, delta
        if best is None:
            break
        direction = -1 if best in current else 1
        if direction == 1:
            current.add(best)
        else:
            current.remove(best)
        for i, value in postings[best]:
            residuals[i] += direction * value
        history.append(
            {
                "word": best,
                "action": "add" if direction == 1 else "remove",
                "training_documents": len(postings[best]),
                "penalized_mae_delta": best_delta,
            }
        )
    return current, history


def predict_rows(rows, lexicon):
    result = []
    for row in rows:
        values = {SCORE_KEYS[key]: density(row, getattr(lexicon, key)) for key in CATEGORIES}
        values["tone"] = values["positive"] - values["negative"]
        values["polarity"] = density(row, lexicon.positive | lexicon.negative)
        values["word_count"] = len(row["tokens"])
        result.append(
            {
                "record_id": row["record_id"],
                "source": row["source"],
                "url": row["url"],
                "original": row["original"],
                "predicted": values,
                "word_count_ratio": row["word_count_ratio"],
                "source_reserved": row["source_reserved"],
            }
        )
    return result


def evaluation(rows, lexicon):
    predicted = predict_rows(rows, lexicon)
    return {
        "all": summarize(predicted),
        "similar_length": summarize([r for r in predicted if 0.9 <= r["word_count_ratio"] <= 1.1]),
        "reserved_sources": summarize([r for r in predicted if r["source_reserved"]]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, nargs="+", required=True)
    parser.add_argument("--train-dates", nargs="+", required=True)
    parser.add_argument("--validation-date", required=True)
    parser.add_argument("--test-date", required=True)
    parser.add_argument("--gi-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check-language", action="store_true")
    args = parser.parse_args()
    dates = args.train_dates + [args.validation_date, args.test_date]
    if len(set(dates)) != len(dates):
        parser.error("Training, validation and test dates must be disjoint")
    args.output.mkdir(parents=True, exist_ok=True)
    splits, counts, audit = prepare_rows(
        args.results,
        set(args.train_dates),
        args.validation_date,
        args.test_date,
        args.check_language,
    )
    (args.output / "split_audit.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in audit), encoding="utf-8"
    )
    print("[SPLITS] " + json.dumps(counts), flush=True)
    if any(len(splits[key]) < 30 for key in ("train", "validation", "test")):
        parser.error("Need at least 30 independent usable bodies in every split")
    train = [r for r in splits["train"] if 0.8 <= r["word_count_ratio"] <= 1.25]
    if len(train) < 100:
        parser.error("Need at least 100 reasonably aligned training bodies")
    validation, test = splits["validation"], splits["test"]
    base = baseline_tone_lexicon()
    vocab_docs = Counter(word for row in train for word in row["counts"])
    observed = {word for word, n in vocab_docs.items() if n >= 8}
    verbs = gi_verbs(args.gi_source)
    expansions = {
        key: set(getattr(base, key)) | (inflections(getattr(base, key)) & observed)
        for key in ("positive", "negative")
    }
    activity_pool = set(base.activity) | (
        (inflections(verbs | AUXILIARIES) | AUXILIARIES) & observed
    )
    options = {key: {"baseline": set(getattr(base, key))} for key in CATEGORIES}
    histories = {}
    for key in ("positive", "negative"):
        options[key]["observed_inflections"] = expansions[key]
    options["activity"].update(
        {
            "active_plus_auxiliaries": set(base.activity) | AUXILIARIES,
            "observed_verbs_and_inflections": activity_pool,
        }
    )
    options["self_group"].update(
        {
            "first_person": FIRST_PERSON,
            "first_and_second_person": FIRST_PERSON | SECOND_PERSON,
            "personal_pronouns": FIRST_PERSON | SECOND_PERSON | THIRD_PERSON,
        }
    )
    for key in CATEGORIES:
        pool = (
            expansions[key]
            if key in expansions
            else activity_pool
            if key == "activity"
            else set(base.self_group) | FIRST_PERSON | SECOND_PERSON | THIRD_PERSON
        )
        for penalty in (0.003, 0.01):
            name = f"refined_penalty_{penalty}"
            initial = getattr(base, key) if key != "self_group" else FIRST_PERSON | SECOND_PERSON
            words, history = fit_edits(
                train,
                initial,
                pool,
                key,
                penalty=penalty,
                max_edits=160 if key == "activity" else 80,
            )
            options[key][name] = words
            histories[f"{key}/{name}"] = history
            print(f"[FIT] {key}/{name}: words={len(words)} edits={len(history)}", flush=True)
    validation_metrics = {
        key: {name: category_mae(validation, words, key) for name, words in variants.items()}
        for key, variants in options.items()
    }
    # Choose the sentiment pair together, to avoid improving components but worsening net tone.
    pair_scores = []
    for positive_name, positive in options["positive"].items():
        for negative_name, negative in options["negative"].items():
            tone_mae = statistics.mean(
                abs(density(r, positive) - density(r, negative) - r["original"]["tone"])
                for r in validation
            )
            objective = (
                tone_mae
                + 0.5 * validation_metrics["positive"][positive_name]
                + 0.5 * validation_metrics["negative"][negative_name]
            )
            pair_scores.append(
                {
                    "positive": positive_name,
                    "negative": negative_name,
                    "tone_mae": tone_mae,
                    "objective": objective,
                }
            )
    pair = min(pair_scores, key=lambda r: r["objective"])
    chosen = {"positive": pair["positive"], "negative": pair["negative"]}
    for key in ("activity", "self_group"):
        metrics = validation_metrics[key]
        chosen[key] = min(metrics, key=metrics.__getitem__)
    profile = ToneLexicon(
        name="gdelt-benchmark-lexicon-v1",
        **{key: frozenset(options[key][chosen[key]]) for key in CATEGORIES},
    )
    sentiment = ToneLexicon(
        name="sentiment-only",
        positive=profile.positive,
        negative=profile.negative,
        activity=base.activity,
        self_group=base.self_group,
    )
    references = ToneLexicon(
        name="activity-reference-only",
        positive=base.positive,
        negative=base.negative,
        activity=profile.activity,
        self_group=profile.self_group,
    )
    report = {
        "split_dates": {
            "train": args.train_dates,
            "validation": args.validation_date,
            "test": args.test_date,
        },
        "counts": counts,
        "aligned_training_n": len(train),
        "source_rule": "sha256(source) first 8 hex digits modulo 5 == 0 excluded from train/validation, retained in test",
        "duplicate_rule": "Normalized-token exact hash or 64-bit token SimHash Hamming distance <=3; earliest split retained",
        "input_hashes": {
            str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in args.results
        },
        "gi_source_sha256": hashlib.sha256(args.gi_source.read_bytes()).hexdigest(),
        "validation_category_mae": validation_metrics,
        "validation_sentiment_pairs": pair_scores,
        "chosen": chosen,
        "test": {
            "baseline": evaluation(test, base),
            "sentiment_only": evaluation(test, sentiment),
            "activity_reference_only": evaluation(test, references),
            "combined": evaluation(test, profile),
        },
        "changes": {
            key: {
                "added": sorted(getattr(profile, key) - getattr(base, key)),
                "removed": sorted(getattr(base, key) - getattr(profile, key)),
                "word_count": len(getattr(profile, key)),
            }
            for key in CATEGORIES
        },
        "interpretation": "Empirical dictionary approximation, not recovered GDELT lexicons. Date/source holdouts, language screening and conservative duplicate removal reduce leakage; live extraction and imperfect near-duplicate detection remain limitations.",
    }
    payload = {
        "name": profile.name,
        "description": report["interpretation"],
        "base_lexicon": base.name,
        "base_source_terms": "https://inquirer.sites.fas.harvard.edu/spreadsheet_guide.htm",
        "training_dates": args.train_dates,
        "validation_date": args.validation_date,
        "source_sha256": report["gi_source_sha256"],
        **{key: sorted(getattr(profile, key)) for key in CATEGORIES},
    }
    (args.output / "lexicon.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (args.output / "training_edits.json").write_text(
        json.dumps(histories, indent=2), encoding="utf-8"
    )
    with (args.output / "test_comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["record_id", "source", "url", "word_count_ratio", "reserved_source"]
            + [f"{kind}_{key}" for key in FIELDS for kind in ("gdelt", "baseline", "revised")],
        )
        writer.writeheader()
        for old, new in zip(predict_rows(test, base), predict_rows(test, profile)):
            out = {key: old[key] for key in ("record_id", "source", "url", "word_count_ratio")}
            out["reserved_source"] = old["source_reserved"]
            for key in FIELDS:
                out.update(
                    {
                        f"gdelt_{key}": old["original"][key],
                        f"baseline_{key}": old["predicted"][key],
                        f"revised_{key}": new["predicted"][key],
                    }
                )
            writer.writerow(out)
    print(
        json.dumps(
            {
                "chosen": chosen,
                "test_n": len(test),
                "baseline": report["test"]["baseline"]["all"],
                "revised": report["test"]["combined"]["all"],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
