"""Import CrisisLexRec text and/or EMTerms CSV/ZIP into a local theme profile.

No download is performed. Templates and unmapped EMTerms categories are
excluded and reported in the output metadata. Review resources' usage terms.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import zipfile
from importlib.resources import files
from pathlib import Path

from gdelt_regkg.config import ExtractionConfig
from gdelt_regkg.rule_inputs import theme_input_from_mapping
from gdelt_regkg.themes import ThemeLexicon

EMTERMS_THEMES = dict(
    zip(
        "C01 C02 C03 C04 C05 C06 C07 C08 O01 O02 T01 T02 T03 T04 T05 T06 T07 T08 T09 T11".split(),
        (
            "CHILDREN_AND_EDUCATION NEEDSPROVIDE_FOOD WELLBEING_HEALTH LOGISTICS_TRANSPORT "
            "NEED_OF_SHELTERS WATER_SANITATION SAFETY TELECOM WEATHER RESPONSEAGENCIESATCRISIS "
            "CAUTION_ADVICE INJURED DEAD INFRASTRUCTURE MONEY SUPPLIES SERVICESNEEDEDOFFERED "
            "MISSINGFOUNDTRAPPEDPEOPLE DISPLACEDRELOCATEDEVACUATED UPDATESSYMPATHY"
        ).split(),
        strict=True,
    )
)


def build_profile(*, crisislex: Path | None = None, emterms: Path | None = None, name: str):
    themes: dict[str, set[str]] = {}
    sources = []
    skipped = {"template": 0, "unmapped_category": 0, "empty": 0}
    for path, kind in ((crisislex, "CrisisLexRec"), (emterms, "EMTerms")):
        if path is None:
            continue
        raw = path.read_bytes()
        sources.append(
            {
                "resource": kind,
                "url": (
                    "https://raw.githubusercontent.com/sajao/CrisisLex/master/data/CrisisLexLexicon/CrisisLexRec.txt"
                    if kind == "CrisisLexRec"
                    else "https://crisislex.org/emterms/EMTerms-v1.0.zip"
                ),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        if kind == "CrisisLexRec":
            rows = (
                (line.strip(), "CRISISLEX_CRISISLEXREC")
                for line in raw.decode("utf-8-sig").splitlines()
            )
        else:
            if zipfile.is_zipfile(io.BytesIO(raw)):
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    raw = archive.read("EMTerms-1.0.csv")
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            if not {"Term", "Category Code"} <= set(reader.fieldnames or []):
                raise ValueError("Expected an EMTerms CSV with Term and Category Code columns")
            rows = ((r["Term"].strip(), r["Category Code"].strip()) for r in reader)
        for phrase, code in rows:
            if not phrase:
                skipped["empty"] += 1
                continue
            if kind == "EMTerms":
                if code not in EMTERMS_THEMES:
                    skipped["unmapped_category"] += 1
                    continue
                code = f"CRISISLEX_{code}_{EMTERMS_THEMES[code]}"
            if "{" in phrase or "}" in phrase:
                skipped["template"] += 1
                continue
            themes.setdefault(code, set()).add(" ".join(phrase.split()))
    if not themes:
        raise ValueError("No supported literal phrases found")
    sorted_themes = {code: sorted(phrases) for code, phrases in sorted(themes.items())}
    ThemeLexicon.from_mapping(sorted_themes, name=name)
    return {"name": name, "sources": sources, "skipped_rows": skipped, "themes": sorted_themes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--crisislex", type=Path)
    parser.add_argument("--emterms", type=Path)
    parser.add_argument("--name", default="crisislex-literal-v1")
    parser.add_argument(
        "--base-config",
        type=Path,
        help="Replace the theme section of this shared config, preserving count rules",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--rule-input",
        action="store_true",
        help="Write source-neutral theme rules instead of a source-shaped profile",
    )
    args = parser.parse_args()
    if args.rule_input and args.base_config:
        parser.error("--rule-input is for standalone theme inputs; omit --base-config")
    payload = build_profile(crisislex=args.crisislex, emterms=args.emterms, name=args.name)
    output = (
        theme_input_from_mapping(
            payload["themes"], name=payload["name"], sources=payload["sources"]
        )
        if args.rule_input
        else payload
    )
    if args.base_config:
        output = json.loads(args.base_config.read_text(encoding="utf-8"))
        output["theme_lexicon"] = payload
        ExtractionConfig.from_dict(output)
    if args.rule_input:
        schema_path = Path(
            str(files("gdelt_regkg").joinpath("resources/schemas/theme-rules.schema.json"))
        )
        output["$schema"] = os.path.relpath(schema_path, args.output.resolve().parent).replace(
            os.sep, "/"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{len(payload['themes'])} themes; {sum(map(len, payload['themes'].values()))} phrase/category pairs"
    )
    print(f"Excluded rows: {payload['skipped_rows']}")


if __name__ == "__main__":
    main()
