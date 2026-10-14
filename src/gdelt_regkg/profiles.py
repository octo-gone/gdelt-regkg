"""Explicit, lazy resource composition for record generation."""

from __future__ import annotations

from dataclasses import dataclass

from .fields.counts import CountRules, default_count_rules
from .fields.gcam import GCAMLexicon, default_gcam_lexicon
from .fields.locations import Gazetteer, default_gazetteer
from .fields.ner import EntityRecognizer
from .fields.themes import ThemeLexicon, default_theme_lexicon
from .fields.tone import ToneLexicon, default_tone_lexicon
from .types import StrPath


@dataclass(frozen=True)
class Resources:
    resources_dir: StrPath | None = None
    tone_lexicon: ToneLexicon | None = None
    theme_lexicon: ThemeLexicon | None = None
    count_rules: CountRules | None = None
    gazetteer: Gazetteer | None = None
    gcam_lexicon: GCAMLexicon | None = None
    recognizer: EntityRecognizer | None = None

    def tone(self) -> ToneLexicon:
        return (
            self.tone_lexicon
            if self.tone_lexicon is not None
            else default_tone_lexicon(self.resources_dir)
        )

    def themes(self) -> ThemeLexicon:
        return (
            self.theme_lexicon
            if self.theme_lexicon is not None
            else default_theme_lexicon(self.resources_dir)
        )

    def counts(self) -> CountRules:
        return (
            self.count_rules
            if self.count_rules is not None
            else default_count_rules(self.resources_dir)
        )

    def places(self) -> Gazetteer:
        return (
            self.gazetteer if self.gazetteer is not None else default_gazetteer(self.resources_dir)
        )

    def gcam(self) -> GCAMLexicon:
        return (
            self.gcam_lexicon
            if self.gcam_lexicon is not None
            else default_gcam_lexicon(self.resources_dir)
        )
