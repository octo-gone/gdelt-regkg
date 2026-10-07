"""Configurable English count patterns, independent of themes and CAMEO.

Rules and offset conventions are local approximations. Geography is optional
caller-supplied resolved data.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from .wire import text_component

PROFILE = "english-counts-v1"
_UNITS = "one two three four five six seven eight nine".split()
_SMALL = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
_VALUES = {word: i for i, word in enumerate(_SMALL)} | {
    word: (i + 2) * 10 for i, word in enumerate(_TENS)
}
_U = "(?:" + "|".join(_UNITS) + ")"
_N100 = "(?:" + "(?:" + "|".join(_TENS) + rf")(?:[ -]{_U})?|(?:" + "|".join(_SMALL) + "))"
_N1000 = rf"(?:{_U} hundred(?: (?:and )?{_N100})?|{_N100})"
_WORDS = rf"(?:{_N1000} million(?: {_N1000} thousand)?(?: (?:and )?{_N1000})?|{_N1000} thousand(?: (?:and )?{_N1000})?|{_N1000})"
_NUMBER = rf"(?:[0-9]{{1,3}}(?:,[0-9]{{3}})+(?: (?:thousand|million))?|[0-9]+(?: (?:thousand|million))?|{_WORDS})"
_NUMBER_RE = re.compile(rf"(?<!\w){_NUMBER}(?!\w)", re.I)


def _normalize_phrase(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z]+(?:[' -][a-zA-Z]+)*", value):
        raise ValueError("Count rule phrases must contain English words, not regex or delimiters")
    return value.lower()


def _alternation(phrases) -> str:
    # Escape user data. Longest first prevents a shorter prefix winning.
    parts = [
        r"\s+".join(re.escape(word) for word in phrase.split())
        for phrase in sorted(phrases, key=lambda p: (-len(p), p))
    ]
    return "(?:" + "|".join(parts) + ")" if parts else r"(?!)"


@dataclass(frozen=True)
class CountRules:
    """Literal vocabulary and bounds for the existing count grammar."""

    name: str
    triggers: Mapping[str, str | tuple[str, ...]]
    active_triggers: tuple[str, ...]
    object_nouns: tuple[str, ...]
    auxiliaries: tuple[str, ...]
    unsafe_phrases: tuple[str, ...]
    unsafe_suffixes: tuple[str, ...]
    bad_object_words: tuple[str, ...]
    max_object_modifiers: int = 3
    context_words: int = 10
    patterns: tuple[dict, ...] = ()
    allow_bare_active: bool = False
    reject_time_objects: bool = False
    empty_object_nouns: tuple[str, ...] = ()
    _patterns: tuple = field(init=False, repr=False, compare=False)
    _noun: str = field(init=False, repr=False, compare=False)
    _passive: re.Pattern = field(init=False, repr=False, compare=False)
    _active: re.Pattern = field(init=False, repr=False, compare=False)
    _trigger_re: re.Pattern = field(init=False, repr=False, compare=False)
    _unsafe: re.Pattern = field(init=False, repr=False, compare=False)
    _bad_object: re.Pattern = field(init=False, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data: dict):
        if not isinstance(data, dict):
            raise ValueError("count_rules must be an object")
        return cls(**data)

    @classmethod
    def from_json(cls, path: str | Path):
        """Load source-neutral rule input or the legacy count-rules object."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if "schema" in data:
            from .rule_inputs import count_rules_from_input

            return count_rules_from_input(data)
        return cls.from_dict(data)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Count rules require a nonempty profile name")
        if not isinstance(self.triggers, Mapping):
            raise TypeError("triggers must map phrases to count codes")
        triggers: dict[str, tuple[str, ...]] = {}
        for phrase, codes in self.triggers.items():
            phrase = _normalize_phrase(phrase)
            codes = (codes,) if isinstance(codes, str) else tuple(codes)
            if not codes or any(
                not isinstance(code, str) or not re.fullmatch(r"[A-Z][A-Z0-9_-]*", code)
                for code in codes
            ):
                raise ValueError(
                    "Count codes must contain uppercase letters, digits, underscores or hyphens"
                )
            codes = tuple(dict.fromkeys(codes))
            if phrase in triggers and triggers[phrase] != codes:
                raise ValueError(f"Conflicting categories for trigger {phrase}")
            triggers[phrase] = codes
        object.__setattr__(self, "triggers", MappingProxyType(triggers))
        for key in (
            "active_triggers",
            "object_nouns",
            "auxiliaries",
            "unsafe_phrases",
            "unsafe_suffixes",
            "bad_object_words",
            "empty_object_nouns",
        ):
            values = getattr(self, key)
            if isinstance(values, str):
                raise TypeError(f"{key} must be a collection of phrases, not a string")
            object.__setattr__(
                self, key, tuple(dict.fromkeys(_normalize_phrase(v) for v in values))
            )
        if set(self.active_triggers) - triggers.keys():
            raise ValueError("Every active trigger must also appear in triggers")
        for key, minimum, maximum in (("max_object_modifiers", 0, 20), ("context_words", 1, 100)):
            value = getattr(self, key)
            if type(value) is not int or not minimum <= value <= maximum:
                raise ValueError(f"{key} must be an integer from {minimum} to {maximum}")
        if not isinstance(self.allow_bare_active, bool):
            raise TypeError("allow_bare_active must be boolean")
        if not isinstance(self.reject_time_objects, bool):
            raise TypeError("reject_time_objects must be boolean")
        noun = _alternation(self.object_nouns)
        obj = rf"(?:[^\W\d_]+\s+){{0,{self.max_object_modifiers}}}{noun}"
        event = _alternation(triggers)
        passive = re.compile(
            rf"(?<!\w)(?P<number>{_NUMBER})(?!\w)\s+"
            rf"(?:(?P<object>{obj})\s+)?"
            rf"(?:(?P<aux>{_alternation(self.auxiliaries)})\s+)?"
            rf"(?P<trigger>{event})(?!\w)",
            re.I,
        )
        active_object = rf"(?:\s+(?P<object>{obj})(?!\w))" + ("?" if self.allow_bare_active else "")
        active = re.compile(
            rf"\b(?P<trigger>{_alternation(self.active_triggers)})\s+"
            rf"(?P<number>{_NUMBER})(?!\w){active_object}",
            re.I,
        )
        object.__setattr__(self, "_noun", noun)
        object.__setattr__(self, "_passive", passive)
        object.__setattr__(self, "_active", active)
        object.__setattr__(self, "_trigger_re", re.compile(rf"\b{event}\b", re.I))
        object.__setattr__(
            self,
            "_unsafe",
            re.compile(
                rf"\b{_alternation(self.unsafe_phrases)}\b|{_alternation(self.unsafe_suffixes)}\b",
                re.I,
            ),
        )
        object.__setattr__(
            self, "_bad_object", re.compile(rf"\b{_alternation(self.bad_object_words)}\b", re.I)
        )
        compiled = []
        stored = []
        ids = set()
        for pattern in self.patterns:
            if set(pattern) != {"id", "template", "labels"}:
                raise ValueError("Count patterns require id, template, labels")
            identifier, template = pattern["id"], pattern["template"]
            if not isinstance(identifier, str) or not identifier or identifier in ids:
                raise ValueError("Pattern IDs must be nonempty and unique")
            ids.add(identifier)
            if not isinstance(template, str) or template.count("{number}") != 1:
                raise ValueError("Count templates require exactly one {number}")
            if any(c in template for c in "#;\t\r\n"):
                raise ValueError("Invalid template delimiter")
            before, after = template.split("{number}")
            # Only literal context plus one explicit numeric capture; no arbitrary regex.
            for context in (before.strip(), after.strip()):
                if context:
                    _normalize_phrase(context)
            if not before.strip() and not after.strip():
                raise ValueError("A bare number is not a count template")
            labels = pattern["labels"]
            if (
                isinstance(labels, str)
                or not labels
                or any(
                    not isinstance(c, str) or not re.fullmatch(r"[A-Z][A-Z0-9_-]*", c)
                    for c in labels
                )
            ):
                raise ValueError("Pattern labels must be a nonempty list of valid codes")
            labels = tuple(dict.fromkeys(labels))

            def literal(s):
                return r"\s+".join(re.escape(word) for word in s.strip().split())

            left = literal(before) + (r"\s+" if before else "")
            right = (r"\s+" if after else "") + literal(after)
            regex = re.compile(rf"(?<!\w){left}(?P<number>{_NUMBER})(?!\w){right}(?!\w)", re.I)
            compiled.append((identifier, regex, labels))
            stored.append(
                MappingProxyType({"id": identifier, "template": template, "labels": labels})
            )
        object.__setattr__(self, "patterns", tuple(stored))
        object.__setattr__(self, "_patterns", tuple(compiled))


