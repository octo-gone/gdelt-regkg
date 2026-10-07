"""Offline resolution of NER place spans using GKG-compatible gazetteer records."""

from __future__ import annotations

import gzip
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from .counts import CountLocation
from .ner import EntityRecognizer, NERResult, analyze_entities
from .utils import read_resource_json, resource_path
from .wire import text_component


def location_key(name):
    name = unicodedata.normalize("NFKC", name).casefold()
    return " ".join(re.sub(r"[.,]", " ", name).split())


@dataclass(frozen=True)
class Place:
    geo_type: str
    full_name: str
    country_code: str
    adm1_code: str
    latitude: str
    longitude: str
    feature_id: str
    adm2_code: str = ""
    aliases: tuple[str, ...] = ()
    frequency: int = 1

    def __post_init__(self):
        CountLocation(0, 1, *self.components())
        if self.geo_type not in {"1", "2", "3", "4", "5"}:
            raise ValueError("Resolved places require location types 1 through 5")
        if not re.fullmatch(r"[A-Z]{2}", self.country_code) or not self.full_name.strip():
            raise ValueError("Places require a name and two-letter FIPS country code")
        if not self.latitude or not self.longitude or not self.feature_id:
            raise ValueError("Places require coordinates and a native feature identifier")
        if any(c in self.adm2_code for c in "#;\t\r\n"):
            raise ValueError("Invalid ADM2 code")
        if type(self.frequency) is not int or self.frequency < 1:
            raise ValueError("frequency must be a positive integer")
        if isinstance(self.aliases, str) or any(
            not isinstance(a, str) or not a.strip() for a in self.aliases
        ):
            raise ValueError("aliases must contain nonempty names")
        object.__setattr__(self, "aliases", tuple(self.aliases))

    def components(self):
        return (
            self.geo_type,
            self.full_name,
            self.country_code,
            self.adm1_code,
            self.latitude,
            self.longitude,
            self.feature_id,
        )

    @property
    def identity(self):
        return self.geo_type, self.country_code, self.adm1_code, self.feature_id


@dataclass(frozen=True)
class Gazetteer:
    name: str
    places: tuple[Place, ...]
    _index: dict = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Gazetteer requires a profile name")
        index = defaultdict(list)
        for place in self.places:
            if not isinstance(place, Place):
                raise TypeError("places must contain Place records")
            for alias in {place.full_name, *place.aliases}:
                index[location_key(alias)].append(place)
        object.__setattr__(self, "places", tuple(self.places))
        object.__setattr__(
            self, "_index", MappingProxyType({key: tuple(values) for key, values in index.items()})
        )

    @classmethod
    def from_json(cls, path):
        path = Path(path)
        raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
        return _load(json.loads(raw.decode("utf-8")))

    def candidates(self, name):
        return self._index.get(location_key(name), ())


def _load(payload):
    return Gazetteer(payload["name"], tuple(Place(**p) for p in payload["places"]))


def default_gazetteer(resources_dir=None):
    return _cached_gazetteer(
        resource_path(
            "lexicons",
            read_resource_json("defaults.json", resources_dir=resources_dir)["locations"],
            resources_dir=resources_dir,
        )
    )


@lru_cache(maxsize=8)
def _cached_gazetteer(path):
    return Gazetteer.from_json(path)


@dataclass(frozen=True)
class LocationMention:
    text: str
    start: int
    end: int
    place: Place

    def __post_init__(self):
        if not isinstance(self.place, Place):
            raise TypeError("place must be Place")
        self.as_count_location()
        if len(self.text) != self.end - self.start:
            raise ValueError("Location text must match its span length")

    def as_count_location(self):
        return CountLocation(self.start, self.end, *self.place.components())

    def to_gkg(self, *, enhanced=False):
        components = list(self.place.components())
        # Preserve the observed spelling, as native GKG does, with the same hierarchy.
        hierarchy = self.place.full_name.partition(",")[2] if self.place.geo_type != "1" else ""
        components[1] = text_component(self.text, separators="#;") + (
            "," + hierarchy if hierarchy and "," not in self.text else ""
        )
        if enhanced:
            components.insert(4, self.place.adm2_code)
            components.append(str(self.start))
        return "#".join(components)


