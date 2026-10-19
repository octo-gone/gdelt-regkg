"""Resource configuration for GKG record generation."""

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
    """Configure resource overrides and lazily loaded default profiles.

    Supplied objects take precedence. Default profiles are loaded when an accessor
    is called.

    Args:
        resources_dir: Local resource root. Defaults to `local-resources` under
            the current working directory.
        tone_lexicon: Custom tone lexicon.
        theme_lexicon: Custom theme lexicon.
        count_rules: Custom count extraction rules.
        gazetteer: Custom geographic reference.
        gcam_lexicon: Custom GCAM lexicon.
        recognizer: Entity recognizer used during record generation.
    """

    resources_dir: StrPath | None = None
    tone_lexicon: ToneLexicon | None = None
    theme_lexicon: ThemeLexicon | None = None
    count_rules: CountRules | None = None
    gazetteer: Gazetteer | None = None
    gcam_lexicon: GCAMLexicon | None = None
    recognizer: EntityRecognizer | None = None

    def tone(self) -> ToneLexicon:
        """Return the supplied tone lexicon or load the default profile.

        Raises:
            ResourceUnavailableError: If the default profile is missing.
        """
        return (
            self.tone_lexicon
            if self.tone_lexicon is not None
            else default_tone_lexicon(self.resources_dir)
        )

    def themes(self) -> ThemeLexicon:
        """Return the supplied theme lexicon or load the default profile.

        Raises:
            ResourceUnavailableError: If the default profile is missing.
        """
        return (
            self.theme_lexicon
            if self.theme_lexicon is not None
            else default_theme_lexicon(self.resources_dir)
        )

    def counts(self) -> CountRules:
        """Return the supplied count rules or load the default profile.

        Raises:
            ResourceUnavailableError: If the default profile is missing.
        """
        return (
            self.count_rules
            if self.count_rules is not None
            else default_count_rules(self.resources_dir)
        )

    def places(self) -> Gazetteer:
        """Return the supplied gazetteer or load the default profile.

        Raises:
            ResourceUnavailableError: If the default profile is missing.
        """
        return (
            self.gazetteer if self.gazetteer is not None else default_gazetteer(self.resources_dir)
        )

    def gcam(self) -> GCAMLexicon:
        """Return the supplied GCAM lexicon or load the default profile.

        Raises:
            ResourceUnavailableError: If the default profile is missing.
        """
        return (
            self.gcam_lexicon
            if self.gcam_lexicon is not None
            else default_gcam_lexicon(self.resources_dir)
        )
