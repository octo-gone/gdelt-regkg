"""English GCAM dictionary converters with explicit source/category provenance."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from ..fields.gcam_tokens import tokenize_gcam, valid_gcam_word
from ..fields.rule_inputs import theme_lexicon_from_input
from ..fields.themes import ThemeLexicon, ThemeRule
from ..fields.tone import _normalize, tokenize_tone
from ..gcam_dictionaries import DICTIONARY_IDS
from ..utils import read_resource_json
from .gcam_expansion import _attach, _native, _normalize_term, _source, _wordnet, add_themes
from .gcam_formats import (
    decode,
    member,
    pattern,
    read_cat,
    read_categories,
    read_liwc,
    source_files,
    table_rows,
    xlsx_rows,
)

COUNT_ALIASES = {
    "PRIMARY/REGR_KNOL/TIMELESSNES": "PRIMARY/REGR_KNOL/TIMELESSNESS",
    "PRIMARY/REGR_KNOL/COUNSCIOUS": "PRIMARY/REGR_KNOL/CONSCIOUS",
    "SECONDARY/ABSTRACT_TOUGHT": "SECONDARY/ABSTRACT_THOUGHT",
    "BARRIER TOTAL/CONTAINEERS": "BARRIER TOTAL/CONTAINERS",
    "harm_virtue": "HarmVirtue",
    "harm_vice": "HarmVice",
    "fairness_virtue": "FairnessVirtue",
    "fairness_vice": "FairnessVice",
    "ingroup_virtue": "IngroupVirtue",
    "ingroup_vice": "IngroupVice",
    "authority_virtue": "AuthorityVirtue",
    "authority_vice": "AuthorityVice",
    "purity_virtue": "PurityVirtue",
    "purity_vice": "PurityVice",
    "morality_general": "MoralityGeneral",
    "care.virtue": "HarmVirtue",
    "care.vice": "HarmVice",
    "fairness.virtue": "FairnessVirtue",
    "fairness.vice": "FairnessVice",
    "loyalty.virtue": "IngroupVirtue",
    "loyalty.vice": "IngroupVice",
    "authority.virtue": "AuthorityVirtue",
    "authority.vice": "AuthorityVice",
    "sanctity.virtue": "PurityVirtue",
    "sanctity.vice": "PurityVice",
    "moral": "MoralityGeneral",
}
LIWC_ALIASES = {
    "achieve": "Achievement",
    "relativ": "Relativeness",
    "bio": "Biology",
    "percept": "Perception",
    "excl": "Exclusion",
    "incl": "Inclusion",
    "inhib": "Inhibition",
    "discrep": "Discrepency",
    "negemo": "NegativeEmotion",
    "posemo": "PositiveEmotion",
    "anx": "Anxiety",
    "friend": "Friends",
    "number": "Numbers",
    "adverb": "Adverbs",
    "auxverb": "AuxVb",
    "verb": "Verbs",
    "shehe": "SheHe",
    "ppron": "PersonalPron",
    "ipron": "IPron",
    "preps": "Prep",
    "relig": "Religion",
    "tentat": "Tentative",
}
GI_GAPS = frozenset((10, 13, 29, 32, 43, 63, 89, 100, 105, 126, 155))


def _counts(baseline, source, codebook, component, groups, *, exclusions=()):
    code = DICTIONARY_IDS[component]
    native = _native(codebook, code)
    canonical: dict[str, set[str]] = {}
    aliases = {**COUNT_ALIASES, **(LIWC_ALIASES if code == 5 else {})}
    by_name = {name.casefold(): key for key, name in native.items()}
    for name, terms in groups.items():
        label = aliases.get(name, name)
        key = name if name in native else by_name.get(label.casefold())
        if key is None:
            raise ValueError(
                f"Unmapped {component} source category: {name!r}; supply a codebook-category JSON crosswalk"
            )
        canonical.setdefault(key, set()).update(terms)
    additions = [
        {"key": key, "category": native[key], "patterns": sorted(terms)}
        for key, terms in canonical.items()
        if terms
    ]
    if not additions:
        raise ValueError(f"No usable categories in {component} source")
    result = dict(baseline)
    result["exclusions"] = {**baseline.get("exclusions", {})}
    result["exclusions"].pop(str(code), None)
    if exclusions:
        result["exclusions"][str(code)] = sorted(set(exclusions))
    if not result["exclusions"]:
        result.pop("exclusions")
    return _attach(
        result,
        additions,
        component,
        _source(
            source,
            implemented_dimensions=len(additions),
            unmapped_categories={key: name for key, name in native.items() if key not in canonical},
            matching="longest nonoverlapping pattern per category; source exclusion tokens preserve boundaries",
        ),
        codebook,
    )


def add_count_dictionary(baseline, source, codebook, component):
    """Import .CAT/.dic or explicit category JSON for historical count sources."""
    path = Path(source)
    skipped = []
    if path.suffix.lower() == ".json":
        groups, exclusions = read_categories(path), ()
    elif component in ("liwc", "moral-foundations"):
        groups, exclusions = read_liwc(path), ()
        if component == "liwc":
            allowed = {name.casefold() for name in _native(codebook, 5).values()}
            # LIWC 2007 contains non-GCAM summary categories as well.
            groups = {
                name: terms
                for name, terms in groups.items()
                if LIWC_ALIASES.get(name, name).casefold() in allowed
            }
            if len(groups) != len(allowed):
                raise ValueError(
                    "LIWC requires the 62 GCAM categories from the compatible 2007 edition; use explicit category JSON for another edition"
                )
    else:
        groups, exclusions, skipped = read_cat(path)
    result = _counts(baseline, source, codebook, component, groups, exclusions=exclusions)
    result["sources"][component]["skipped_entries"] = skipped
    if component == "liwc":
        result["sources"][component]["category_aliases"] = {
            name: LIWC_ALIASES[name] for name in groups if name in LIWC_ALIASES
        }
    return result


def add_general_inquirer_legacy(baseline, source, codebook):
    """Recover the eleven tags absent from the basic spreadsheet, case-sensitively."""
    native = {
        key: name for key, name in _native(codebook, 2).items() if int(key.split(".")[1]) in GI_GAPS
    }
    groups = defaultdict(set)
    lines = Path(source).read_text(encoding="utf-8-sig").splitlines()
    if not lines or not lines[0].startswith("Entryword Source "):
        raise ValueError("Expected Harvard's inqdict.txt, including its header")
    skipped = []
    for line in lines[1:]:
        fields = line.split("|", 1)[0].split()
        if len(fields) < 2:
            continue
        term = re.sub(r"#_?\d+$", "", fields[0]).rstrip(">").casefold()
        if tokenize_tone(term) != [term]:
            skipped.append(fields[0])
            continue
        tags = set(fields[2:])
        for key, name in native.items():
            if name in tags:
                groups[key].add(term)
    additions = [
        {"key": key, "category": native[key], "words": sorted(terms)}
        for key, terms in groups.items()
        if terms
    ]
    baseline = {
        **baseline,
        "dimensions": [
            dimension for dimension in baseline["dimensions"] if dimension["key"] not in native
        ],
    }
    return _attach(
        baseline,
        additions,
        "general-inquirer-legacy",
        _source(
            source,
            implemented_dimensions=len(additions),
            skipped_entries=sorted(set(skipped)),
            matching="exact tokens; case-sensitive tag mapping; union of senses",
            unmapped_categories={key: name for key, name in native.items() if not groups[key]},
        ),
        codebook,
    )


def add_authored_themes(baseline, codebook):
    """Add authored phrases while preserving existing rules and provenance."""
    source = read_resource_json("themes", "gcam-experimental.v1.json")
    native = set(_native(codebook, 18).values())
    existing = {rule["theme"] for rule in baseline.get("theme_rules", ())}
    rules = [ThemeRule(**rule) for rule in baseline.get("theme_rules", ())]
    rules.extend(
        rule
        for rule in theme_lexicon_from_input(source).rules
        if rule.theme in native and rule.theme not in existing
    )
    result = add_themes(baseline, codebook, ThemeLexicon(source["name"], tuple(rules)))
    result["name"] += "-authored"
    result["sources"]["themes-authored"] = {
        "status": source["status"],
        "approximation": "authored-rules",
        "approximate_dimensions": sorted(
            set(
                baseline.get("sources", {})
                .get("themes-authored", {})
                .get("approximate_dimensions", [])
            )
            | {
                key[1:]
                for key, category in _native(codebook, 18).items()
                if category in {rule.theme for rule in rules} - existing
            }
        ),
        "source_sha256": hashlib.sha256(json.dumps(source, sort_keys=True).encode()).hexdigest(),
        "deferred_categories": source["deferred_categories"],
        "additional_categories": len({r.theme for r in rules} - existing),
    }
    return result


# Compatibility for callers of the earlier opt-in converter.
add_experimental_themes = add_authored_themes


def add_wordnet_affect_v1(baseline, source, wordnet_source, codebook):
    synsets, exceptions = _wordnet(wordnet_source)
    files = source_files(source)
    labels = {
        "att": "Attitude",
        "beh": "Behaviour",
        "cog": "Cognitive State",
        "eds": "Edonic Signal",
        "emo": "Emotion",
        "moo": "Mood",
        "phy": "Physical State",
        "res": "Emotional Response",
        "sen": "Sensation",
        "sit": "Emotion-Eliciting Situation",
        "tra": "Trait",
    }
    groups: defaultdict[str, set[str]] = defaultdict(set)
    missing = []
    for line in member(files, "wn-affect-labels-1.0.txt").splitlines():
        fields = line.split("|")
        if len(fields) < 3:
            continue
        pos, offset = fields[0].split("#")
        synset = synsets.get(("a" if pos == "s" else pos, offset))
        if synset is None:
            missing.append(fields[0])
            continue
        for label in set(fields[2:]) & labels.keys():
            groups[labels[label]].update(filter(None, map(_normalize_term, synset[1])))
    native = _native(codebook, 14)
    additions = [
        {"key": key, "category": name, "patterns": sorted(groups[name]), "lemmatization": "wordnet"}
        for key, name in native.items()
        if groups[name]
    ]
    return _attach(
        baseline,
        additions,
        "wordnet-affect-1.0",
        _source(
            source,
            wordnet_version="1.6",
            wordnet_source=_source(wordnet_source),
            implemented_dimensions=len(additions),
            missing_synsets=len(missing),
            matching="union of annotated senses; eleven direct labels; WordNet morphology",
        ),
        codebook,
        exceptions=exceptions,
    )


def add_lexicoder_topics(baseline, source, codebook):
    root = ET.fromstring(member(source_files(source), "policy_agendas_english.lcd"))
    if root.tag != "dictionary":
        raise ValueError("Expected the Lexicoder topic XML dictionary")
    groups = defaultdict(set)
    for category in root.findall("cnode"):
        for node in category.findall("pnode"):
            raw = node.attrib["name"]
            term = pattern(raw)
            if term:
                # Legacy .lcd strings encode word boundaries with surrounding spaces.
                term = (
                    ("" if raw[:1].isspace() else "*") + term + ("" if raw[-1:].isspace() else "*")
                )
                groups[category.attrib["name"]].add(term)
    return _counts(baseline, source, codebook, "lexicoder-topics", groups)


def add_subjectivity(baseline, source, codebook):
    groups = defaultdict(set)
    normalizations: list[dict[str, object]] = []
    skipped = []
    files = source_files(source)
    candidates = [
        raw
        for name, raw in files.items()
        if name.endswith((".tff", ".txt")) and "README" not in name.upper()
    ]
    if len(candidates) != 1:
        raise ValueError("Subjectivity source requires one clues .tff/.txt file")
    for number, line in enumerate(decode(candidates[0]).splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        tokens = line.split()
        stray = [item for item in tokens if "=" not in item]
        if stray:
            if stray != ["m"]:
                raise ValueError(f"Malformed subjectivity field at line {number}: {stray!r}")
            tokens.remove("m")
            normalizations.append({"line": number, "removed_tokens": stray})
        row = dict(item.split("=", 1) for item in tokens)
        if row.get("len") != "1" or row.get("type") not in ("strongsubj", "weaksubj"):
            raise ValueError("Subjectivity importer requires length-one strongsubj/weaksubj clues")
        polarity = row.get("priorpolarity")
        # This historical row supplies its intended polarity separately. Use
        # that explicit value rather than dropping the clue or guessing a label.
        if polarity == "weakneg" and row.get("polarity") == "negative":
            polarity = "negative"
            normalizations.append(
                {
                    "line": number,
                    "field": "priorpolarity",
                    "original": "weakneg",
                    "normalized": polarity,
                    "basis": "polarity=negative in source row",
                }
            )
        if polarity not in ("both", "negative", "neutral", "positive"):
            raise ValueError("Unknown subjectivity prior polarity")
        if row.get("stemmed1") == "1":
            skipped.append(
                {"line": number, "word": row["word1"], "reason": "unrecognized stemmed1=1"}
            )
            continue
        if row.get("stemmed1") not in ("y", "n"):
            raise ValueError("Unknown subjectivity stem flag")
        term = pattern(row["word1"] + ("*" if row["stemmed1"] == "y" else ""))
        for category in (row["type"], "tone" + polarity, row["type"] + "tone" + polarity):
            groups[category].add(term)
    result = _counts(baseline, source, codebook, "subjectivity", groups)
    result["sources"]["subjectivity"]["normalizations"] = normalizations
    result["sources"]["subjectivity"]["skipped_entries"] = skipped
    return result


def add_opinion_observer(baseline, source, codebook):
    files, groups = source_files(source), {}
    for polarity in ("negative", "positive"):
        groups[polarity] = {
            pattern(line.strip())
            for line in member(files, polarity + "-words.txt").splitlines()
            if line.strip() and not line.startswith(";")
        }
    return _counts(baseline, source, codebook, "opinion-observer", groups)


def add_loughran_mcdonald(baseline, source, codebook):
    rows = table_rows(source)
    columns = {
        "Litigious": "Litigious",
        "ModalStrong": "Strong_Modal",
        "ModalWeak": "Weak_Modal",
        "Negative": "Negative",
        "Positive": "Positive",
        "Uncertainty": "Uncertainty",
    }
    if not rows or not {"Word", *columns.values()} <= rows[0].keys():
        raise ValueError("Expected the Loughran-McDonald master CSV with sentiment columns")
    groups = defaultdict(set)
    for row in rows:
        term = pattern(row["Word"])
        for name, column in columns.items():
            value = int(row[column])
            # Negative years mark words removed from the current edition.
            if value > 0 and term:
                groups[name].add(term)
    return _counts(baseline, source, codebook, "loughran-mcdonald", groups)


def add_central_bank(baseline, source, codebook):
    if Path(source).suffix.lower() == ".json":
        groups = read_categories(source)
    else:
        groups = defaultdict(set)
        rows = xlsx_rows(source, "1 FS Dictionary")
        if (
            rows[0].get("A") != "Word"
            or rows[0].get("B") != "Positive"
            or rows[0].get("C") != "Negative"
        ):
            raise ValueError("Unexpected central-bank dictionary columns")
        for row in rows[1:]:
            term = pattern(row.get("A", ""))
            for column, category in (("B", "POSITIVE"), ("C", "NEGATIVE")):
                if row.get(column) == "1" and term:
                    groups[category].add(term)
        rows = xlsx_rows(source, "3 Non-FS Words")
        if rows[0].get("A") != "Word" or rows[0].get("B") != "Non-FS (neutral)":
            raise ValueError("Unexpected central-bank neutral columns")
        groups["NEUTRAL"].update(
            pattern(row["A"]) for row in rows[1:] if row.get("B") == "1" and row.get("A")
        )
    return _counts(baseline, source, codebook, "central-bank", groups)


def _score(
    baseline, source, codebook, component, groups, *, value_only=False, words=(), skipped=()
):
    native = {
        key: row["category"]
        for key, row in codebook["dimensions"].items()
        if key.startswith(f"v{DICTIONARY_IDS[component]}.")
    }
    # The published codebook lists only c38.1; native records also emit v38.1.
    if component == "french-imagery" and "c38.1" in codebook["dimensions"]:
        native.setdefault("v38.1", codebook["dimensions"]["c38.1"]["category"])
    additions = []
    for key, terms in groups.items():
        if key not in native:
            raise ValueError(f"Score key outside the {component} codebook: {key}")
        scores = {term: math.fsum(values) / len(values) for term, values in terms.items() if values}
        if scores:
            item = {"key": key, "category": native[key], "scores": scores}
            if value_only:
                item["emit_count"] = False
            additions.append(item)
    if words:
        additions.append(
            {"key": "c42.1", "category": "moralwordcount", "words": sorted(set(words))}
        )
    if not additions:
        raise ValueError(f"No supported scores in {component} source")
    return _attach(
        baseline,
        additions,
        component,
        _source(
            source,
            implemented_dimensions=len(additions),
            aggregation="arithmetic mean of distinct source records per normalized token; occurrence-weighted document mean",
            unmapped_categories={key: name for key, name in native.items() if key not in groups},
            skipped_term_policy="multiword and punctuation-split weighted terms omitted",
            skipped_entries=sorted(set(skipped)),
        ),
        codebook,
    )


def _add_score(groups, key, raw_term, raw_score, language="eng"):
    term = (
        _normalize_term(raw_term)
        if language == "eng"
        else _normalize(raw_term).replace("_", " ").strip()
    )
    score = float(raw_score)
    if not math.isfinite(score):
        raise ValueError("Source scores must be finite")
    if term and valid_gcam_word(term, language):
        groups[key][term].append(score)
        return True
    return False


def add_sentiwords(baseline, source, codebook):
    groups: defaultdict[str, defaultdict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    files = source_files(source)
    seen = set()
    skipped: set[str] = set()
    for line in member(files, "SentiWords_1.0.txt").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or line in seen:
            continue
        seen.add(line)
        term, score = line.split("\t")
        lemma, pos = term.rsplit("#", 1)
        if pos not in ("n", "v", "a", "r"):
            raise ValueError("Unknown SentiWords part of speech")
        if not _add_score(groups, "v11.1", lemma, score):
            skipped.add(lemma)
    return _score(baseline, source, codebook, "sentiwords", groups, skipped=skipped)


def add_sentiwordnet(baseline, source, codebook):
    groups: defaultdict[str, defaultdict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    files, seen = source_files(source), set()
    skipped: set[str] = set()
    for line in member(files, "SentiWordNet_3.0.0.txt").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or line in seen:
            continue
        seen.add(line)
        fields = line.split("\t")
        if len(fields) < 5 or fields[0] not in ("n", "v", "a", "r"):
            raise ValueError("Invalid SentiWordNet source row")
        for term in set(fields[4].split()):
            lemma, _ = term.rsplit("#", 1)
            for key, score in (("v10.1", fields[2]), ("v10.2", fields[3])):
                if not 0 <= float(score) <= 1:
                    raise ValueError("SentiWordNet scores must be between zero and one")
                if not _add_score(groups, key, lemma, score):
                    skipped.add(lemma)
    return _score(baseline, source, codebook, "sentiwordnet", groups, skipped=skipped)


def add_ml_senticon(baseline, source, codebook):
    """Import cumulative English layers from XML or explicit score columns."""
    if Path(source).suffix.lower() != ".xml":
        return add_weighted_table(baseline, source, codebook, "ml-senticon")
    from .gcam_multilingual import senticon_groups

    groups, skipped = senticon_groups(source, codebook, "eng", 20)
    return _score(baseline, source, codebook, "ml-senticon", groups, skipped=skipped)


def add_weighted_table(baseline, source, codebook, component, *, progress=None):
    """Import ANEW/ML-SENTICON interchange tables, labMT, or eMFD CSV."""
    audit = None
    if component == "french-imagery" and Path(source).suffix.lower() == ".pdf":
        from .french_imagery import convert_pdf

        converted, audit = convert_pdf(
            Path(source).read_bytes(),
            progress=progress,
            draft_path=Path(source).with_suffix(".ocr.txt"),
        )
        rows = list(csv.DictReader(io.StringIO(converted.decode("utf-8"))))
    else:
        rows = _weighted_rows(source, component)
    groups: defaultdict[str, defaultdict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    words: set[str] = set()
    seen = set()
    skipped: set[str] = set()
    column_map = {
        key: row["category"].removesuffix(" (Scored Value)")
        for key, row in codebook["dimensions"].items()
        if key.startswith(f"v{DICTIONARY_IDS[component]}.")
    }
    if component == "hedonometer":
        column_map = {"v21.1": "happiness_average"}
    elif component == "french-imagery":
        column_map = {"v38.1": "ImageryValence"}
    term_column = next(
        (name for name in ("word", "Word", "term", "lemma") if name in rows[0]), None
    )
    if term_column is None or not set(column_map.values()) <= rows[0].keys():
        raise ValueError(
            f"{component} requires a word column and columns: {', '.join(column_map.values())}"
        )
    for row in rows:
        identity = tuple(sorted(row.items()))
        if identity in seen:
            continue
        seen.add(identity)
        language = next(
            (
                row.get("language", "eng")
                for key, row in codebook["dimensions"].items()
                if key in column_map or "v" + key[1:] in column_map
            ),
            "eng",
        )
        term = (
            _normalize_term(row[term_column])
            if language == "eng"
            else _normalize(row[term_column]).strip()
        )
        if not term or tokenize_gcam(term, language) != [term]:
            skipped.add(row[term_column])
            continue
        words.add(term)
        for key, column in column_map.items():
            if row[column] != "":
                if (
                    component in ("french-imagery", "portuguese-emotion")
                    and not 10 <= float(row[column]) <= 70
                ):
                    raise ValueError(f"{component} ratings must be between 10 and 70")
                _add_score(groups, key, term, row[column], language)
    result = _score(
        baseline,
        source,
        codebook,
        component,
        groups,
        value_only=component == "emfd",
        words=words if component == "emfd" else (),
        skipped=skipped,
    )
    if component == "french-imagery" and any(row.get("approximation") for row in rows):
        if any(row.get("approximation") != "class-midpoint" for row in rows):
            raise ValueError("French imagery approximation metadata must be consistent")
        result["sources"][component].update(
            approximation="class-midpoint",
            approximate_dimensions=["38.1"],
            review_status=sorted({row.get("review_status", "unverified") for row in rows}),
            source_pdf_sha256=sorted({row.get("source_pdf_sha256", "") for row in rows}),
        )
        if audit is not None:
            result["sources"][component]["conversion_audit"] = audit
    return result


def _weighted_rows(source, component):
    if component != "hedonometer" or Path(source).suffix.lower() != ".json":
        return table_rows(source)
    payload = json.loads(Path(source).read_text(encoding="utf-8"))
    rows = payload.get("objects")
    if (
        not isinstance(rows, list)
        or not rows
        or payload.get("meta", {}).get("total_count") != len(rows)
    ):
        raise ValueError("Hedonometer JSON must contain the complete word list, without pagination")
    if any(row.get("wordlist", {}).get("title") != "labMT-en-v1" for row in rows):
        raise ValueError("Expected the English labMT-en-v1 word list")
    return [{"word": row["word"], "happiness_average": str(row["happs"])} for row in rows]


IMPORTERS = {
    "general-inquirer-legacy": add_general_inquirer_legacy,
    "lexicoder-topics": add_lexicoder_topics,
    "subjectivity": add_subjectivity,
    "opinion-observer": add_opinion_observer,
    "loughran-mcdonald": add_loughran_mcdonald,
    "central-bank": add_central_bank,
    "sentiwords": add_sentiwords,
    "sentiwordnet": add_sentiwordnet,
    "ml-senticon": add_ml_senticon,
}
