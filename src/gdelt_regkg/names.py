"""Broad names from a shared NER result, independent of person/ORG cell filters."""

from __future__ import annotations

from dataclasses import dataclass

from .ner import EntityRecognizer, NameMention, NERResult, analyze_entities
from .wire import text_component


@dataclass(frozen=True)
class NameResult:
    text: str
    mentions: tuple[NameMention, ...]
    backend_name: str

    def to_gkg(self):
        return ";".join(
            f"{text_component(m.text, separators=';,')},{m.start}" for m in self.mentions
        )


def analyze_names(
    text: str, *, recognizer: EntityRecognizer | None = None, ner: NERResult | None = None
) -> NameResult:
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if recognizer is not None and ner is not None:
        raise ValueError("Supply recognizer or ner, not both")
    ner = analyze_entities(text, recognizer=recognizer) if ner is None else ner
    if not isinstance(ner, NERResult) or ner.text != text:
        raise ValueError("NER result must refer to the unchanged body")
    return NameResult(text, ner.all_names, ner.backend_name)
