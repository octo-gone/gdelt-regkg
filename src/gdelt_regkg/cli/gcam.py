"""GCAM build selections and their source dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

COMPONENT_SOURCES = {
    "general-inquirer": ("general-inquirer", "codebook"),
    "vader": ("vader",),
    "roget": ("roget", "wordnet-31", "codebook"),
    "wordnet-lexical": ("wordnet-31", "codebook"),
    "wordnet-affect": ("wordnet-affect", "wordnet-16", "codebook"),
    "wordnet-domains": ("wordnet-domains", "wordnet-20", "codebook"),
    "themes": ("crisislex", "codebook"),
    "lexicoder": ("lexicoder",),
}
STANDARD_COMPONENTS = (
    "vader",
    "general-inquirer",
    "wordnet-lexical",
    "wordnet-affect",
    "wordnet-domains",
    "themes",
)
PROFILE_COMPONENTS = {
    "v1": (),
    "v2": ("vader",),
    "v3": STANDARD_COMPONENTS,
    "full": (*STANDARD_COMPONENTS, "roget", "lexicoder"),
}
# Native GCAM dictionary prefixes. Replacing one of these families must also
# remove categories no longer present in the newly selected source or variant.
COMPONENT_PREFIXES = {
    "roget": "c9.",
    "wordnet-affect": "c15.",
    "wordnet-domains": "c16.",
    "wordnet-lexical": "c17.",
    "themes": "c18.",
}


@dataclass(frozen=True)
class GCAMOptions:
    profile: str | None = None
    baseline: Path | None = None
    additions: tuple[str, ...] = ()
    affect_propagate_hierarchy: bool = False
    affect_nouns_only: bool = False

    def __post_init__(self):
        if self.profile is not None and self.profile not in PROFILE_COMPONENTS:
            raise ValueError(f"Unknown GCAM profile: {self.profile}")
        if self.profile is not None and self.baseline is not None:
            raise ValueError("Choose --use or --gcam-baseline")
        if unknown := set(self.additions) - COMPONENT_SOURCES.keys():
            raise ValueError(f"Unknown GCAM additions: {sorted(unknown)}")
        if (
            self.affect_propagate_hierarchy or self.affect_nouns_only
        ) and "wordnet-affect" not in self.components:
            raise ValueError("Affect options require the wordnet-affect component")

    @property
    def components(self) -> tuple[str, ...]:
        base = () if self.baseline is not None else PROFILE_COMPONENTS[self.profile or "v3"]
        return tuple(dict.fromkeys((*base, *self.additions)))

    @property
    def filename(self) -> str:
        if (
            self.baseline is not None
            or self.additions
            or self.affect_propagate_hierarchy
            or self.affect_nouns_only
        ):
            return "gcam.custom.json.gz"
        return {
            "v1": "gcam.v1.json",
            "v2": "gcam.v2.json",
            "v3": "gcam.v3.json.gz",
            "full": "gcam.full.json.gz",
        }[self.profile or "v3"]

    def required_sources(self) -> tuple[str, ...]:
        base = () if self.baseline is not None else ("general-inquirer",)
        return tuple(
            dict.fromkeys(
                (
                    *base,
                    *(
                        source
                        for component in self.components
                        for source in COMPONENT_SOURCES[component]
                    ),
                )
            )
        )
