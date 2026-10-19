"""Broad named-span extraction for the GKG all-names field."""

from __future__ import annotations

from dataclasses import dataclass

from ..wire import text_component
from .ner import EntityRecognizer, NameMention, NERResult, analyze_entities


@dataclass(frozen=True)
class NameResult:
    """Named spans for an input body, including the recognizer's identity.

    Attributes:
        text: Analyzed body.
        mentions: Broad name spans with source offsets and labels.
        backend_name: Recognizer identity.
    """

    text: str
    mentions: tuple[NameMention, ...]
    backend_name: str

    def to_gkg(self):
        """Serialize names and offsets, or an empty string for no matches."""
        return ";".join(
            f"{text_component(m.text, separators=';,')},{m.start}" for m in self.mentions
        )


def analyze_names(
    text: str, *, recognizer: EntityRecognizer | None = None, ner: NERResult | None = None
) -> NameResult:
    """Collect broad named spans from a recognizer or precomputed NER result.

    Args:
        text: Prepared body.
        recognizer: Entity recognizer. Defaults to the installed English model.
        ner: Precomputed NER for this exact body; supply it instead of `recognizer`.

    Returns:
        Name spans and the recognizer identity, preserving source coordinates.

    Raises:
        TypeError: If `text` is not a string.
        ValueError: If both NER inputs are supplied or the result describes another body.
        NERUnavailableError: If the default model is unavailable.
        OptionalDependencyError: If the default recognizer's dependency is unavailable.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if recognizer is not None and ner is not None:
        raise ValueError("Supply recognizer or ner, not both")
    ner = analyze_entities(text, recognizer=recognizer) if ner is None else ner
    if not isinstance(ner, NERResult) or ner.text != text:
        raise ValueError("NER result must refer to the unchanged body")
    return NameResult(text, ner.all_names, ner.backend_name)
