"""Compare locations, dates, amounts, names, quotations and GCAM with GKG ZIPs.

No retrieval or fitting. Use a separately reserved corpus for final evaluation.
Offsets are excluded from identity scoring because body snapshots can differ.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
import zipfile
from collections import Counter, defaultdict
from decimal import Decimal
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from gdelt_regkg import (
    SpacyNER,
    analyze_amounts,
    analyze_dates,
    analyze_gcam,
    analyze_locations,
    analyze_names,
    analyze_quotations,
)
from gdelt_regkg.gcam import GCAMLexicon, default_gcam_lexicon
from gdelt_regkg.locations import default_gazetteer
from gdelt_regkg.tone import tokenize_tone
from gdelt_regkg.utils import read_resource_json, resource_path

from .benchmark_extraction import normalize_name
from .build_gcam_expansion import read_codebook


def parse_gcam(value):
    gcam = {}
    for entry in filter(None, value.split(",")):
        key, value = entry.split(":", 1)
        if key in gcam:
            raise ValueError("Duplicate GCAM key")
        gcam[key] = float(value)
        if not math.isfinite(gcam[key]):
            raise ValueError("Nonfinite GCAM value")
    return gcam


def _parse_locations(cell):
    locations = set()
    for entry in filter(None, cell.split(";")):
        p = entry.split("#")
        if len(p) != 9:
            raise ValueError("Enhanced location requires nine components")
        locations.add((p[0], p[2], p[3], p[7]))
    return locations


def _parse_dates(cell):
    dates = set()
    for entry in filter(None, cell.split(";")):
        p = entry.split("#" if "#" in entry else ",")
        if len(p) != 5:
            raise ValueError("Enhanced date requires five components")
        dates.add(tuple(map(int, p[:4])))
    return dates


def _parse_names(cell):
    names = set()
    for entry in filter(None, cell.split(";")):
        name, offset = entry.rsplit(",", 1)
        int(offset)
        names.add(normalize_name(name))
    return names


def _parse_amounts(cell):
    amounts = set()
    for entry in filter(None, cell.split(";")):
        p = entry.split(",")
        if len(p) != 3:
            raise ValueError("Amount requires three components")
        number = Decimal(p[0])
        if not number.is_finite():
            raise ValueError("Amount must be finite")
        int(p[2])
        amounts.add((number, normalize_name(p[1])))
    return amounts


def parse_references(cells, *, tolerate_malformed=False):
    """Parse identities; optional auditing excludes only the malformed field."""
    result, errors = {}, {}
    for name, column, parser in (
        ("locations", 10, _parse_locations),
        ("dates", 16, _parse_dates),
        ("all_names", 23, _parse_names),
        ("amounts", 24, _parse_amounts),
        ("gcam", 17, parse_gcam),
    ):
        try:
            result[name] = parser(cells[column])
        except (ValueError, ArithmeticError) as error:
            if not tolerate_malformed:
                raise
            errors[name] = str(error)
            result[name] = {} if name == "gcam" else None
    if tolerate_malformed:
        result["errors"] = errors
    return result


def score_sets(rows):
    tp = sum(len(expected & actual) for expected, actual in rows)
    predicted = sum(len(actual) for _, actual in rows)
    reference = sum(len(expected) for expected, _ in rows)
    return {
        "articles": len(rows),
        "reference_positive_articles": sum(bool(expected) for expected, _ in rows),
        "predicted_positive_articles": sum(bool(actual) for _, actual in rows),
        "true_positives": tp,
        "predicted": predicted,
        "reference": reference,
        "precision": tp / predicted if predicted else None,
        "recall": tp / reference if reference else None,
        "f1": 2 * tp / (predicted + reference) if predicted + reference else None,
        "exact_document_match": sum(expected == actual for expected, actual in rows) / len(rows)
        if rows
        else None,
    }


def parse_quotation_reference(cell):
    """Ignore coordinates; retain normalized content and content/verb identities."""
    content, with_verbs = set(), set()
    for entry in filter(None, cell.split("#")):
        offset, length, verb, quote = entry.split("|", 3)
        if int(offset) < 0 or int(length) <= 0 or not quote.strip():
            raise ValueError("Invalid quotation span or empty content")
        quote = normalize_name(quote)
        content.add(quote)
        with_verbs.add((quote, normalize_name(verb)))
    return content, with_verbs


def bootstrap_f1(rows, *, samples, seed):
    """Percentile interval from document resampling, conditional on this corpus."""
    if not rows or not samples:
        return None
    counts = [(len(expected & actual), len(expected), len(actual)) for expected, actual in rows]
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        tp = reference = predicted = 0
        for hit, expected, actual in rng.choices(counts, k=len(counts)):
            tp += hit
            reference += expected
            predicted += actual
        if reference + predicted:
            estimates.append(2 * tp / (reference + predicted))
    if not estimates:
        return None
    estimates.sort()

    def percentile(fraction):
        index = (len(estimates) - 1) * fraction
        lower = math.floor(index)
        upper = math.ceil(index)
        return estimates[lower] + (estimates[upper] - estimates[lower]) * (index - lower)

    return [percentile(0.025), percentile(0.975)]


def _corpus_rows(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            yield json.loads(line)


def _correlation(pairs):
    if len(pairs) < 2:
        return None
    xs, ys = zip(*pairs)
    if not statistics.pvariance(xs) or not statistics.pvariance(ys):
        return None
    return statistics.correlation(xs, ys)


def _presence_metrics(count_pairs, family):
    tp = predicted = reference = exact = total = 0
    for key, pairs in count_pairs.items():
        if key[1:].split(".")[0] != family:
            continue
        for x, y in pairs:
            tp += x > 0 and y > 0
            predicted += y > 0
            reference += x > 0
            exact += (x > 0) == (y > 0)
            total += 1
    return {
        "true_positives": tp,
        "predicted": predicted,
        "reference": reference,
        "precision": tp / predicted if predicted else None,
        "recall": tp / reference if reference else None,
        "f1": 2 * tp / (predicted + reference) if predicted + reference else None,
        "exact_document_match": exact / total if total else None,
    }


@lru_cache(maxsize=2)
def _matching_originals(archives, identifiers):
    """Reuse originals across frozen profiles; keys include archive content hashes."""
    urls = dict(identifiers)
    matched: dict[str, list[str]] = {}
    audit = Counter[str]()
    for filename, _checksum in archives:
        with zipfile.ZipFile(filename) as archive:
            for member in archive.namelist():
                if not member.endswith(".csv"):
                    continue
                with archive.open(member) as stream:
                    for raw in stream:
                        # Most records are unselected; avoid decoding their large GCAM cells.
                        identifier = raw.split(b"\t", 1)[0].decode("utf-8", errors="replace")
                        if identifier not in urls:
                            continue
                        cells = raw.decode("utf-8", errors="replace").rstrip("\r\n").split("\t")
                        if len(cells) != 27:
                            raise ValueError("Original record must contain 27 columns")
                        if cells[4] != urls[identifier]:
                            # Native translated archives can reuse IDs for other URLs.
                            # Only the exact ID/URL pair identifies our selected document.
                            audit["ignored_same_id_other_url_records"] += 1
                            continue
                        if identifier in matched and matched[identifier] != cells:
                            raise ValueError("Conflicting original records")
                        matched[identifier] = cells
    return matched, dict(audit)


def benchmark_fields(
    corpus,
    archives,
    *,
    recognizer=None,
    sample_size=None,
    include_translated=False,
    gcam_lexicon=None,
    gcam_only=False,
    fields_only=False,
    bootstrap_samples=0,
    bootstrap_seed=1729,
    resources_dir=None,
):
    """Evaluate saved English analyzed bodies without changing any resource."""
    corpus = Path(corpus)
    if gcam_only and fields_only:
        raise ValueError("gcam_only and fields_only cannot be combined")
    if type(bootstrap_samples) is not int or bootstrap_samples < 0:
        raise ValueError("bootstrap_samples must be a nonnegative integer")
    if not gcam_only and recognizer is None:
        raise ValueError("Field benchmarking requires a recognizer unless gcam_only is enabled")
    lexicon = (
        None
        if fields_only
        else (default_gcam_lexicon(resources_dir) if gcam_lexicon is None else gcam_lexicon)
    )
    selected = {}
    audit = Counter[str]()
    for row in _corpus_rows(corpus):
        if row.get("status") != "ok" or not isinstance(row.get("text"), str):
            audit["excluded_missing_body"] += 1
            continue
        if row.get("translated") and not include_translated:
            audit["excluded_translated"] += 1
            continue
        if row["record_id"] in selected:
            raise ValueError("Duplicate record ID in corpus")
        selected[row["record_id"]] = row
    # Stable order fixed before scoring. sample_size is a smoke-check convenience,
    # not a source-balanced sampling method. Prefer the whole reserved corpus.
    if sample_size is not None:
        if type(sample_size) is not int or sample_size < 1:
            raise ValueError("sample_size must be a positive integer")
        selected = dict(sorted(selected.items())[:sample_size])
    manifest = []
    archive_checksums = []
    for path in sorted(map(Path, archives)):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.append({"name": path.name, "sha256": checksum})
        archive_checksums.append((str(path.resolve()), checksum))
    matched, pairing_audit = _matching_originals(
        tuple(archive_checksums),
        tuple(sorted((identifier, row["url"]) for identifier, row in selected.items())),
    )
    audit.update(pairing_audit)
    audit["missing_original_record"] = len(selected) - len(matched)
    pairs: dict[str, list[tuple[set, set]]] = (
        {}
        if gcam_only
        else {
            name: []
            for name in (
                "locations",
                "dates",
                "all_names",
                "amounts",
                "amount_values",
                "quotations",
                "quotations_with_verbs",
            )
        }
    )
    subset_pairs: defaultdict[str, dict[str, list[tuple[set, set]]]] = defaultdict(
        lambda: {name: [] for name in pairs}
    )
    sources = set()
    dimensions = {} if lexicon is None else lexicon.dimensions
    errors: dict[str, list[float]] = {key: [] for key in dimensions}
    count_pairs: dict[str, list[tuple[float, float]]] = {key: [] for key in dimensions}
    density_errors: dict[str, list[float]] = {key: [] for key in dimensions}
    count_exclusions = Counter[str]()
    value_pairs: dict[str, list[tuple[float, float]]] = (
        {} if lexicon is None else {key: [] for key in lexicon.weighted_dimensions}
    )
    value_audit = (
        {} if lexicon is None else {key: Counter[str]() for key in lexicon.weighted_dimensions}
    )
    wc_errors, wc_ratios = [], []
    codebook = None if fields_only else read_codebook(resources_dir=resources_dir)
    gazetteer = None if gcam_only else default_gazetteer(resources_dir)
    engine_checksums = {
        name: hashlib.sha256(files("gdelt_regkg").joinpath(name).read_bytes()).hexdigest()
        for name in (
            (() if fields_only else ("gcam.py", "tone.py", "themes.py"))
            + (
                ()
                if gcam_only
                else (
                    "ner.py",
                    "names.py",
                    "locations.py",
                    "dates.py",
                    "amounts.py",
                    "quotations.py",
                    "tone.py",
                    "wire.py",
                    "scripts/benchmark_extraction.py",
                )
            )
            + ("scripts/benchmark_fields.py",)
        )
    }
    implemented = (
        set()
        if lexicon is None
        else {key[1:] for key in (*dimensions, *lexicon.weighted_dimensions)}
    )
    inventory = set() if codebook is None else {key[1:] for key in codebook["dimensions"]}
    native_dimensions, supported_native_dimensions = set(), set()
    native_assignments = supported_native_assignments = 0
    native_occurrences = supported_native_occurrences = 0
    family_occurrences, family_supported_occurrences = Counter[str](), Counter[str]()
    family_assignments, family_supported_assignments = Counter[str](), Counter[str]()
    for record_id, row in selected.items():
        if record_id not in matched:
            continue
        try:
            reference = (
                {"gcam": parse_gcam(matched[record_id][17])}
                if gcam_only
                else parse_references(matched[record_id], tolerate_malformed=True)
            )
        except (ValueError, ArithmeticError):
            audit["malformed_original_fields"] += 1
            continue
        for field in reference.pop("errors", {}):
            audit["excluded_malformed_" + field] += 1
        text = row["text"]
        gcam = None if fields_only else analyze_gcam(text, lexicon=lexicon)
        if not gcam_only:
            ner = recognizer.analyze(text)
            locations = analyze_locations(text, ner=ner, gazetteer=gazetteer)
            dates = analyze_dates(text)
            amounts = analyze_amounts(text)
            names = analyze_names(text, ner=ner)
            actual = {
                "locations": {m.place.identity for m in locations.mentions},
                "dates": {(m.resolution, m.month, m.day, m.year) for m in dates.mentions},
                "all_names": {normalize_name(m.text) for m in names.mentions},
                "amounts": {(m.amount, normalize_name(m.object_type)) for m in amounts.mentions},
            }
            reference["amount_values"] = (
                None
                if reference["amounts"] is None
                else {amount for amount, _ in reference["amounts"]}
            )
            actual["amount_values"] = {m.amount for m in amounts.mentions}
            try:
                reference["quotations"], reference["quotations_with_verbs"] = (
                    parse_quotation_reference(matched[record_id][22])
                )
            except ValueError:
                audit["excluded_malformed_quotations"] += 1
            else:
                quotes = analyze_quotations(text)
                actual["quotations"], actual["quotations_with_verbs"] = parse_quotation_reference(
                    quotes.to_gkg()
                )
            groups = ["month/" + row.get("sample_month", record_id[:6])]
            if row.get("novel_source") is True:
                groups.append("novel_sources")
            original_wc = reference["gcam"].get("wc", 0)
            if original_wc > 0:
                # Use the same tokenizer as the earlier body-length diagnostic.
                if abs(len(tokenize_tone(text)) / original_wc - 1) <= 0.1:
                    groups.append("word_count_within_10_percent")
            for name, actual_values in actual.items():
                if reference[name] is None:
                    continue
                pairs[name].append((reference[name], actual_values))
                for group in groups:
                    subset_pairs[group][name].append((reference[name], actual_values))
            audit["recognized_location_mentions"] += len(ner.locations)
            audit["resolved_location_mentions"] += len(locations.mentions)
            audit["unknown_locations"] += sum(m.reason == "unknown-place" for m in locations.issues)
            audit["ambiguous_locations"] += sum(
                m.reason == "ambiguous-place" for m in locations.issues
            )
        audit["articles"] += 1
        sources.add(row.get("source", row["url"]))
        if fields_only:
            continue
        assert gcam is not None and lexicon is not None
        original_wc = reference["gcam"].get("wc", 0)
        if original_wc > 0 and gcam.word_count > 0:
            observed = {
                key[1:]
                for key, value in reference["gcam"].items()
                if key != "wc" and (key.startswith("v") or value > 0)
            }
            native_dimensions.update(observed)
            supported_native_dimensions.update(observed & implemented)
            native_assignments += len(observed)
            supported_native_assignments += len(observed & implemented)
            for dimension in observed:
                family = dimension.split(".")[0]
                family_assignments[family] += 1
                if dimension in implemented:
                    family_supported_assignments[family] += 1
            for key, value in reference["gcam"].items():
                if key.startswith("c") and value > 0:
                    native_occurrences += value
                    family_occurrences[key[1:].split(".")[0]] += value
                    if key[1:] in implemented:
                        supported_native_occurrences += value
                        family_supported_occurrences[key[1:].split(".")[0]] += value
            wc_errors.append(abs(gcam.word_count - original_wc))
            wc_ratios.append(gcam.word_count / original_wc)
            for key in dimensions:
                if "v" + key[1:] in lexicon.weighted_dimensions and key not in reference["gcam"]:
                    count_exclusions[key] += 1
                    continue
                original = reference["gcam"].get(key, 0)
                count_pairs[key].append((original, gcam.counts[key]))
                errors[key].append(abs(gcam.counts[key] - original))
                density_errors[key].append(
                    abs(100 * gcam.counts[key] / gcam.word_count - 100 * original / original_wc)
                )
            for key in value_pairs:
                count_key = "c" + key[1:]
                # Real GKG archives often emit the weighted value without the
                # companion count advertised in the master codebook. A value,
                # including zero, establishes that its mean is defined.
                native_has_matches = (
                    key in reference["gcam"] or reference["gcam"].get(count_key, 0) > 0
                )
                local_has_matches = gcam.counts[count_key] > 0
                if key in reference["gcam"] and count_key not in reference["gcam"]:
                    value_audit[key]["reference_match_count_unreported"] += 1
                if key in reference["gcam"] and reference["gcam"].get(count_key, 1) <= 0:
                    value_audit[key]["inconsistent_reference_value_with_nonpositive_count"] += 1
                    continue
                if native_has_matches and local_has_matches:
                    if key not in reference["gcam"]:
                        value_audit[key]["missing_reference_value"] += 1
                    else:
                        value_pairs[key].append((reference["gcam"][key], gcam.values[key]))
                elif native_has_matches:
                    value_audit[key]["reference_matches_only"] += 1
                elif local_has_matches:
                    value_audit[key]["local_matches_only"] += 1
                else:
                    value_audit[key]["both_no_matches"] += 1
        else:
            audit["excluded_gcam_no_word_count"] += 1
    return {
        "schema": "gdelt-regkg/field-benchmark/v2",
        "corpus_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
        "archives": manifest,
        "profiles": {
            "ner": None if gcam_only else getattr(recognizer, "name", type(recognizer).__name__),
            "gazetteer": None if gazetteer is None else gazetteer.name,
            "gcam": None if lexicon is None else lexicon.name,
            "ner_name_policy": None if gcam_only else getattr(recognizer, "name_policy", None),
        },
        "resource_sha256": {
            name: hashlib.sha256(
                resource_path("lexicons", name, resources_dir=resources_dir).read_bytes()
            ).hexdigest()
            for name in (
                (
                    ()
                    if gcam_only
                    else (
                        read_resource_json("defaults.json", resources_dir=resources_dir)[
                            "locations"
                        ],
                    )
                )
                + (
                    (read_resource_json("defaults.json", resources_dir=resources_dir)["gcam"],)
                    if not fields_only and gcam_lexicon is None
                    else ()
                )
            )
        },
        "gcam_configuration_sha256": None
        if lexicon is None
        else hashlib.sha256(
            json.dumps(
                {
                    "name": lexicon.name,
                    "dimensions": {key: sorted(words) for key, words in lexicon.dimensions.items()},
                    "weighted_dimensions": {
                        key: dict(scores) for key, scores in lexicon.weighted_dimensions.items()
                    },
                    "patterns": dict(lexicon.patterns),
                    "tokenization": dict(lexicon.tokenization),
                    "lemmatization": dict(lexicon.lemmatization),
                    "exceptions": dict(lexicon.exceptions),
                    "theme_dimensions": dict(lexicon.theme_dimensions),
                    "theme_rules": [
                        {
                            "theme": r.theme,
                            "phrase": r.phrase,
                            "requires_all": r.requires_all,
                            "exclude_any": r.exclude_any,
                        }
                        for r in lexicon.theme_lexicon.rules
                    ]
                    if lexicon.theme_lexicon is not None
                    else [],
                },
                sort_keys=True,
            ).encode()
        ).hexdigest(),
        "engine_sha256": engine_checksums,
        "audit": dict(audit),
        "sources": len(sources),
        "evaluation": {
            "identity_policy": "Per-document sets, ignoring offsets and repetition",
            "quotation_policy": "Exact complete wire content after NFKC, casefold, apostrophe normalization and whitespace collapse; punctuation retained",
            "amount_values_policy": "Numeric values only; diagnostic alongside primary value/object scoring",
            "bootstrap_samples": bootstrap_samples,
            "bootstrap_seed": bootstrap_seed,
            "interval_policy": "95% percentile F1 intervals from resampling documents; conditional on retrieved corpus, not source-clustered or input-mismatch uncertainty",
            "fitting": False,
        },
        "metrics": {
            name: {
                **score_sets(rows),
                **(
                    {"f1_ci95": bootstrap_f1(rows, samples=bootstrap_samples, seed=bootstrap_seed)}
                    if bootstrap_samples
                    else {}
                ),
            }
            for name, rows in pairs.items()
        },
        "subsets": {
            group: {name: score_sets(rows) for name, rows in fields.items()}
            for group, fields in sorted(subset_pairs.items())
        },
        "gcam": None
        if lexicon is None or codebook is None
        else {
            "coverage": {
                "codebook_sha256": codebook["source_sha256"],
                "codebook_dimensions": len(inventory),
                "implemented_dimensions": len(implemented & inventory),
                "implemented_outside_codebook": sorted(implemented - inventory),
                "dimension_fraction": len(implemented & inventory) / len(inventory),
                "native_observed_dimensions": len(native_dimensions),
                "supported_native_observed_dimensions": len(supported_native_dimensions),
                "native_document_dimension_assignments": native_assignments,
                "supported_native_document_dimension_assignments": supported_native_assignments,
                "native_assignment_fraction": supported_native_assignments / native_assignments
                if native_assignments
                else None,
                "native_count_occurrences": native_occurrences,
                "supported_native_count_occurrences": supported_native_occurrences,
                "native_count_occurrence_fraction": supported_native_occurrences
                / native_occurrences
                if native_occurrences
                else None,
                "policy": "Conceptual c/v pairs counted once; occurrence coverage uses positive native count keys only",
            },
            "families": {
                family: {
                    "implemented_dimensions": sum(d.split(".")[0] == family for d in implemented),
                    "codebook_dimensions": sum(d.split(".")[0] == family for d in inventory),
                    "native_count_occurrences": family_occurrences[family],
                    "supported_native_count_occurrences": family_supported_occurrences[family],
                    "native_assignment_fraction": family_supported_assignments[family]
                    / family_assignments[family]
                    if family_assignments[family]
                    else None,
                    "count_wape": sum(
                        sum(errors[k]) for k in dimensions if k[1:].split(".")[0] == family
                    )
                    / sum(
                        sum(x for x, _ in count_pairs[k])
                        for k in dimensions
                        if k[1:].split(".")[0] == family
                    )
                    if sum(
                        sum(x for x, _ in count_pairs[k])
                        for k in dimensions
                        if k[1:].split(".")[0] == family
                    )
                    else None,
                    "density_mae_percentage_points": statistics.mean(
                        e
                        for k in dimensions
                        if k[1:].split(".")[0] == family
                        for e in density_errors[k]
                    )
                    if any(density_errors[k] for k in dimensions if k[1:].split(".")[0] == family)
                    else None,
                    "median_count_pearson_supported": statistics.median(
                        r
                        for k in dimensions
                        if k[1:].split(".")[0] == family
                        and sum(x > 0 for x, _ in count_pairs[k]) >= 20
                        and (r := _correlation(count_pairs[k])) is not None
                    )
                    if any(
                        k[1:].split(".")[0] == family
                        and sum(x > 0 for x, _ in count_pairs[k]) >= 20
                        and _correlation(count_pairs[k]) is not None
                        for k in dimensions
                    )
                    else None,
                    "presence": _presence_metrics(count_pairs, family),
                }
                for family in sorted({d.split(".")[0] for d in implemented}, key=int)
            },
            "evaluated_dimensions": list(dimensions) + list(lexicon.weighted_dimensions),
            "word_count_mae": statistics.mean(wc_errors) if wc_errors else None,
            "median_word_count_ratio": statistics.median(wc_ratios) if wc_ratios else None,
            "dimensions": {
                key: {
                    "articles": len(errors[key]),
                    "excluded_unreported_native_count": count_exclusions[key],
                    "count_mae": statistics.mean(errors[key]) if errors[key] else None,
                    "count_bias": statistics.mean(y - x for x, y in count_pairs[key])
                    if count_pairs[key]
                    else None,
                    "count_pearson": _correlation(count_pairs[key]),
                    "reference_nonzero_articles": sum(x > 0 for x, _ in count_pairs[key]),
                    "predicted_nonzero_articles": sum(y > 0 for _, y in count_pairs[key]),
                    "density_mae_percentage_points": statistics.mean(density_errors[key])
                    if density_errors[key]
                    else None,
                }
                for key in dimensions
            },
            "values": {
                key: {
                    "paired_articles": len(rows),
                    "value_mae": statistics.mean(abs(y - x) for x, y in rows) if rows else None,
                    "value_bias": statistics.mean(y - x for x, y in rows) if rows else None,
                    "pearson": _correlation(rows),
                    "sign_agreement": statistics.mean(
                        (x > 0) - (x < 0) == (y > 0) - (y < 0) for x, y in rows
                    )
                    if rows
                    else None,
                    "audit": dict(value_audit[key]),
                }
                for key, rows in value_pairs.items()
            },
        },
        "limitations": [
            "Saved bodies can differ from GDELT's original body",
            "Set scoring ignores offsets and repeated mentions",
            "Amount scoring requires matching numeric value and normalized object",
            "Quotation scoring requires complete content identity; changed boundaries and punctuation can lower agreement",
            "Malformed native fields are excluded only from their corresponding metrics; amount-value diagnostics share amount exclusions",
            "GCAM scores cover declared implemented dimensions only",
            "Value errors require a native value and local matches; native companion counts are checked when present",
            "Missing native weighted match counts are unreported, not measured zeros; they are excluded from count errors",
            "Dimension and occurrence coverage measure computable keys, independently of matching agreement",
            "Family correlations require at least 20 native-positive articles; WAPE divides absolute count error by native counts",
            "A sample-size limit selects record IDs in order and is not source-balanced",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resources-dir",
        type=Path,
        default=Path("local-resources"),
        help="Directory containing prepared profiles and defaults.json",
    )
    parser.add_argument(
        "--corpus",
        type=Path,
        required=True,
        help="Saved results.jsonl with analyzed text, URL and original record ID",
    )
    parser.add_argument("--archives", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ner-model", default="en_core_web_sm")
    parser.add_argument("--sample-size", type=int)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--gcam-only", action="store_true", help="Score GCAM without loading NER")
    mode.add_argument(
        "--fields-only", action="store_true", help="Score text fields without recomputing GCAM"
    )
    parser.add_argument(
        "--bootstrap-samples",
        type=int,
        default=0,
        help="Document bootstrap samples for 95%% F1 intervals; zero disables",
    )
    parser.add_argument("--bootstrap-seed", type=int, default=1729)
    parser.add_argument("--gcam-lexicon", type=Path, help="Explicit GCAM profile JSON")
    parser.add_argument(
        "--include-translated",
        action="store_true",
        help="Use saved translated English bodies; does not perform translation",
    )
    args = parser.parse_args()
    result = benchmark_fields(
        args.corpus,
        args.archives,
        resources_dir=args.resources_dir,
        recognizer=None
        if args.gcam_only
        else SpacyNER.from_model(args.ner_model, resources_dir=args.resources_dir),
        sample_size=args.sample_size,
        include_translated=args.include_translated,
        gcam_only=args.gcam_only,
        fields_only=args.fields_only,
        bootstrap_samples=args.bootstrap_samples,
        bootstrap_seed=args.bootstrap_seed,
        gcam_lexicon=GCAMLexicon.from_json(args.gcam_lexicon) if args.gcam_lexicon else None,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"audit": result["audit"], "metrics": result["metrics"], "gcam": result["gcam"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
