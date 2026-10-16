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
    "wordnet-affect-v1": ("wordnet-affect", "wordnet-16", "codebook"),
    "sentiwords": ("sentiwords", "codebook"),
    "general-inquirer-legacy": ("general-inquirer-legacy", "codebook"),
    "themes-experimental": ("codebook",),
    "themes-authored": ("codebook",),
}
for _component in (
    "forest-values",
    "lexicoder-topics",
    "liwc",
    "loughran-mcdonald",
    "opinion-observer",
    "rid",
    "subjectivity",
    "body-boundary",
    "moral-foundations",
    "hogenraad-motive",
    "time",
    "temperament",
    "central-bank",
    "sentiwordnet",
    "anew",
    "ml-senticon",
    "hedonometer",
    "emfd",
    "rid-french",
    "rid-portuguese",
    "rid-swedish",
    "rid-german",
    "rid-hungarian",
    "rid-russian",
    "anew-spanish",
    "french-imagery",
    "portuguese-emotion",
    "hogenraad-motive-french",
    "hogenraad-motive-spanish",
):
    COMPONENT_SOURCES[_component] = (_component, "codebook")
COMPONENT_SOURCES["ml-senticon-multilingual"] = (
    "ml-senticon-ca",
    "ml-senticon-es",
    "ml-senticon-gl",
    "codebook",
)
COMPONENT_SOURCES["hedonometer-multilingual"] = tuple(
    "hedonometer-" + code
    for code in ("ar", "de", "fr", "hi", "id", "ko", "pt", "ru", "es", "ur", "zh")
) + ("codebook",)

V1_COMPONENTS = ()
V2_COMPONENTS = ("vader",)
V3_COMPONENTS = (
    *V2_COMPONENTS,
    "general-inquirer",
    "wordnet-lexical",
    "wordnet-affect",
    "wordnet-domains",
    "themes",
)
V4_COMPONENTS = (
    *V3_COMPONENTS,
    "roget",
    "lexicoder",
)
V5_COMPONENTS = (
    *V4_COMPONENTS,
    "wordnet-affect-v1",
    "sentiwords",
    "general-inquirer-legacy",
    "forest-values",
    "lexicoder-topics",
    "rid",
    "body-boundary",
    "opinion-observer",
    "loughran-mcdonald",
    "central-bank",
    "sentiwordnet",
    "moral-foundations",
    "anew",
    "hedonometer",
    "emfd",
    "ml-senticon",
    "ml-senticon-multilingual",
    "hedonometer-multilingual",
    "anew-spanish",
    "rid-french",
    "rid-portuguese",
    "rid-swedish",
    "rid-german",
    "rid-hungarian",
    "themes-authored",
    "french-imagery",
)
PROFILE_COMPONENTS = {
    "v1": V1_COMPONENTS,
    "v2": V2_COMPONENTS,
    "v3": V3_COMPONENTS,
    "v4": V4_COMPONENTS,
    "v5": V5_COMPONENTS,
}
PROFILE_ALIASES = {"full": "v5"}


@dataclass(frozen=True)
class GCAMOptions:
    profile: str | None = None
    baseline: Path | None = None
    additions: tuple[str, ...] = ()
    affect_propagate_hierarchy: bool = False
    affect_nouns_only: bool = False

    def __post_init__(self):
        if self.profile is not None:
            object.__setattr__(self, "profile", PROFILE_ALIASES.get(self.profile, self.profile))
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
            "v4": "gcam.v4.json.gz",
            "v5": "gcam.v5.json.gz",
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