@dataclass(frozen=True)
class LocationIssue:
    text: str
    start: int
    reason: str


@dataclass(frozen=True)
class LocationResult:
    text: str
    mentions: tuple[LocationMention, ...]
    issues: tuple[LocationIssue, ...]
    gazetteer_name: str

    def to_gkg(self, *, enhanced=False):
        entries = [m.to_gkg(enhanced=enhanced) for m in self.mentions]
        return ";".join(entries if enhanced else dict.fromkeys(entries))

    @property
    def count_locations(self):
        return tuple(m.as_count_location() for m in self.mentions)


def analyze_locations(
    text: str,
    *,
    recognizer: EntityRecognizer | None = None,
    ner: NERResult | None = None,
    gazetteer: Gazetteer | None = None,
) -> LocationResult:
    """Resolve one unchanged body. Unknown and ambiguous names remain diagnostics.

    Explicit nearby country/ADM1 references take precedence over the reference
    frequency prior. Without context, a candidate needs >=80% of alias frequency.
    Multiple aliases of one feature do not inflate that prior.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if recognizer is not None and ner is not None:
        raise ValueError("Supply recognizer or ner, not both")
    ner = analyze_entities(text, recognizer=recognizer) if ner is None else ner
    if not isinstance(ner, NERResult) or ner.text != text:
        raise ValueError("NER result must refer to the unchanged body")
    gazetteer = default_gazetteer() if gazetteer is None else gazetteer
    if not isinstance(gazetteer, Gazetteer):
        raise TypeError("gazetteer must be Gazetteer")
    inputs = []
    for mention in ner.locations:
        candidates = gazetteer.candidates(mention.text)
        if candidates:
            inputs.append((mention.text, mention.start, mention.end, candidates))
            continue
        # A backend can emit 'Paris, France' as one span. Resolve each component.
        parts = list(re.finditer(r"[^,]+", mention.text))
        if len(parts) > 1:
            for part in parts:
                value = part[0].strip()
                start = mention.start + part.start() + len(part[0]) - len(part[0].lstrip())
                inputs.append((value, start, start + len(value), gazetteer.candidates(value)))
        else:
            inputs.append((mention.text, mention.start, mention.end, ()))
    anchors = []
    for _, start, _, candidates in inputs:
        identities = {p.identity for p in candidates}
        if len(identities) == 1 and candidates[0].geo_type in {"1", "2", "5"}:
            anchors.append((start, candidates[0]))
    mentions, issues = [], []
    for value, start, end, raw in inputs:
        by_id: dict[tuple[str, str, str, str], Place] = {}
        for p in raw:
            if p.identity not in by_id or p.frequency > by_id[p.identity].frequency:
                by_id[p.identity] = p
        candidates = list(by_id.values())
        if len(candidates) > 1:
            # Use the closest applicable explicit anchor within 200 characters.
            # sorted consumes this key immediately within the current iteration.
            for position, anchor in sorted(anchors, key=lambda a: abs(a[0] - start)):  # pylint: disable=cell-var-from-loop
                if abs(position - start) > 200:
                    continue
                matching = [
                    p
                    for p in candidates
                    if p.country_code == anchor.country_code
                    and (anchor.geo_type == "1" or p.adm1_code == anchor.adm1_code)
                ]
                if matching:
                    candidates = matching
                    break
        if len(candidates) > 1:
            candidates.sort(key=lambda p: (-p.frequency, p.identity))
            if candidates[0].frequency / sum(p.frequency for p in candidates) >= 0.8:
                candidates = candidates[:1]
        if len(candidates) == 1:
            mentions.append(LocationMention(value, start, end, candidates[0]))
        else:
            issues.append(
                LocationIssue(
                    value, start, "unknown-place" if not candidates else "ambiguous-place"
                )
            )
    return LocationResult(
        text, tuple(sorted(mentions, key=lambda m: m.start)), tuple(issues), gazetteer.name
    )
