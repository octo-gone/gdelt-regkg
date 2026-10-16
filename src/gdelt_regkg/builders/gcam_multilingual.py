"""Published native-language GCAM sources with explicit codebook mappings."""

from __future__ import annotations

import csv
import json
import math
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any

from ..fields.translation import normalize_language
from ..gcam_dictionaries import DICTIONARY_IDS
from .gcam_expansion import _native
from .gcam_formats import decode, read_cat, source_files

RID_LANGUAGES = {
    "rid-french": "fra",
    "rid-portuguese": "por",
    "rid-swedish": "swe",
    "rid-german": "deu",
    "rid-hungarian": "hun",
}
LABMT_LANGUAGES = {
    "ar": "ara",
    "de": "deu",
    "fr": "fra",
    "hi": "hin",
    "id": "ind",
    "ko": "kor",
    "pt": "por",
    "ru": "rus",
    "es": "spa",
    "ur": "urd",
    "zh": "zho",
}
SPANISH_WORDS = 1034


def category_identity(label):
    """Fold source/codebook category spelling; dictionary vocabulary keeps accents."""
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", label.casefold())
        if not unicodedata.combining(char) and char != "."
    )


def add_rid(baseline, source, codebook, component):
    from .gcam_imports import _counts

    language = RID_LANGUAGES[component]
    encoding = "cp1250" if language == "hun" else "cp1252"
    groups, exclusions, skipped = read_cat(source, encoding=encoding, language=language)
    native = _native(codebook, DICTIONARY_IDS[component])
    by_name = {category_identity(name): key for key, name in native.items()}
    mapped = {}
    crosswalk = {}
    for name, terms in groups.items():
        identity = category_identity(name)
        # The native Hungarian edition labels the primary-process root EMOTIONS.
        if language == "hun" and identity.startswith("elsodleges/"):
            identity = "emotions/" + identity.split("/", 1)[1]
        key = by_name.get(identity)
        if key is None:
            raise ValueError(f"Unmapped {component} category: {name}")
        mapped[key] = terms
        crosswalk[name] = key
    result = _counts(baseline, source, codebook, component, mapped, exclusions=exclusions)
    result["sources"][component].update(
        encoding=encoding,
        category_crosswalk=crosswalk,
        skipped_entries=skipped,
        morphology="source wildcards only; no inferred language stemming",
    )
    return result


