"""Build an offline reference gazetteer from supplied GKG 2.1 ZIP archives.

Only geographic reference cells are read. Do not use held-out benchmark archives.
Names, FIPS codes, GNIS/GNS IDs and GAUL ADM2 values retain their source metadata.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path

from gdelt_regkg.locations import Gazetteer, Place


def build_gazetteer(archives, *, name="gkg-reference-gazetteer-v1"):
    observed = Counter[tuple[str, ...]]()
    sources = []
    for path in sorted(map(Path, archives)):
        raw = path.read_bytes()
        sources.append(
            {
                "url": "http://data.gdeltproject.org/gdeltv2/" + path.name,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if not member.endswith(".csv"):
                    continue
                with archive.open(member) as stream:
                    for line in stream:
                        cells = line.decode("utf-8", errors="replace").rstrip("\r\n").split("\t")
                        if len(cells) != 27:
                            continue
                        for item in cells[10].split(";"):
                            parts = item.split("#")
                            if len(parts) != 9:
                                continue
                            geo_type, full_name, country, adm1, adm2, lat, lon, feature, _ = parts
                            try:
                                place = Place(
                                    geo_type, full_name, country, adm1, lat, lon, feature, adm2
                                )
                            except (TypeError, ValueError):
                                continue
                            observed[tuple(place.components()) + (adm2,)] += 1
    # The same feature/name can have formatting or coordinate revisions. Retain
    # the most frequent complete tuple, with a deterministic lexical tie break.
    grouped = defaultdict(list)
    for values, frequency in observed.items():
        grouped[(values[0], values[1], values[2], values[3], values[6])].append((frequency, values))
    places = []
    for candidates in grouped.values():
        candidates.sort(key=lambda item: (-item[0], item[1]))
        frequency, values = candidates[0]
        geo_type, full_name, country, adm1, lat, lon, feature, adm2 = values
        aliases = [] if geo_type == "1" else [full_name.split(",", 1)[0]]
        if geo_type == "1":
            aliases += {
                "US": ["United States", "United States of America", "US", "U.S.", "USA", "U.S.A."],
                "UK": ["United Kingdom", "UK", "U.K.", "Britain", "Great Britain"],
            }.get(country, [])
        places.append(
            Place(
                geo_type,
                full_name,
                country,
                adm1,
                lat,
                lon,
                feature,
                adm2,
                tuple(sorted(set(aliases))),
                sum(f for f, _ in candidates),
            )
        )
    places.sort(key=lambda p: (p.identity, p.full_name))
    Gazetteer(name, tuple(places))
    return {"name": name, "sources": sources, "places": [asdict(p) for p in places]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", default="gkg-reference-gazetteer-v1")
    args = parser.parse_args()
    result = build_gazetteer(args.archives, name=args.name)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    args.output.write_bytes(gzip.compress(raw, mtime=0) if args.output.suffix == ".gz" else raw)


if __name__ == "__main__":
    main()
