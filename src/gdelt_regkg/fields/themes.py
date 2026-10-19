"""Literal theme matching with source-text character offsets."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..types import StrPath

_TOKEN = re.compile(r"\w+(?:['’]\w+)*|[^\w\s]")
_CODE = re.compile(r"[A-Z][A-Z0-9_-]*")


@dataclass(frozen=True)
class ThemeRule:
    """A theme label and literal phrase with document-wide context conditions.

    Each `requires_all` group needs at least one matching phrase. Any matching
    `exclude_any` phrase suppresses the rule.
    """

    theme: str
    phrase: str
    requires_all: tuple[tuple[str, ...], ...] = ()
    exclude_any: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.theme, str) or not _CODE.fullmatch(self.theme):
            raise ValueError(
                "Theme codes must contain uppercase letters, digits, underscores or hyphens"
            )
        if not isinstance(self.phrase, str) or not self.phrase.strip():
            raise ValueError("A theme phrase must be a nonempty string")
        if any(c in self.phrase for c in "{}\t\r\n"):
            raise ValueError("Use literal single-line phrases, without template braces")
        if isinstance(self.requires_all, str) or isinstance(self.exclude_any, str):
            raise TypeError("Theme conditions must be phrase collections")
        groups = []
        for group in self.requires_all:
            if isinstance(group, str) or not group:
                raise ValueError("Each requires_all group must be a nonempty phrase list")
            groups.append(tuple(group))
        excluded = tuple(self.exclude_any)
        for phrase in [p for group in groups for p in group] + list(excluded):
            if (
                not isinstance(phrase, str)
                or not phrase.strip()
                or any(c in phrase for c in "{}\t\r\n")
            ):
                raise ValueError("Theme conditions require nonempty literal single-line phrases")
        object.__setattr__(self, "requires_all", tuple(groups))
        object.__setattr__(self, "exclude_any", excluded)


@dataclass(frozen=True)
class ThemeLexicon:
    """Reusable named collection of literal theme rules.

    Matching uses casefolded token sequences, including punctuation, and ignores
    whitespace between tokens. Context conditions apply across the document.
    """

    name: str
    rules: tuple[ThemeRule, ...]
    _trie: dict = field(init=False, repr=False, compare=False)
    _context_trie: dict = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Lexicon name must identify its source/version")
        rules = tuple(self.rules)
        trie: dict[str | None, Any] = {}
        context_trie: dict[str | None, Any] = {}
        for index, rule in enumerate(rules):
            if not isinstance(rule, ThemeRule):
                raise TypeError("rules must contain ThemeRule instances")
            node = trie
            for token in _TOKEN.findall(rule.phrase):
                node = node.setdefault(token.casefold(), {})
            node.setdefault(None, set()).add(index)
            for phrase in [p for group in rule.requires_all for p in group] + list(
                rule.exclude_any
            ):
                key = tuple(token.casefold() for token in _TOKEN.findall(phrase))
                node = context_trie
                for token in key:
                    node = node.setdefault(token, {})
                node.setdefault(None, set()).add(key)
        object.__setattr__(self, "rules", rules)
        object.__setattr__(self, "_trie", trie)
        object.__setattr__(self, "_context_trie", context_trie)

    @classmethod
    def from_mapping(
        cls, themes: Mapping[str, Iterable[str]], *, name: str = "custom"
    ) -> ThemeLexicon:
        """Build a lexicon from theme codes mapped to collections of phrases.

        Args:
            themes: Theme codes and their literal matching phrases.
            name: Source or version identifier.

        Returns:
            A compiled lexicon ready for `analyze_themes`.
        """
        rules: list[ThemeRule] = []
        for theme, phrases in themes.items():
            if isinstance(phrases, str):
                raise TypeError("Each theme must map to a collection of phrases, not a string")
            rules.extend(ThemeRule(theme, phrase) for phrase in phrases)
        return cls(name, tuple(rules))

    @classmethod
    def from_json(cls, path: str | Path) -> ThemeLexicon:
        """Load source-neutral rules or a legacy theme-code mapping."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if "schema" in data:
            from .rule_inputs import theme_lexicon_from_input

            return theme_lexicon_from_input(data)
        return cls.from_mapping(data["themes"], name=data["name"])


def default_theme_lexicon(resources_dir: StrPath | None = None) -> ThemeLexicon:
    from ..utils import ResourceStore

    return _cached_theme_lexicon(ResourceStore(resources_dir).profile("themes"))


@lru_cache(maxsize=8)
def _cached_theme_lexicon(path):
    return ThemeLexicon.from_json(path)


@dataclass(frozen=True)
class ThemeMention:
    """A theme code and matched text with zero-based start and exclusive end offsets."""

    theme: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class ThemeResult:
    """Theme matches in source order and the name of the lexicon used."""

    mentions: tuple[ThemeMention, ...]
    lexicon_name: str

    def to_gkg(self, *, enhanced: bool = False) -> str:
        """Serialize standard or enhanced theme entries.

        Args:
            enhanced: Include offsets for every mention. Standard output keeps
                distinct theme codes in first-match order.

        Returns:
            Semicolon-terminated entries, or an empty string for no matches.
        """
        if enhanced:
            return "".join(f"{m.theme},{m.start};" for m in self.mentions)
        return "".join(code + ";" for code in dict.fromkeys(m.theme for m in self.mentions))


def analyze_themes(text: str, *, lexicon: ThemeLexicon | None = None) -> ThemeResult:
    """Match literal theme phrases while preserving source character offsets.

    Repeated and overlapping matches are retained. Context conditions inspect
    the whole document; offsets identify each rule's matching phrase.

    Args:
        text: Prepared body in the lexicon's language.
        lexicon: Reusable theme rules. Defaults to the configured local profile.

    Returns:
        Theme mentions in source order and the lexicon identity.

    Raises:
        TypeError: If `text` or `lexicon` has an invalid type.
        ResourceUnavailableError: If the default local profile is unavailable.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    lexicon = default_theme_lexicon() if lexicon is None else lexicon
    if not isinstance(lexicon, ThemeLexicon):
        raise TypeError("lexicon must be ThemeLexicon")
    tokens = list(_TOKEN.finditer(text))
    values = [m.group().casefold() for m in tokens]
    present = set()
    if lexicon._context_trie:
        for i in range(len(tokens)):
            node = lexicon._context_trie
            for j in range(i, len(tokens)):
                child = node.get(values[j])
                if child is None:
                    break
                node = child
                present.update(node.get(None, ()))
    allowed = []
    for rule in lexicon.rules:

        def seen(phrase):
            return tuple(token.casefold() for token in _TOKEN.findall(phrase)) in present

        allowed.append(
            all(any(seen(p) for p in group) for group in rule.requires_all)
            and not any(seen(p) for p in rule.exclude_any)
        )
    mentions = {}
    for i, token in enumerate(tokens):
        node = lexicon._trie
        for j in range(i, len(tokens)):
            child = node.get(values[j])
            if child is None:
                break
            node = child
            for index in node.get(None, ()):
                if not allowed[index]:
                    continue
                theme = lexicon.rules[index].theme
                end = tokens[j].end()
                mentions[theme, token.start(), end] = ThemeMention(
                    theme, token.start(), end, text[token.start() : end]
                )
    return ThemeResult(
        tuple(sorted(mentions.values(), key=lambda m: (m.start, m.theme, m.end))), lexicon.name
    )
