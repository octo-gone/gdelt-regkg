"""Reusable entity mentions and an optional spaCy backend for prepared text."""

from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, fields
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from .utils import read_resource_json, resource_path
from .wire import text_component

_LABELS = {"PERSON", "ORG", "LOCATION"}
_SPACY_LABELS = {
    "PERSON": "PERSON",
    "ORG": "ORG",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "FAC": "LOCATION",
}
_PAGE_TEXT = re.compile(
    r"\b(?:sponsored content|all rights reserved|cookie (?:policy|settings)|privacy policy|terms of use|skip to|navigation)\b",
    re.I,
)
_NAME_POLICIES = {"surface", "gdelt", "gdelt-full-names"}
_NAME_LABELS = set(_SPACY_LABELS) | {"NORP", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE"}


@lru_cache(maxsize=16384)
def organization_features(name: str) -> frozenset[str]:
    """Binary word, bigram, and bounded character features for name filtering."""
    words = name.split()
    result = {"w:" + word for word in words}
    result.update("b:" + " ".join(words[i : i + 2]) for i in range(len(words) - 1))
    for word in words:
        marked = "^" + word + "$"
        for n in (3, 4):
            result.update("c:" + marked[i : i + n] for i in range(len(marked) - n + 1))
    result.add("length:" + str(min(len(words), 6)))
    return frozenset(result)


def canonical_entity_name(value: str) -> str:
    """Approximate native name spelling without altering source spans."""
    value = unicodedata.normalize("NFKC", value).casefold().replace("’", "'")
    value = re.sub(r"(?:'s|s')$", lambda m: "s" if m[0] == "s'" else "", value)
    value = re.sub(r"^(?:the|a|an)\s+", "", value)
    value = value.replace(".", " ").replace(",", " ")
    value = re.sub(r"[^\w\s\-']", " ", value)
    return " ".join(value.split())


@dataclass(frozen=True)
class NameRules:
    """Optional calibrated cell spellings and exclusions; source mentions stay intact."""

    name: str = "identity"
    strip_person_titles: bool = False
    strip_person_initials: bool = False
    strip_person_suffixes: bool = False
    organization_blocklist: frozenset[str] = frozenset()
    person_aliases: Mapping[str, str] = field(default_factory=dict)
    organization_aliases: Mapping[str, str] = field(default_factory=dict)
    organization_weights: Mapping[str, float] = field(default_factory=dict)
    organization_intercept: float = 0.0
    organization_threshold: float | None = None

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Name rules require a profile name")
        for name in ("strip_person_titles", "strip_person_initials", "strip_person_suffixes"):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be boolean")
        if isinstance(self.organization_blocklist, str):
            raise TypeError("organization_blocklist must contain names")
        object.__setattr__(
            self,
            "organization_blocklist",
            frozenset(canonical_entity_name(n) for n in self.organization_blocklist),
        )
        for name in ("person_aliases", "organization_aliases"):
            if not isinstance(getattr(self, name), Mapping):
                raise TypeError(f"{name} must map names to names")
            values = {}
            for source, target in getattr(self, name).items():
                source, target = canonical_entity_name(source), canonical_entity_name(target)
                if not source or not target:
                    raise ValueError("Aliases must have nonempty names")
                values[source] = target
            object.__setattr__(self, name, MappingProxyType(values))
        weights = dict(self.organization_weights)
        if any(
            not isinstance(key, str)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            for key, value in weights.items()
        ):
            raise ValueError("Organization weights require finite numbers and string features")
        if not isinstance(self.organization_intercept, (int, float)) or not math.isfinite(
            self.organization_intercept
        ):
            raise ValueError("Organization intercept must be finite")
        if self.organization_threshold is not None and (
            not isinstance(self.organization_threshold, (int, float))
            or not math.isfinite(self.organization_threshold)
        ):
            raise ValueError("Organization threshold must be finite or None")
        object.__setattr__(self, "organization_weights", MappingProxyType(weights))

    @classmethod
    def from_json(cls, path):
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Name rules must be a JSON object")
        allowed = {item.name for item in fields(cls)}
        extra = payload.keys() - allowed - {"schema", "$schema", "evaluation"}
        if extra:
            raise ValueError(f"Unknown name rule fields: {sorted(extra)}")
        return cls(**{key: value for key, value in payload.items() if key in allowed})

    def apply(self, name, label):
        if label == "ORG":
            if name in self.organization_blocklist:
                return ""
            if self.organization_threshold is not None:
                value = self.organization_intercept + sum(
                    self.organization_weights.get(key, 0.0)
                    for key in sorted(organization_features(name))
                )
                if value < self.organization_threshold:
                    return ""
            return self.organization_aliases.get(name, name)
        if self.strip_person_titles:
            name = re.sub(
                r"^(?:(?:president|prime minister|minister|dr|mr|mrs|ms|sir|dame|prof|professor|rev|reverend|sen|senator|rep|representative|general|gen)\s+)+",
                "",
                name,
            )
        if self.strip_person_suffixes:
            name = re.sub(r"\s+(?:jr|sr|ii|iii|iv)$", "", name)
        if self.strip_person_initials:
            name = " ".join(part for part in name.split() if len(part) != 1)
        return self.person_aliases.get(name, name)


def default_name_rules(resources_dir=None) -> NameRules:
    """Load the fixed development-selected cell normalization and ORG filter."""
    return _cached_name_rules(
        resource_path(
            "lexicons",
            read_resource_json("defaults.json", resources_dir=resources_dir)["ner"],
            resources_dir=resources_dir,
        )
    )


@lru_cache(maxsize=8)
def _cached_name_rules(path):
    return NameRules.from_json(path)


class NERUnavailableError(RuntimeError):
    """The requested optional NER dependency or trained model is unavailable."""


@dataclass(frozen=True)
class EntityMention:
    text: str
    label: str
    start: int
    end: int
    source_label: str | None = None

    def __post_init__(self):
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Entity text must be a nonempty string")
        if self.label not in _LABELS:
            raise ValueError("Entity label must be PERSON, ORG, or LOCATION")
        if (
            type(self.start) is not int
            or type(self.end) is not int
            or not 0 <= self.start < self.end
        ):
            raise ValueError("Entity offsets must be integers with 0 <= start < end")
        if self.source_label is not None and not isinstance(self.source_label, str):
            raise TypeError("source_label must be a string or None")


@dataclass(frozen=True)
class NameMention:
    """A broad named span; includes events, laws and products beyond entity cells."""

    text: str
    start: int
    end: int
    source_label: str = "PROPN"

    def __post_init__(self):
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Name text must be nonempty")
        if (
            type(self.start) is not int
            or type(self.end) is not int
            or not 0 <= self.start < self.end
        ):
            raise ValueError("Name offsets must be valid integers")
        if not isinstance(self.source_label, str) or not self.source_label:
            raise ValueError("Name source label must be nonempty")


@dataclass(frozen=True)
class NERResult:
    text: str
    mentions: tuple[EntityMention, ...]
    backend_name: str = "supplied-mentions"
    name_policy: str = "surface"
    name_rules: NameRules | None = None
    name_mentions: tuple[NameMention, ...] | None = None

    def __post_init__(self):
        if not isinstance(self.text, str):
            raise TypeError("text must be str")
        if not isinstance(self.backend_name, str) or not self.backend_name.strip():
            raise ValueError("backend_name must identify the source")
        if self.name_policy not in _NAME_POLICIES:
            raise ValueError("Unknown entity name policy")
        if self.name_rules is not None and not isinstance(self.name_rules, NameRules):
            raise TypeError("name_rules must be NameRules or None")
        mentions = tuple(self.mentions)
        for mention in mentions:
            if not isinstance(mention, EntityMention):
                raise TypeError("mentions must contain EntityMention instances")
            if (
                mention.end > len(self.text)
                or self.text[mention.start : mention.end] != mention.text
            ):
                raise ValueError("Entity text and offsets must match the original body text")
        object.__setattr__(
            self, "mentions", tuple(sorted(mentions, key=lambda m: (m.start, m.end, m.label)))
        )
        names = (
            tuple(self.name_mentions)
            if self.name_mentions is not None
            else tuple(
                NameMention(m.text, m.start, m.end, m.source_label or m.label) for m in mentions
            )
        )
        for name in names:
            if not isinstance(name, NameMention):
                raise TypeError("name_mentions must contain NameMention records")
            if name.end > len(self.text) or self.text[name.start : name.end] != name.text:
                raise ValueError("Name spans must match the original body")
        object.__setattr__(
            self,
            "name_mentions",
            tuple(sorted(set(names), key=lambda m: (m.start, m.end, m.source_label))),
        )

    @property
    def all_names(self) -> tuple[NameMention, ...]:
        assert self.name_mentions is not None  # Normalized in __post_init__.
        return self.name_mentions

    @property
    def persons(self) -> tuple[EntityMention, ...]:
        return tuple(m for m in self.mentions if m.label == "PERSON")

    @property
    def organizations(self) -> tuple[EntityMention, ...]:
        return tuple(m for m in self.mentions if m.label == "ORG")

    @property
    def locations(self) -> tuple[EntityMention, ...]:
        return tuple(m for m in self.mentions if m.label == "LOCATION")

    def to_gkg(self, label: str, *, enhanced: bool = False) -> str:
        """Distinct names for legacy fields; every mention for enhanced fields."""
        if label == "LOCATION":
            raise NotImplementedError(
                "Location mentions require geographic resolution before GKG serialization"
            )
        if label not in {"PERSON", "ORG"}:
            raise ValueError("GKG entity label must be PERSON or ORG")
        entries = []
        for mention in self.mentions:
            if mention.label != label:
                continue
            name = text_component(mention.text, separators=";,")
            if self.name_policy != "surface":
                name = canonical_entity_name(name)
                if self.name_rules is not None:
                    name = self.name_rules.apply(name, label)
                if len(name.split()) < 2 and (
                    label == "PERSON" or self.name_policy == "gdelt-full-names"
                ):
                    continue
            if not name:
                continue
            entries.append(f"{name},{mention.start}" if enhanced else name)
        if not enhanced:
            entries = list(dict.fromkeys(entries))
        return ";".join(entries)


class EntityRecognizer(Protocol):
    def analyze(self, text: str) -> NERResult: ...


class SpacyNER:
    """Wrap a loaded spaCy pipeline; load once and reuse across documents."""

    def __init__(
        self,
        nlp,
        *,
        name: str | None = None,
        filter_spans: bool = True,
        name_policy: str = "surface",
        name_rules: NameRules | None = None,
    ):
        if not callable(nlp) or not {"ner", "entity_ruler"}.intersection(nlp.pipe_names):
            raise ValueError("Provide a spaCy pipeline with ner or entity_ruler")
        self.nlp = nlp
        self.filter_spans = filter_spans
        if name_policy not in _NAME_POLICIES:
            raise ValueError("Unknown entity name policy")
        self.name_policy = name_policy
        self.name_rules = name_rules
        meta = nlp.meta
        self.name = (
            name
            or f"spacy:{meta.get('lang', '')}:{meta.get('name', 'custom')}:{meta.get('version', '')}"
        )

    @classmethod
    def from_model(
        cls,
        model: str = "en_core_web_sm",
        *,
        name_policy: str = "gdelt-full-names",
        name_rules: NameRules | None = None,
        resources_dir=None,
    ) -> SpacyNER:
        try:
            import spacy
        except ImportError as error:
            raise NERUnavailableError(
                "Install gdelt-regkg to use spaCy, or supply another recognizer"
            ) from error
        try:
            nlp = spacy.load(model)
        except OSError as error:
            raise NERUnavailableError(
                f"Install model {model!r} with python -m spacy download {model}, or provide a loaded pipeline"
            ) from error
        # POS tags also supply proper names outside the entity categories.
        nlp.disable_pipes(*[pipe for pipe in ("parser", "lemmatizer") if pipe in nlp.pipe_names])
        if name_rules is None and name_policy == "gdelt-full-names":
            name_rules = default_name_rules(resources_dir)
        return cls(nlp, name_policy=name_policy, name_rules=name_rules)

    def analyze(self, text: str) -> NERResult:
        if not isinstance(text, str):
            raise TypeError("text must be str")
        doc = self.nlp(text)
        return self._analyze_doc(text, doc)

    def analyze_many(self, texts: Iterable[str], *, batch_size: int = 32):
        """Batch the model while retaining the same mention filtering and offsets."""
        if type(batch_size) is not int or batch_size < 1:
            raise ValueError("batch_size must be a positive integer")
        texts = list(texts)
        if any(not isinstance(text, str) for text in texts):
            raise TypeError("texts must contain strings")
        for text, doc in zip(texts, self.nlp.pipe(texts, batch_size=batch_size), strict=True):
            yield self._analyze_doc(text, doc)

    def _analyze_doc(self, text, doc):
        if doc.text != text:
            raise ValueError("NER backend must preserve the original body text")
        mentions = []
        names = []
        for ent in doc.ents:
            if ent.label_ in _NAME_LABELS:
                names.append(
                    NameMention(
                        text[ent.start_char : ent.end_char],
                        ent.start_char,
                        ent.end_char,
                        ent.label_,
                    )
                )
        for ent in doc.ents:
            if ent.label_ not in _SPACY_LABELS:
                continue
            start, end = ent.start_char, ent.end_char
            if self.filter_spans and ent.label_ in {"PERSON", "ORG"}:
                name = text[start:end]
                suffix = re.search(
                    r"\s+(?:(?:official|corporate|publishing)\s+)?(?:website|web\s+site|homepage)\b",
                    name,
                    re.I,
                )
                if suffix:
                    end = start + suffix.start()
                    name = text[start:end]
                limit = 6 if ent.label_ == "PERSON" else 12
                if (
                    not name.strip()
                    or len(name.split()) > limit
                    or len(name) > 120
                    or "\n\n" in name
                    or _PAGE_TEXT.search(name)
                ):
                    continue
            mentions.append(
                EntityMention(text[start:end], _SPACY_LABELS[ent.label_], start, end, ent.label_)
            )
        # Entity ruler pipelines without a tagger can still provide broad names.
        if hasattr(doc, "has_annotation") and doc.has_annotation("POS") is True:
            tokens = list(doc)
            i = 0
            while i < len(tokens):
                if tokens[i].pos_ != "PROPN":
                    i += 1
                    continue
                start = i
                i += 1
                while i < len(tokens) and i - start < 12:
                    if tokens[i].pos_ == "PROPN":
                        i += 1
                    elif (
                        tokens[i].lower_ in {"of", "the", "and", "for"}
                        and i + 1 < len(tokens)
                        and tokens[i + 1].pos_ == "PROPN"
                    ):
                        i += 2
                    else:
                        break
                a, b = tokens[start].idx, tokens[i - 1].idx + len(tokens[i - 1])
                if not any(a < ent.end_char and ent.start_char < b for ent in doc.ents):
                    names.append(NameMention(text[a:b], a, b))
        return NERResult(
            text, tuple(mentions), self.name, self.name_policy, self.name_rules, tuple(names)
        )


@lru_cache(maxsize=1)
def default_recognizer() -> SpacyNER:
    """Load the installed English model lazily; never download it automatically."""
    return SpacyNER.from_model()


def analyze_entities(
    text: str,
    *,
    recognizer: EntityRecognizer | None = None,
    mentions: Iterable[EntityMention] | None = None,
) -> NERResult:
    """Analyze body text or validate supplied mentions in original coordinates."""
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if mentions is not None:
        if recognizer is not None:
            raise ValueError("Supply a recognizer or mentions, not both")
        return NERResult(text, tuple(mentions))
    recognizer = default_recognizer() if recognizer is None else recognizer
    result = recognizer.analyze(text)
    if not isinstance(result, NERResult) or result.text != text:
        raise ValueError("Recognizer must return NERResult for the unchanged input text")
    return result