def default_count_rules(resources_dir=None) -> CountRules:
    from .utils import read_resource_json, resource_path

    return _cached_count_rules(
        resource_path(
            "lexicons",
            read_resource_json("defaults.json", resources_dir=resources_dir)["counts"],
            resources_dir=resources_dir,
        )
    )


@lru_cache(maxsize=8)
def _cached_count_rules(path):
    from .rule_inputs import count_rules_from_input

    return count_rules_from_input(json.loads(path.read_text(encoding="utf-8")))


def _integer(expression: str) -> int:
    parts = expression.lower().replace(",", "").replace("-", " ").split()
    total = current = 0
    for part in parts:
        if part == "and":
            continue
        if part == "hundred":
            current *= 100
        elif part in {"thousand", "million"}:
            total += current * (1_000 if part == "thousand" else 1_000_000)
            current = 0
        else:
            current += int(part) if part.isascii() and part.isdigit() else _VALUES[part]
    return total + current


def _wire(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("Count subfields must be strings")
    if any(c in value for c in "#;\t\r\n"):
        raise ValueError("Count subfields cannot contain #, ;, tabs or newlines")


def _span(start: int, end: int) -> None:
    if type(start) is not int or type(end) is not int or start < 0 or end <= start:
        raise ValueError("Expected a nonempty span with nonnegative integer offsets")


@dataclass(frozen=True)
class CountLocation:
    """Resolved geographic mention, in the original text's character coordinates.

    Caller owns geocoding and compatible FIPS/GNS/GNIS identifiers. There is no
    ADM2 component in the count layout. Empty components remain empty on export.
    """

    start: int
    end: int
    geo_type: str = ""
    full_name: str = ""
    country_code: str = ""
    adm1_code: str = ""
    latitude: str = ""
    longitude: str = ""
    feature_id: str = ""

    def __post_init__(self):
        _span(self.start, self.end)
        for value in self.components():
            _wire(value)
        if self.geo_type not in {"", "0", "1", "2", "3", "4", "5"}:
            raise ValueError("geo_type must be empty or a string from 0 through 5")
        for value, limit in ((self.latitude, 90), (self.longitude, 180)):
            if value and (not math.isfinite(float(value)) or not -limit <= float(value) <= limit):
                raise ValueError("Invalid geographic coordinate")

    def components(self) -> tuple[str, ...]:
        return (
            self.geo_type,
            text_component(self.full_name, separators="#;"),
            self.country_code,
            self.adm1_code,
            self.latitude,
            self.longitude,
            self.feature_id,
        )


@dataclass(frozen=True)
class CountMention:
    count_type: str
    number: int
    object_type: str
    start: int
    end: int
    trigger_start: int
    location: CountLocation | None = None

    def __post_init__(self):
        _span(self.start, self.end)
        if type(self.number) is not int or self.number < 0:
            raise ValueError("number must be a nonnegative integer")
        if not isinstance(self.count_type, str) or not re.fullmatch(
            r"[A-Z][A-Z0-9_-]*", self.count_type
        ):
            raise ValueError("Invalid count type")
        _wire(text_component(self.object_type, separators="#;"))
        if type(self.trigger_start) is not int or self.trigger_start < 0:
            raise ValueError("trigger_start must be a nonnegative integer")
        if self.location is not None and not isinstance(self.location, CountLocation):
            raise TypeError("location must be CountLocation or None")

    def to_gkg(self, *, enhanced: bool = False) -> str:
        components = [
            self.count_type,
            str(self.number),
            text_component(self.object_type, separators="#;"),
        ]
        components.extend(self.location.components() if self.location else ("0",) + ("",) * 6)
        if enhanced:
            components.append(str(self.start))
        for value in components:
            _wire(value)
        return "#".join(components)


@dataclass(frozen=True)
class CountIssue:
    start: int
    end: int
    reason: str


@dataclass(frozen=True)
class CountResult:
    mentions: tuple[CountMention, ...]
    issues: tuple[CountIssue, ...]
    profile_name: str = PROFILE
    empty_object_nouns: tuple[str, ...] = field(default=(), repr=False)

    def to_gkg(self, *, enhanced: bool = False) -> str:
        return "".join(
            (
                replace(m, object_type="")
                if m.object_type.casefold() in self.empty_object_nouns
                else m
            ).to_gkg(enhanced=enhanced)
            + ";"
            for m in self.mentions
        )


def _rejection(
    text: str, match: re.Match, active: bool, rules: CountRules, *, template: bool = False
) -> str | None:
    start = match.start("number")
    # Do not match the tail of a decimal, signed number, malformed grouping,
    # range, fraction, or hyphenated age such as 25-year-old.
    if start and text[start - 1] in ".,/-+–—":
        return "unsupported_numeric_form"
    end = match.end("number")
    if end < len(text):
        suffix = text[end]
        if suffix in "/-+%–—" or (
            suffix in ".," and end + 1 < len(text) and text[end + 1].isdigit()
        ):
            return "unsupported_numeric_form"
    before = re.split(r"[.!?;\n]", text[: match.start()])[-1]
    context = " ".join(before.split()[-rules.context_words :])
    if rules._unsafe.search(context):
        return "qualified_negated_or_speculative"
    if re.search(r"\b(?:to|or)\s*$", context, re.I):
        return "range_or_alternative"
    # A preceding numeric expression can be the first half of a range or a
    # malformed number. Never salvage just the final number in that phrase.
    if re.search(r"(?:\d|hundred|thousand|million)\s*$", context, re.I):
        return "unsupported_numeric_form"
    obj = (match.group("object") or "") if not template else ""
    if (
        rules.reject_time_objects
        and not obj
        and re.match(
            r"\s+(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?|decades?|centuries)\b",
            text[match.end("number") :],
            re.I,
        )
    ):
        return "temporal_quantity"
    if rules._bad_object.search(obj):
        return "ambiguous_object"
    tail = text[match.end() :]
    if not active and not template:
        if match.group("aux") is None:
            if _NUMBER_RE.match(tail.lstrip()) or re.match(
                rf"\s+(?:a|an|the|him|her|them|{rules._noun})\b", tail, re.I
            ):
                return "possible_actor_count"
        if not obj and re.match(rf"\s+{rules._noun}\b", tail, re.I):
            return "adjectival_mention"
    if _integer(match.group("number")) == 0:
        return "zero_or_negated_count"
    return None


def _nearest_location(locations: tuple[CountLocation, ...], start: int) -> CountLocation | None:
    return min(
        locations,
        key=lambda loc: (max(loc.start - start, start - loc.end, 0), loc.start, loc.end),
        default=None,
    )


def analyze_counts(
    text: str, *, locations: Iterable[CountLocation] = (), rules: CountRules | None = None
) -> CountResult:
    """Extract exact positive quantities in a limited set of English constructions."""
    if not isinstance(text, str):
        raise TypeError("text must be str")
    rules = default_count_rules() if rules is None else rules
    if not isinstance(rules, CountRules):
        raise TypeError("rules must be CountRules")
    locations = tuple(locations)
    for supplied_location in locations:
        if not isinstance(supplied_location, CountLocation):
            raise TypeError("locations must contain CountLocation instances")
        if supplied_location.end > len(text):
            raise ValueError("Location span is outside the input text")
    mentions = {}
    rejected = {}
    for pattern, active in ((rules._passive, False), (rules._active, True)):
        for match in pattern.finditer(text):
            trigger = match.start("trigger")
            if reason := _rejection(text, match, active, rules):
                rejected[trigger] = reason
                continue
            start = match.start("number")
            location = _nearest_location(locations, start)
            for label in rules.triggers[" ".join(match.group("trigger").lower().split())]:
                mention = CountMention(
                    label,
                    _integer(match.group("number")),
                    " ".join((match.group("object") or "").split()),
                    start,
                    match.end(),
                    trigger,
                    location,
                )
                mentions[start, label, trigger] = mention
    # Templates add nominal and trigger-before-number constructions. Deduplicate
    # equivalent label/quantity spans across rules; source duplicates can be
    # preserved losslessly with the wire parser, but their extraction cause is unknown.
    for _identifier, pattern, labels in rules._patterns:
        for match in pattern.finditer(text):
            if _rejection(text, match, False, rules, template=True):
                continue
            start = match.start("number")
            location = _nearest_location(locations, start)
            for label in labels:
                if any(m.start == start and m.count_type == label for m in mentions.values()):
                    continue
                mentions[start, label, match.start()] = CountMention(
                    label,
                    _integer(match.group("number")),
                    "",
                    start,
                    max(match.end(), match.end("number")),
                    match.start(),
                    location,
                )
    accepted = {m.trigger_start for m in mentions.values()}
    issues = tuple(
        CountIssue(m.start(), m.end(), rejected.get(m.start(), "unsupported_construction"))
        for m in rules._trigger_re.finditer(text)
        if m.start() not in accepted
    )
    return CountResult(
        tuple(mentions[key] for key in sorted(mentions)),
        issues,
        rules.name,
        rules.empty_object_nouns,
    )
