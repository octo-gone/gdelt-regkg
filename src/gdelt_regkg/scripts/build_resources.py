"""Prepare local dictionaries from supplied sources and packaged build recipes."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import io
import json
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from gdelt_regkg.rule_inputs import count_rules_from_input, theme_lexicon_from_input
from gdelt_regkg.tone import _parse_lexicon
from gdelt_regkg.utils import packaged_resource_path, read_resource_json

from .build_theme_profile import merge_inputs
from .build_tone_lexicon import build_lexicon


def revise_tone(baseline, edits):
    """Replay the recorded revision without fitting against benchmark bodies."""
    if baseline.get("source_sha256") != edits["base_source_sha256"]:
        raise ValueError("Tone source checksum differs from the recorded revision")
    if (
        "base_dictionary_sha256" in edits
        and hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest()
        != edits["base_dictionary_sha256"]
    ):
        raise ValueError("Tone dictionary checksum differs from the recorded revision")
    result = copy.deepcopy(edits["metadata"])
    for category, changes in edits["changes"].items():
        words = set(baseline[category])
        removals = set(changes.get("remove", ()))
        by_hash = {hashlib.sha256(word.encode()).hexdigest(): word for word in words}
        for digest in changes.get("remove_sha256", ()):
            if digest not in by_hash:
                raise ValueError(f"Revision removes unknown {category} term hash")
            removals.add(by_hash[digest])
        if not removals <= words:
            raise ValueError(f"Revision removes unknown {category} terms")
        result[category] = sorted((words - removals) | set(changes["add"]))
    _parse_lexicon(json.dumps(result))
    return result


def revise_themes(baseline, revision):
    """Replay validated rule replacements and additions against a fixed baseline."""
    checksum = hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest()
    if checksum != revision.get("base_sha256"):
        raise ValueError("Theme baseline checksum differs from the recorded revision")
    revision = copy.deepcopy(revision)
    originals = {rule["id"]: rule for rule in baseline["rules"]}
    for entry in revision.pop("external_rule_overrides", []):
        patch = entry["rule"]
        if patch["id"] not in originals:
            raise ValueError("External theme override requires a matching source rule")
        revision["rules"].insert(
            entry["position"], {**patch, "expression": originals[patch["id"]]["expression"]}
        )
    theme_lexicon_from_input(revision)
    result = copy.deepcopy(baseline)
    result["name"] = revision["name"]
    result["evaluation"] = copy.deepcopy(revision["evaluation"])
    changes = {rule["id"]: rule for rule in revision["rules"]}
    result["rules"] = [copy.deepcopy(changes.pop(rule["id"], rule)) for rule in baseline["rules"]]
    result["rules"].extend(copy.deepcopy(list(changes.values())))
    theme_lexicon_from_input(result)
    return result


def restore_crisislex(authored, source):
    """Merge external phrases into authored rules without storing the vocabulary."""
    from .build_theme_lexicon import build_profile

    data = copy.deepcopy(authored)
    identifiers = data.pop("external_rule_ids", {})
    profile = build_profile(crisislex=Path(source), name="source")
    if profile["sources"] != data["sources"]:
        raise ValueError("CrisisLex source checksum differs from the recorded recipe")
    rules = {rule["expression"]: rule for rule in data["rules"]}
    for phrase in profile["themes"]["CRISISLEX_CRISISLEXREC"]:
        rule = rules.setdefault(
            phrase,
            {
                "id": identifiers.get(
                    hashlib.sha256(phrase.encode()).hexdigest(),
                    "literal-" + hashlib.sha256(phrase.encode()).hexdigest()[:16],
                ),
                "kind": "literal",
                "expression": phrase,
                "labels": [],
                "status": "enabled",
                "provenance": {"evidence": []},
            },
        )
        rule["labels"] = sorted(set(rule["labels"]) | {"CRISISLEX_CRISISLEXREC"})
    data["rules"] = [rule for _, rule in sorted(rules.items())]
    return data


def authored_theme_input():
    """Independent custom rules; no third-party vocabulary or source checksum."""
    first = read_resource_json("themes", "themes-count-candidates-v2.json")
    seeds = read_resource_json("themes", "theme_seeds.json")
    revision = read_resource_json("themes", "revision.v3.json")
    result = merge_inputs([first, seeds], name="authored-themes-v3")
    changes = {rule["id"]: rule for rule in revision["rules"]}
    result["rules"] = [copy.deepcopy(changes.pop(rule["id"], rule)) for rule in result["rules"]]
    result["rules"].extend(changes.values())
    result["sources"] = []
    result["$schema"] = "../schemas/theme-rules.schema.json"
    theme_lexicon_from_input(result)
    return result


def build_resources(
    output,
    *,
    tone_source=None,
    vader_source=None,
    crisislex_source=None,
    codebook_source=None,
    wordnet_31=None,
    wordnet_20=None,
    wordnet_16=None,
    wordnet_annotations=None,
    gazetteer_archives=None,
    authored_themes_only=False,
    fields=("tone", "themes", "counts", "ner", "locations", "gcam"),
):
    """Build local profiles; never copy an existing external dictionary.

    The recorded tone/theme revisions require their original source versions.
    Use the standalone source importers for different dictionaries or editions.
    """
    output = Path(output)
    required = {}
    if "tone" in fields or "gcam" in fields:
        required["General Inquirer TSV (--tone-source)"] = tone_source
    if ("themes" in fields or "gcam" in fields) and not authored_themes_only:
        required["CrisisLexRec text (--crisislex-source)"] = crisislex_source
    if "gcam" in fields:
        required.update(
            {
                "VADER vocabulary (--vader-source)": vader_source,
                "GCAM codebook TSV (--codebook-source)": codebook_source,
                "WordNet 3.1 (--wordnet-31)": wordnet_31,
                "WordNet 2.0 (--wordnet-20)": wordnet_20,
                "WordNet 1.6 (--wordnet-16)": wordnet_16,
                "Domains/Affect annotations (--wordnet-annotations)": wordnet_annotations,
            }
        )
    if "locations" in fields:
        required["GKG reference archives (--gazetteer-archives)"] = gazetteer_archives
    if missing := [name for name, value in required.items() if not value]:
        raise ValueError("Required source inputs: " + ", ".join(missing))
    dictionaries = {}
    if "tone" in fields:
        dictionaries["tone.v1.json"] = build_lexicon(Path(tone_source))
        dictionaries["tone.v2.json"] = revise_tone(
            dictionaries["tone.v1.json"], read_resource_json("tone", "v2-edits.json")
        )
        dictionaries["tone.v3.json"] = revise_tone(
            dictionaries["tone.v2.json"], read_resource_json("tone", "v3-edits.json")
        )
    if "themes" in fields:
        first = read_resource_json("themes", "themes-count-candidates-v2.json")
        if not authored_themes_only:
            first = restore_crisislex(first, crisislex_source)
        additions = read_resource_json("themes", "theme_seeds.json")
        dictionaries["themes.v1.json"] = merge_inputs([first], name="gdelt-theme-candidates-v2")
        dictionaries["themes.v2.json"] = merge_inputs(
            [first, additions], name="gdelt-theme-candidates-v3"
        )
        for name in ("themes.v1.json", "themes.v2.json"):
            dictionaries[name]["$schema"] = "../schemas/theme-rules.schema.json"
            theme_lexicon_from_input(dictionaries[name])
        if authored_themes_only:
            for name in ("themes.v1.json", "themes.v2.json"):
                dictionaries.pop(name)
            dictionaries["themes.authored.json"] = authored_theme_input()
        else:
            dictionaries["themes.v3.json"] = revise_themes(
                dictionaries["themes.v2.json"], read_resource_json("themes", "revision.v3.json")
            )
    if "counts" in fields:
        dictionaries["counts.v1.json"] = read_resource_json("counts", "rules.v1.json")
        count_rules_from_input(dictionaries["counts.v1.json"])
        dictionaries["counts.v2.json"] = read_resource_json("counts", "rules.v2.json")
        count_rules_from_input(dictionaries["counts.v2.json"])
        dictionaries["counts.v3.json"] = read_resource_json("counts", "rules.v3.json")
        count_rules_from_input(dictionaries["counts.v3.json"])
    if "ner" in fields:
        from gdelt_regkg.ner import NameRules

        source = packaged_resource_path("ner", "names.v1.json")
        NameRules.from_json(source)
        dictionaries["names.v1.json"] = read_resource_json("ner", "names.v1.json")
    if "gcam" in fields:
        from .build_gcam_expansion import (
            add_general_inquirer,
            add_themes,
            add_wordnet_affect,
            add_wordnet_domains,
            add_wordnet_lexical,
            read_codebook,
        )
        from .build_gcam_lexicon import build_gcam_lexicon, extend_gcam_lexicon

        book = read_codebook(codebook_source)
        dictionaries["gcam.v1.json"] = build_gcam_lexicon(tone_source)
        dictionaries["gcam.v2.json"] = extend_gcam_lexicon(
            dictionaries["gcam.v1.json"], vader_source=vader_source
        )
        expanded = add_general_inquirer(dictionaries["gcam.v2.json"], tone_source, book)
        expanded = add_wordnet_lexical(expanded, wordnet_31, book)
        expanded = add_wordnet_affect(expanded, wordnet_annotations, wordnet_16, book)
        expanded = add_wordnet_domains(expanded, wordnet_annotations, wordnet_20, book)
        theme_data = dictionaries.get("themes.v3.json") or dictionaries.get("themes.authored.json")
        if theme_data is None:
            if authored_themes_only:
                theme_data = authored_theme_input()
            else:
                first = restore_crisislex(
                    read_resource_json("themes", "themes-count-candidates-v2.json"),
                    crisislex_source,
                )
                baseline = merge_inputs(
                    [first, read_resource_json("themes", "theme_seeds.json")],
                    name="gdelt-theme-candidates-v3",
                )
                baseline["$schema"] = "../schemas/theme-rules.schema.json"
                theme_data = revise_themes(
                    baseline, read_resource_json("themes", "revision.v3.json")
                )
        expanded = add_themes(expanded, book, theme_lexicon_from_input(theme_data))
        expanded["name"] = "general-inquirer-wordnet-themes-vader-gcam-v3"
        expanded["wordnet_parsing"] = (
            "Strip documented adjective syntactic flags (a), (p), (ip) before normalizing lemmas"
        )
        annotation_url = read_resource_json("recipes.json")["sources"]["wordnet-annotations"]["url"]
        for key in ("wordnet-affect-1.1", "wordnet-domains-3.2"):
            expanded["sources"][key]["retrieval_url"] = annotation_url
        dictionaries["gcam.v3.json.gz"] = expanded
    if "locations" in fields:
        from .build_gazetteer import build_gazetteer

        dictionaries["locations.v1.json.gz"] = build_gazetteer(gazetteer_archives)
    schemas = output / "schemas"
    lexicons = output / "lexicons"
    schemas.mkdir(parents=True, exist_ok=True)
    lexicons.mkdir(parents=True, exist_ok=True)
    for source in packaged_resource_path("schemas").iterdir():
        if source.name.endswith(".schema.json"):
            (schemas / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    for name, payload in dictionaries.items():
        raw = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        (lexicons / name).write_bytes(gzip.compress(raw, mtime=0) if name.endswith(".gz") else raw)
    if "gcam" in fields:
        codebook = output / "gcam"
        codebook.mkdir(exist_ok=True)
        (codebook / "codebook.v1.json").write_text(
            json.dumps(book, indent=2) + "\n", encoding="utf-8"
        )
    defaults = json.loads(packaged_resource_path("defaults.json").read_text(encoding="utf-8"))
    selected = {field: defaults[field] for field in fields}
    if authored_themes_only and "themes" in selected:
        selected["themes"] = "themes.authored.json"
    (output / "defaults.json").write_text(json.dumps(selected, indent=2) + "\n", encoding="utf-8")
    return dictionaries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory for lexicons, schemas and defaults.json",
    )
    parser.add_argument(
        "--fields",
        choices=("tone", "themes", "counts", "ner", "locations", "gcam"),
        nargs="+",
        default=["tone", "themes", "counts", "ner", "locations", "gcam"],
    )
    parser.add_argument("--tone-source", type=Path, help="General Inquirer basic TSV")
    parser.add_argument("--vader-source", type=Path, help="VADER vocabulary to rebuild GCAM v2")
    parser.add_argument("--crisislex-source", type=Path)
    parser.add_argument("--codebook-source", type=Path)
    parser.add_argument("--wordnet-31", type=Path)
    parser.add_argument("--wordnet-20", type=Path)
    parser.add_argument("--wordnet-16", type=Path)
    parser.add_argument("--wordnet-annotations", type=Path)
    parser.add_argument("--gazetteer-archives", nargs="+", type=Path)
    parser.add_argument(
        "--sources-dir",
        type=Path,
        help="Directory containing the recipe's source filenames and GKG archives",
    )
    parser.add_argument(
        "--download-sources",
        action="store_true",
        help="Explicitly fetch required published sources into --sources-dir; review their terms first",
    )
    parser.add_argument(
        "--authored-themes-only",
        action="store_true",
        help="Build independent custom theme rules without CrisisLex; agreement metrics for the full profile do not apply",
    )
    parser.add_argument(
        "--download-tone-source",
        action="store_true",
        help="Explicitly download the published General Inquirer TSV",
    )
    args = parser.parse_args()
    recipe = read_resource_json("recipes.json")
    if args.download_sources and args.sources_dir is None:
        parser.error("--download-sources requires --sources-dir")
    try:
        prepare_inputs(args, recipe, parser)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        parser.error(str(exc))
    try:
        dictionaries = build_resources(
            args.output,
            fields=args.fields,
            tone_source=args.tone_source,
            vader_source=args.vader_source,
            crisislex_source=args.crisislex_source,
            codebook_source=args.codebook_source,
            wordnet_31=args.wordnet_31,
            wordnet_20=args.wordnet_20,
            wordnet_16=args.wordnet_16,
            wordnet_annotations=args.wordnet_annotations,
            gazetteer_archives=args.gazetteer_archives,
            authored_themes_only=args.authored_themes_only,
        )
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))
    print("Built " + ", ".join(dictionaries))


def prepare_inputs(args, recipe, parser):
    """Resolve explicitly supplied or requested source inputs before building."""
    sources = {}
    if "tone" in args.fields or "gcam" in args.fields:
        sources["general-inquirer"] = "tone_source"
    if ("themes" in args.fields or "gcam" in args.fields) and not args.authored_themes_only:
        sources["crisislex"] = "crisislex_source"
    if "gcam" in args.fields:
        sources.update(
            {
                "vader": "vader_source",
                "codebook": "codebook_source",
                "wordnet-31": "wordnet_31",
                "wordnet-20": "wordnet_20",
                "wordnet-16": "wordnet_16",
                "wordnet-annotations": "wordnet_annotations",
            }
        )
    for source, argument in sources.items():
        if getattr(args, argument) is None and args.sources_dir:
            entry = recipe["sources"][source]
            path = args.sources_dir / entry["filename"]
            if args.download_sources:
                download_source(path, entry)
            if path.is_file():
                verify_source(path, entry)
                setattr(args, argument, path)
    if "locations" in args.fields and args.gazetteer_archives is None and args.sources_dir:
        args.gazetteer_archives = []
        for entry in recipe["gazetteer_sources"]:
            path = args.sources_dir / entry["url"].rsplit("/", 1)[-1]
            if args.download_sources:
                download_source(path, entry)
            verify_source(path, entry)
            args.gazetteer_archives.append(path)
    if args.tone_source and args.download_tone_source:
        parser.error("Choose a supplied source or an explicit download")
    if args.download_tone_source:
        source = args.output / "sources" / "inqtabs.txt"
        source.parent.mkdir(parents=True, exist_ok=True)
        with urlopen("https://inquirer.sites.fas.harvard.edu/inqtabs.txt", timeout=60) as response:
            source.write_bytes(response.read())
        args.tone_source = source
    if "tone" in args.fields and args.tone_source is None:
        parser.error("Supply --tone-source or --download-tone-source to rebuild tone")


def verify_source(path, entry):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError(
            f"Source checksum mismatch: {path}. Use the recorded edition; extraction metrics apply to those inputs."
        )


def download_source(path, entry):
    """Only an explicit setup command downloads; reject changed upstream bytes."""
    path = Path(path)
    if path.is_file():
        verify_source(path, entry)
        return
    with urlopen(
        Request(entry["url"], headers={"User-Agent": "gdelt-regkg resource setup"}), timeout=60
    ) as response:
        raw = response.read()
    if "archive_member" in entry:
        if hashlib.sha256(raw).hexdigest() != entry["archive_sha256"]:
            raise ValueError(f"Downloaded archive checksum mismatch: {entry['url']}")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            raw = archive.read(entry["archive_member"])
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError(
            f"Downloaded source checksum mismatch: {entry['url']}; no file was installed"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


if __name__ == "__main__":
    main()
