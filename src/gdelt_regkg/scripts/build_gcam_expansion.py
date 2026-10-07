"""Compile native GCAM categories from published, versioned dictionaries.

No article bodies or GDELT reference scores are used to build the dictionaries.
Roget is supplied separately because redistribution terms are not established.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import tarfile
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from gdelt_regkg.gcam import _load, _order, read_gcam_json
from gdelt_regkg.themes import default_theme_lexicon
from gdelt_regkg.tone import tokenize_tone
from gdelt_regkg.utils import read_resource_json

from .build_gcam_lexicon import CATEGORIES, extend_gcam_lexicon
from .build_resources import download_source

GI_ALIASES = {
    "Acad": "Academ",
    "AbsOther": "Abs@",
    "Complt": "Complet",
    "Decr": "Decreas",
    "Doctr": "Doctrin",
    "EconOther": "Econ@",
    "Exprs": "Exprsv",
    "Incr": "Increas",
    "KinOther": "Kin@",
    "Natpro": "NatrPro",
    "Percv": "Perceiv",
    "Pleasure": "Pleasur",
    "PolitOther": "Polit@",
    "Qual": "Quality",
    "Strng": "Strong",
    "Subm": "Submit",
    "Eval": "Eval@",
    "TimeOther": "Time@",
    "ARENAS": "ArenaLw",
    "ENDS": "EndsLw",
    "FORM": "FormLw",
    "NOT": "NotLw",
    "NATIONS": "Nation",
    "POWAPT": "PowAuPt",
    "RCTENDS": "RcEnds",
    "RCTETH": "RcEthic",
    "RCTGAIN": "RcGain",
    "RCTLOSS": "RcLoss",
    "RCTREL": "RcRelig",
    "RCTTOT": "RcTot",
    "SKLAS": "SklAsth",
    "SURE": "SureLw",
    "TIMESP": "TimeSpc",
    "TRANS": "TranLw",
}


def read_codebook(path=None, *, resources_dir=None):
    if path is None:
        return read_resource_json("gcam", "codebook.v1.json", resources_dir=resources_dir)
    raw = Path(path).read_bytes()
    rows = list(csv.DictReader(raw.decode("latin1").splitlines(), delimiter="\t"))
    if not rows or not {"Variable", "DictionaryID", "DimensionHumanName"} <= set(rows[0]):
        raise ValueError("Expected the GCAM master codebook TSV")
    dimensions = {}
    for row in rows:
        key = row["Variable"]
        if key in dimensions:
            raise ValueError("Duplicate codebook key")
        dimensions[key] = {
            "category": row["DimensionHumanName"],
            "dictionary": row["DictionaryHumanName"],
            "language": row["LanguageCode"],
            "type": row["Type"],
        }
    return {
        "source_url": "http://data.gdeltproject.org/documentation/GCAM-MASTER-CODEBOOK.TXT",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "dimensions": dimensions,
        "identity_conflicts": [
            {
                "key": row["Variable"],
                "dictionary_id": row["DictionaryID"],
                "dimension_id": row["DimensionID"],
            }
            for row in rows
            if row["Variable"][1:] != row["DictionaryID"] + "." + row["DimensionID"]
        ],
    }


def _native(codebook, dictionary):
    return {
        key: row["category"]
        for key, row in codebook["dimensions"].items()
        if key.startswith(f"c{dictionary}.")
    }


def _source(path, **metadata):
    path = Path(path)
    if path.is_dir():
        digest = hashlib.sha256()
        for member in sorted(p for p in path.rglob("*") if p.is_file()):
            digest.update(member.relative_to(path).as_posix().encode() + b"\0")
            digest.update(member.read_bytes())
        checksum = digest.hexdigest()
    else:
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"sha256": checksum, **metadata}


def _attach(baseline, additions, family, metadata, codebook, *, exceptions=None):
    result = copy.deepcopy(baseline)
    replaced = {d["key"] for d in additions}
    result["dimensions"] = [d for d in result["dimensions"] if d["key"] not in replaced] + additions
    result["dimensions"].sort(key=lambda d: _order(d["key"]))
    result["name"] = baseline["name"] + "-" + family
    result.setdefault("sources", {})[family] = metadata
    result["codebook_sha256"] = codebook["source_sha256"]
    if exceptions:
        merged = defaultdict(set)
        for form, lemmas in result.get("exceptions", {}).items():
            merged[form].update(lemmas)
        for form, lemmas in exceptions.items():
            merged[form].update(lemmas)
        result["exceptions"] = {form: sorted(lemmas) for form, lemmas in sorted(merged.items())}
    _load(result)
    return result


def add_general_inquirer(baseline, source, codebook):
    rows = list(
        csv.DictReader(Path(source).read_text(encoding="utf-8-sig").splitlines(), delimiter="\t")
    )
    if not rows or not {"Entry", "Source", "Othtags"} <= set(rows[0]):
        raise ValueError("Expected the General Inquirer basic TSV")
    native = _native(codebook, 2)
    headers = set(rows[0]) - {"Entry", "Source", "Othtags", "Defined"}
    tags = {tag for row in rows for tag in row["Othtags"].split()}
    source_tags = {row["Source"] for row in rows}
    native_case = Counter(name.casefold() for name in native.values())
    mappings = {}
    for key, name in native.items():
        if name in headers:
            mappings[key] = ("column", name)
        elif name in tags:
            mappings[key] = ("tag", name)
        elif name in source_tags:
            mappings[key] = ("source", name)
        elif name in GI_ALIASES and GI_ALIASES[name] in headers:
            mappings[key] = ("column", GI_ALIASES[name])
        elif native_case[name.casefold()] == 1:
            columns = [h for h in headers if h.casefold() == name.casefold()]
            matching_tags = [t for t in tags if t.casefold() == name.casefold()]
            if len(columns) == 1:
                mappings[key] = ("column", columns[0])
            elif len(matching_tags) == 1:
                mappings[key] = ("tag", matching_tags[0])
    vocabularies: dict[str, set[str]] = {key: set() for key in mappings}
    skipped = set()
    for row in rows:
        word = re.sub(r"#_?\d+$", "", row["Entry"]).rstrip(">").casefold()
        if tokenize_tone(word) != [word]:
            skipped.add(word)
            continue
        row_tags = set(row["Othtags"].split())
        for key, (kind, name) in mappings.items():
            hit = (
                bool(row[name].strip())
                if kind == "column"
                else name in row_tags
                if kind == "tag"
                else row["Source"] == name
            )
            if hit:
                vocabularies[key].add(word)
    additions = [
        {"key": key, "category": native[key], "words": sorted(words)}
        for key, words in vocabularies.items()
        if words
    ]
    # Preserve the published baseline's eight categories exactly. Their legacy
    # importer discarded a small number of unusual sense suffixes.
    previous = {
        d["key"]: d for d in baseline["dimensions"] if "words" in d and d["key"] in CATEGORIES
    }
    preserved = []
    for dimension in additions:
        if dimension["key"] in previous:
            dimension["words"] = copy.deepcopy(previous[dimension["key"]]["words"])
            preserved.append(dimension["key"])
    return _attach(
        baseline,
        additions,
        "general-inquirer-expanded",
        _source(
            source,
            source_url="https://inquirer.sites.fas.harvard.edu/inqtabs.txt",
            terms_url="https://inquirer.sites.fas.harvard.edu/spreadsheet_guide.htm",
            native_dimensions=len(native),
            implemented_dimensions=len(additions),
            category_mapping={
                key: {"kind": kind, "name": name} for key, (kind, name) in mappings.items()
            },
            unmapped_categories={
                key: name
                for key, name in native.items()
                if key not in {d["key"] for d in additions}
            },
            skipped_entries=sorted(skipped),
            sense_policy="union of senses, without disambiguation",
            preserved_baseline_categories=preserved,
        ),
        codebook,
    )


def _archive_files(path):
    """Read data members only; never extract files or execute archive content."""
    path = Path(path)
    if path.is_dir():
        return {
            str(p.relative_to(path)).replace("\\", "/"): p.read_bytes()
            for p in path.rglob("*")
            if p.is_file()
        }
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            return {
                info.filename: archive.read(info)
                for info in archive.infolist()
                if not info.is_dir() and not info.filename.startswith("__MACOSX/")
            }
    with tarfile.open(path) as archive:
        result = {}
        for info in archive.getmembers():
            if info.isfile():
                stream = archive.extractfile(info)
                if stream is None:
                    raise ValueError(f"Cannot read archive member {info.name}")
                result[info.name] = stream.read()
        return result


def _member(files, filename):
    candidates = [raw for name, raw in files.items() if name.rsplit("/", 1)[-1] == filename]
    if len(candidates) != 1:
        raise ValueError(f"Source requires exactly one {filename}")
    return candidates[0]


def _wordnet(path):
    files = _archive_files(path)
    synsets, exceptions = {}, defaultdict(set)
    for pos, suffix in (("n", "noun"), ("v", "verb"), ("a", "adj"), ("r", "adv")):
        for line in _member(files, "data." + suffix).decode("latin1").splitlines():
            if not line or not line[0].isdigit():
                continue
            fields = line.split("|", 1)[0].split()
            offset, lexname, word_count = fields[0], int(fields[1]), int(fields[3], 16)
            terms = [fields[4 + i * 2] for i in range(word_count)]
            if pos == "a":
                # These are grammatical metadata, not collocation components.
                # https://wordnet.princeton.edu/documentation/wndb5wn
                terms = [re.sub(r"\((?:a|p|ip)\)$", "", word) for word in terms]
            synsets[(pos, offset)] = (lexname, terms)
        for line in _member(files, suffix + ".exc").decode("latin1").splitlines():
            parts = line.casefold().split()
            if len(parts) >= 2 and all(tokenize_tone(p) == [p] for p in parts):
                exceptions[parts[0]].update(parts[1:])
    return synsets, {key: sorted(values) for key, values in exceptions.items()}


def _normalize_term(term):
    # Match the runtime tokenizer, including punctuation splitting of phrases.
    return " ".join(tokenize_tone(term.replace("_", " ")))


def add_roget(baseline, source, wordnet_source, codebook):
    files = _archive_files(source)
    groups = defaultdict(set)
    stack: list[str] = []
    for line in _member(files, "ROGET.CAT").decode("cp1252").splitlines():
        if not line.strip():
            continue
        depth = len(line) - len(line.lstrip("\t"))
        text = line.strip()
        match = re.fullmatch(r"(.+) \(([-+]?\d+(?:\.\d+)?)\)", text)
        if match:
            if float(match[2]) != 1:
                raise ValueError("Roget count importer requires unit-weight source entries")
            term = _normalize_term(match[1])
            if term:
                groups["/".join(stack)].add(term)
        else:
            stack = stack[:depth] + [text]
    native = _native(codebook, 9)
    unknown = set(groups) - set(native.values())
    if unknown:
        raise ValueError(f"Roget category paths differ from the codebook: {sorted(unknown)[:3]}")
    _, exceptions = _wordnet(wordnet_source)
    additions = [
        {
            "key": key,
            "category": category,
            "patterns": sorted(groups[category]),
            "lemmatization": "wordnet",
        }
        for key, category in native.items()
        if groups.get(category)
    ]
    return _attach(
        baseline,
        additions,
        "roget-1911",
        _source(
            source,
            source_url="https://provalisresearch.com/Download/Roget.zip",
            documentation_url="https://www.kovcomp.co.uk/wordstat/Roget.html",
            bundled_with_package=False,
            implemented_dimensions=len(additions),
            normalized_category_entries=sum(len(d["patterns"]) for d in additions),
            morphology_source=_source(wordnet_source),
            matching="longest nonoverlapping phrase per category; WordNet morphology without POS disambiguation",
        ),
        codebook,
        exceptions=exceptions,
    )


def add_wordnet_lexical(baseline, source, codebook):
    synsets, exceptions = _wordnet(source)
    # GCAM category order differs from WordNet lexicographer file numbers.
    names = {
        0: "ADJ/ALL",
        1: "ADJ/PERT",
        2: "ADV/ALL",
        3: "NOUN/TOPS",
        4: "NOUN/ACT",
        5: "NOUN/ANIMAL",
        6: "NOUN/ARTIFACT",
        7: "NOUN/ATTRIBUTE",
        8: "NOUN/BODY",
        9: "NOUN/COGNITION",
        10: "NOUN/COMMUNICATION",
        11: "NOUN/EVENT",
        12: "NOUN/FEELING",
        13: "NOUN/FOOD",
        14: "NOUN/GROUP",
        15: "NOUN/LOCATION",
        16: "NOUN/MOTIVE",
        17: "NOUN/OBJECT",
        18: "NOUN/PERSON",
        19: "NOUN/PHENOMENON",
        20: "NOUN/PLANT",
        21: "NOUN/POSSESSION",
        22: "NOUN/PROCESS",
        23: "NOUN/QUANTITY",
        24: "NOUN/RELATION",
        25: "NOUN/SHAPE",
        26: "NOUN/STATE",
        27: "NOUN/SUBSTANCE",
        28: "NOUN/TIME",
        29: "VERB/BODY",
        30: "VERB/CHANGE",
        31: "VERB/COGNITION",
        32: "VERB/COMMUNICATION",
        33: "VERB/COMPETITION",
        34: "VERB/CONSUMPTION",
        35: "VERB/CONTACT",
        36: "VERB/CREATION",
        37: "VERB/EMOTION",
        38: "VERB/MOTION",
        39: "VERB/PERCEPTION",
        40: "VERB/POSSESSION",
        41: "VERB/SOCIAL",
        42: "VERB/STATIVE",
        43: "VERB/WEATHER",
        44: "ADJ/PPL",
    }
    groups: defaultdict[str, set[str]] = defaultdict(set)
    for lexname, terms in synsets.values():
        groups[names[lexname]].update(filter(None, map(_normalize_term, terms)))
    native = _native(codebook, 17)
    additions = [
        {
            "key": key,
            "category": category,
            "patterns": sorted(groups[category]),
            "lemmatization": "wordnet",
        }
        for key, category in native.items()
        if groups.get(category)
    ]
    return _attach(
        baseline,
        additions,
        "wordnet-lexical-3.1",
        _source(
            source,
            source_url="https://wordnetcode.princeton.edu/wn3.1.dict.tar.gz",
            license="Princeton WordNet license",
            native_dimensions=len(native),
            implemented_dimensions=len(additions),
            omitted_source_categories=["NOUN/TOPS"],
            sense_policy="union of all senses; each occurrence counted once per category",
        ),
        codebook,
        exceptions=exceptions,
    )


def add_wordnet_domains(baseline, annotations, wordnet_source, codebook):
    files = _archive_files(annotations)
    synsets, exceptions = _wordnet(wordnet_source)
    groups, missing = defaultdict(set), []
    for line in _member(files, "wn-domains-3.2-20070223").decode("latin1").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        offset, pos = parts[0].split("-")
        if pos == "s":
            pos = "a"  # Adjective satellites reside in data.adj.
        synset = synsets.get((pos, offset))
        if synset is None:
            missing.append(parts[0])
            continue
        terms = set(filter(None, map(_normalize_term, synset[1])))
        for category in parts[1:]:
            groups[category].update(terms)
    native = _native(codebook, 16)
    additions = [
        {
            "key": key,
            "category": category,
            "patterns": sorted(groups[category]),
            "lemmatization": "wordnet",
        }
        for key, category in native.items()
        if groups.get(category)
    ]
    return _attach(
        baseline,
        additions,
        "wordnet-domains-3.2",
        _source(
            annotations,
            source_url="https://wndomains.fbk.eu/download.html",
            license="CC BY 3.0",
            wordnet_version="2.0",
            wordnet_source=_source(wordnet_source),
            implemented_dimensions=len(additions),
            missing_synsets=len(missing),
            missing_synset_examples=missing[:10],
            unmapped_categories={
                key: category for key, category in native.items() if not groups.get(category)
            },
            sense_policy="union of annotated senses; no unannotated parent propagation",
        ),
        codebook,
        exceptions=exceptions,
    )


def add_wordnet_affect(
    baseline, annotations, wordnet_source, codebook, *, propagate_hierarchy=False, nouns_only=False
):
    files = _archive_files(annotations)
    synsets, exceptions = _wordnet(wordnet_source)
    hierarchy = {
        node.attrib["name"]: node.attrib.get("isa")
        for node in ET.fromstring(_member(files, "a-hierarchy.xml"))
    }
    root = ET.fromstring(_member(files, "a-synsets.xml"))
    noun_list = root.find("noun-syn-list")
    if noun_list is None:
        raise ValueError("WordNet Affect source is missing noun-syn-list")
    noun_categories = {node.attrib["id"]: node.attrib["categ"] for node in noun_list}
    groups, missing, cycles = defaultdict(set), [], set()
    for node in root.iter():
        if "id" not in node.attrib:
            continue
        pos, offset = node.attrib["id"].split("#")
        if nouns_only and pos != "n":
            continue
        synset = synsets.get((pos, offset))
        if synset is None:
            missing.append(node.attrib["id"])
            continue
        category: str | None = node.attrib.get("categ") or noun_categories[node.attrib["noun-id"]]
        terms = set(filter(None, map(_normalize_term, synset[1])))
        visited = set()
        while category:
            if category in visited:
                cycles.add(category)
                break
            visited.add(category)
            groups[category].update(terms)
            if not propagate_hierarchy:
                break
            category = hierarchy.get(category)
    native = _native(codebook, 15)
    # The source contains the documented spelling error "simpathy".
    if "simpathy" in groups:
        groups["sympathy"].update(groups["simpathy"])
    additions = [
        {
            "key": key,
            "category": category,
            "patterns": sorted(groups[category]),
            "lemmatization": "wordnet",
        }
        for key, category in native.items()
        if groups.get(category)
    ]
    return _attach(
        baseline,
        additions,
        "wordnet-affect-1.1",
        _source(
            annotations,
            source_url="https://wndomains.fbk.eu/wnaffect.html",
            license="CC BY 3.0",
            wordnet_version="1.6",
            wordnet_source=_source(wordnet_source),
            implemented_dimensions=len(additions),
            missing_synsets=len(missing),
            missing_synset_examples=missing[:10],
            cyclic_hierarchy_categories=sorted(cycles),
            unmapped_categories={
                key: category for key, category in native.items() if not groups.get(category)
            },
            sense_policy="union of annotated senses; direct labels"
            if not propagate_hierarchy
            else "union of annotated senses with published hierarchy propagation",
            propagate_hierarchy=propagate_hierarchy,
            nouns_only=nouns_only,
        ),
        codebook,
        exceptions=exceptions,
    )


def add_themes(baseline, codebook, lexicon=None):
    lexicon = default_theme_lexicon() if lexicon is None else lexicon
    labels = {rule.theme for rule in lexicon.rules}
    native = _native(codebook, 18)
    additions = [
        {"key": key, "category": category, "theme": category}
        for key, category in native.items()
        if category in labels
    ]
    result = copy.deepcopy(baseline)
    result["theme_rules"] = [
        {
            "theme": rule.theme,
            "phrase": rule.phrase,
            "requires_all": rule.requires_all,
            "exclude_any": rule.exclude_any,
        }
        for rule in lexicon.rules
        if rule.theme in set(native.values())
    ]
    return _attach(
        result,
        additions,
        "gkg-themes",
        {
            "source_profile": lexicon.name,
            "source_sha256": hashlib.sha256(
                json.dumps(result["theme_rules"], sort_keys=True).encode()
            ).hexdigest(),
            "implemented_dimensions": len(additions),
            "matching": "unique matched spans per category; overlapping spans retained; document context guards preserved",
            "unmapped_categories": {
                key: category for key, category in native.items() if category not in labels
            },
        },
        codebook,
    )


def prepare_expansion_downloads(args):
    """Download only explicitly requested dictionaries, checking recipe hashes."""
    if not (args.download_roget or args.download_lexicoder):
        return
    recipe = read_resource_json("recipes.json")
    for source in ("roget", "lexicoder"):
        if not getattr(args, f"download_{source}"):
            continue
        entry = recipe["sources"][source]
        argument = f"{source}_source"
        path = getattr(args, argument) or args.sources_dir / entry["filename"]
        if path.is_dir():
            raise ValueError(f"--download-{source} requires a ZIP file path, not a directory")
        download_source(path, entry)
        setattr(args, argument, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resources-dir",
        type=Path,
        default=Path("local-resources"),
        help="Directory containing prepared profiles and defaults.json",
    )
    parser.add_argument(
        "--baseline", type=Path, help="GCAM JSON; defaults to the selected local profile"
    )
    parser.add_argument(
        "--codebook",
        type=Path,
        help="Master codebook TSV; defaults to the locally prepared snapshot",
    )
    parser.add_argument("--general-inquirer", type=Path)
    parser.add_argument(
        "--sources-dir",
        type=Path,
        default=Path("downloads/resources"),
        help="Destination for requested source downloads (default: downloads/resources)",
    )
    parser.add_argument(
        "--download-roget",
        action="store_true",
        help="Download the recorded Roget ZIP and verify its checksum",
    )
    parser.add_argument(
        "--download-lexicoder",
        action="store_true",
        help="Download the recorded Lexicoder ZIP; review https://www.snsoroka.com/s/LSDagreement.pdf before use",
    )
    parser.add_argument(
        "--lexicoder-source",
        type=Path,
        help="Your original Lexicoder ZIP, LC3 directory or category JSON",
    )
    parser.add_argument(
        "--roget-source", type=Path, help="Separately obtained Roget ZIP or directory"
    )
    parser.add_argument("--wordnet-31", type=Path, help="WordNet 3.1 dict TAR or directory")
    parser.add_argument("--wordnet-lexical", action="store_true")
    parser.add_argument("--wordnet-domains", type=Path, help="Domains 3.2 ZIP or directory")
    parser.add_argument("--wordnet-20", type=Path)
    parser.add_argument("--wordnet-affect", type=Path, help="Affect 1.1 ZIP or directory")
    parser.add_argument("--wordnet-16", type=Path)
    parser.add_argument(
        "--affect-propagate-hierarchy",
        action="store_true",
        help="Include ancestor labels for an explicit comparison",
    )
    parser.add_argument(
        "--affect-nouns-only",
        action="store_true",
        help="Restrict Affect to its noun synsets for an explicit comparison",
    )
    parser.add_argument(
        "--themes",
        action="store_true",
        help="Reuse the selected local theme matcher for native GCAM keys",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for selected, required, flag in (
        (
            args.roget_source or args.download_roget or args.wordnet_lexical,
            args.wordnet_31,
            "--wordnet-31",
        ),
        (args.wordnet_domains, args.wordnet_20, "--wordnet-20"),
        (args.wordnet_affect, args.wordnet_16, "--wordnet-16"),
    ):
        if selected and not required:
            parser.error(f"Selected expansion requires {flag}")
    try:
        prepare_expansion_downloads(args)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    result = (
        read_gcam_json(args.baseline)
        if args.baseline
        else read_resource_json(
            "lexicons",
            read_resource_json("defaults.json", resources_dir=args.resources_dir)["gcam"],
            resources_dir=args.resources_dir,
        )
    )
    codebook = read_codebook(args.codebook, resources_dir=args.resources_dir)
    if args.general_inquirer:
        result = add_general_inquirer(result, args.general_inquirer, codebook)
    if args.roget_source:
        result = add_roget(result, args.roget_source, args.wordnet_31, codebook)
    if args.wordnet_lexical:
        result = add_wordnet_lexical(result, args.wordnet_31, codebook)
    if args.wordnet_affect:
        result = add_wordnet_affect(
            result,
            args.wordnet_affect,
            args.wordnet_16,
            codebook,
            propagate_hierarchy=args.affect_propagate_hierarchy,
            nouns_only=args.affect_nouns_only,
        )
    if args.wordnet_domains:
        result = add_wordnet_domains(result, args.wordnet_domains, args.wordnet_20, codebook)
    if args.themes:
        result = add_themes(result, codebook, default_theme_lexicon(args.resources_dir))
    if args.lexicoder_source:
        name = result["name"]
        result = extend_gcam_lexicon(result, lexicoder_source=args.lexicoder_source)
        result["name"] = name + "-lexicoder-custom"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"name": result["name"], "dimensions": len(_load(result).dimensions)}))


if __name__ == "__main__":
    main()