def senticon_groups(source, codebook, language, dictionary):
    from .gcam_imports import _add_score

    root = ET.fromstring(Path(source).read_bytes())
    if root.tag != "senticon" or normalize_language(root.attrib.get("lang", "")) != language:
        raise ValueError(
            f"ML-SENTICON requires an {'English' if language == 'eng' else language} source"
        )
    keys = {
        (row["language"], row["category"].removesuffix(" (Scored Value)")): key
        for key, row in codebook["dimensions"].items()
        if key.startswith(f"v{dictionary}.")
    }
    layers = {}
    for layer in root.findall("layer"):
        level = int(layer.attrib["level"])
        if level not in range(1, 9) or level in layers:
            raise ValueError("ML-SENTICON requires unique layer levels from 1 to 8")
        layers[level] = layer
    if not layers:
        raise ValueError("ML-SENTICON source has no layers")
    cumulative: dict[str, dict[Any, tuple[str, float]]] = {"positive": {}, "negative": {}}
    groups: defaultdict[str, defaultdict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    skipped = set()
    for level, layer in sorted(layers.items()):
        for polarity, records in cumulative.items():
            for node in layer.findall(f"{polarity}/lemma"):
                term, score = node.text or "", float(node.attrib["pol"])
                if (
                    not math.isfinite(score)
                    or not -1 <= score <= 1
                    or (polarity == "positive" and score < 0)
                    or (polarity == "negative" and score > 0)
                ):
                    raise ValueError("ML-SENTICON polarity must be signed and between -1 and 1")
                records[term, tuple(sorted(node.attrib.items()))] = (term, score)
            key = keys.get((language, f"Level{level}{polarity.title()}"))
            if key is None:
                raise ValueError("ML-SENTICON layer missing from the native codebook")
            for term, score in records.values():
                if not _add_score(groups, key, term, score, language):
                    skipped.add(term)
    return groups, skipped


def add_senticon_languages(baseline, sources, codebook):
    from .gcam_imports import _score

    groups, skipped = {}, set()
    for code, language in (("ca", "cat"), ("es", "spa"), ("gl", "glg")):
        part, omitted = senticon_groups(sources["ml-senticon-" + code], codebook, language, 23)
        groups.update(part)
        skipped.update(omitted)
    result = _score(
        baseline, sources, codebook, "ml-senticon-multilingual", groups, skipped=skipped
    )
    result["sources"]["ml-senticon-multilingual"]["layers"] = (
        "cumulative; inherited distinct source records retained"
    )
    return result


def add_spanish_anew(baseline, source, codebook):
    from .gcam_imports import _add_score, _score

    files = source_files(source)
    candidates = [
        raw
        for name, raw in files.items()
        if name.rsplit("/", 1)[-1].casefold() == "redondo(2007).txt"
    ]
    if len(candidates) != 1:
        raise ValueError("Spanish ANEW requires the original Redondo(2007).txt table")
    rows = list(csv.DictReader(decode(candidates[0], "cp1252").splitlines(), delimiter="\t"))
    if len(rows) != SPANISH_WORDS or len({row["Number"] for row in rows}) != len(rows):
        raise ValueError(f"Spanish ANEW requires {SPANISH_WORDS} distinct word records")
    columns = [
        f"{rating}-Mn-{group}"
        for group in ("All", "Fem", "Mal")
        for rating in ("Val", "Aro", "Dom")
    ] + ["Fam", "Con", "Imag"]
    groups: defaultdict[str, defaultdict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    skipped: set[str] = set()
    unavailable = 0
    for row in rows:
        row = {key.strip(): value.strip() for key, value in row.items()}
        for index, column in enumerate(columns, 1):
            value = row[column]
            if value.casefold() in {"", "unav"}:
                unavailable += 1
                continue
            if not _add_score(
                groups, f"v22.{index}", row["S-Word"], value.replace(",", "."), "spa"
            ):
                skipped.add(row["S-Word"])
    result = _score(baseline, source, codebook, "anew-spanish", groups, skipped=skipped)
    result["sources"]["anew-spanish"].update(
        records=len(rows), unavailable_ratings=unavailable, encoding="cp1252"
    )
    return result


def add_labmt_languages(baseline, sources, codebook):
    from .gcam_imports import _add_score, _score

    groups: defaultdict[str, defaultdict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    skipped: set[str] = set()
    keys = {
        row["language"]: key
        for key, row in codebook["dimensions"].items()
        if key.startswith("v24.")
    }
    for code, language in LABMT_LANGUAGES.items():
        payload = json.loads(Path(sources["hedonometer-" + code]).read_text(encoding="utf-8"))
        rows = payload.get("objects", [])
        if (
            not rows
            or payload.get("meta", {}).get("total_count") != len(rows)
            or payload["meta"].get("next")
        ):
            raise ValueError("Hedonometer requires a complete unpaginated word list")
        if any(row.get("wordlist", {}).get("title") != f"labMT-{code}-v1" for row in rows):
            raise ValueError("Hedonometer word-list identity mismatch")
        for row in rows:
            score = float(row["happs"])
            if not 1 <= score <= 9:
                raise ValueError("Hedonometer happiness must be between 1 and 9")
            if not _add_score(groups, keys[language], row["word"], score, language):
                skipped.add(row["word"])
    result = _score(
        baseline, sources, codebook, "hedonometer-multilingual", groups, skipped=skipped
    )
    result["sources"]["hedonometer-multilingual"].update(
        acquired_languages=list(LABMT_LANGUAGES.values()),
        deferred_languages=[],
        chinese_segmentation="jieba standard dictionary; HMM=False; supplied by build extra",
    )
    return result
