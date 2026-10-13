"""Compile selected profiles using the existing source-format converters."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from functools import cached_property
from time import perf_counter

from gdelt_regkg.builders.gazetteer import build_gazetteer
from gdelt_regkg.builders.gcam_expansion import (
    add_general_inquirer,
    add_roget,
    add_themes,
    add_wordnet_affect,
    add_wordnet_domains,
    add_wordnet_lexical,
    read_codebook,
)
from gdelt_regkg.builders.gcam_lexicon import (
    LEXICODER_CATEGORIES,
    build_gcam_lexicon,
    extend_gcam_lexicon,
)
from gdelt_regkg.builders.themes import (
    authored_theme_input,
    merge_inputs,
    restore_crisislex,
    revise_themes,
)
from gdelt_regkg.builders.tone import build_lexicon, revise_tone
from gdelt_regkg.fields.gcam import _load, read_gcam_json
from gdelt_regkg.fields.ner import NameRules
from gdelt_regkg.fields.rule_inputs import count_rules_from_input, theme_lexicon_from_input
from gdelt_regkg.utils import packaged_resource_path, read_resource_json

from .gcam import COMPONENT_PREFIXES, STANDARD_COMPONENTS
from .inputs import BuildInputs
from .progress import Progress, ignore_progress
from .validation import validate_output


@dataclass(frozen=True)
class Artifact:
    path: str
    payload: dict


@dataclass
class BuildContext:
    inputs: BuildInputs
    progress: Progress = ignore_progress

    @cached_property
    def themes(self):
        """Compile once whether themes, GCAM, or both need this dependency."""
        if self.inputs.authored_themes_only:
            self.progress("[themes] Compiling authored rules")
            return authored_theme_input()
        self.progress("[themes] Restoring CrisisLex rules")
        first = restore_crisislex(
            read_resource_json("themes", "themes-count-candidates-v2.json"),
            self.inputs.sources["crisislex"],
        )
        recipe = self.inputs.recipes.get("themes", "v3")
        if recipe == "v1":
            profile = merge_inputs([first], name="gdelt-theme-candidates-v2")
            profile["$schema"] = "../schemas/theme-rules.schema.json"
            return profile
        self.progress("[themes] Merging seed rules")
        baseline = merge_inputs(
            [first, read_resource_json("themes", "theme_seeds.json")],
            name="gdelt-theme-candidates-v3",
        )
        baseline["$schema"] = "../schemas/theme-rules.schema.json"
        if recipe == "v2":
            return baseline
        self.progress("[themes] Applying v3 revision")
        return revise_themes(baseline, read_resource_json("themes", "revision.v3.json"))


def build_tone(context: BuildContext) -> tuple[Artifact, ...]:
    context.progress("[tone] Importing General Inquirer")
    profile = build_lexicon(context.inputs.sources["general-inquirer"])
    recipe = context.inputs.recipes["tone"]
    for version in range(2, int(recipe[1:]) + 1):
        context.progress(f"[tone] Applying v{version} revision")
        profile = revise_tone(profile, read_resource_json("tone", f"v{version}-edits.json"))
    return (Artifact(f"lexicons/tone.{recipe}.json", profile),)


def build_themes(context: BuildContext) -> tuple[Artifact, ...]:
    name = f"themes.{context.inputs.recipes['themes']}.json"
    theme_lexicon_from_input(context.themes)
    return (Artifact("lexicons/" + name, context.themes),)


def build_counts(context: BuildContext) -> tuple[Artifact, ...]:
    recipe = context.inputs.recipes["counts"]
    profile = read_resource_json("counts", f"rules.{recipe}.json")
    count_rules_from_input(profile)
    return (Artifact(f"lexicons/counts.{recipe}.json", profile),)


def build_names(_context: BuildContext) -> tuple[Artifact, ...]:
    NameRules.from_json(packaged_resource_path("ner", "names.v1.json"))
    return (Artifact("lexicons/names.v1.json", read_resource_json("ner", "names.v1.json")),)


def build_locations(context: BuildContext) -> tuple[Artifact, ...]:
    context.progress(
        f"[locations] Compiling {len(context.inputs.gazetteer_archives)} reference archives"
    )
    return (
        Artifact(
            "lexicons/" + context.inputs.gazetteer_filename,
            build_gazetteer(context.inputs.gazetteer_archives, name=context.inputs.gazetteer_name),
        ),
    )


def build_gcam(context: BuildContext) -> tuple[Artifact, ...]:
    sources = context.inputs.sources
    options = context.inputs.gcam
    context.progress(
        f"[gcam] Reading baseline: {options.baseline}"
        if options.baseline is not None
        else "[gcam] Importing General Inquirer baseline"
    )
    profile = (
        read_gcam_json(options.baseline)
        if options.baseline is not None
        else build_gcam_lexicon(sources["general-inquirer"])
    )
    _load(profile)
    if "codebook" in sources:
        context.progress("[gcam] Reading codebook")
    book = read_codebook(sources["codebook"]) if "codebook" in sources else None
    for component in options.components:
        context.progress(f"[gcam] Compiling {component}")
        if prefix := COMPONENT_PREFIXES.get(component):
            profile = copy.deepcopy(profile)
            profile["dimensions"] = [
                dimension
                for dimension in profile["dimensions"]
                if not dimension["key"].startswith(prefix)
            ]
        if component in ("vader", "lexicoder"):
            # These importers append dimensions. Replacing a selected family must
            # first discard its existing keys, especially when expanding a baseline.
            replaced = {"v26.1"} if component == "vader" else set(LEXICODER_CATEGORIES)
            profile = copy.deepcopy(profile)
            name = profile["name"]
            profile["dimensions"] = [d for d in profile["dimensions"] if d["key"] not in replaced]
            profile = extend_gcam_lexicon(profile, **{component + "_source": sources[component]})
            if options.baseline is not None or component == "lexicoder":
                profile["name"] = name + "-" + component
        elif component == "general-inquirer":
            profile = add_general_inquirer(profile, sources["general-inquirer"], book)
        elif component == "roget":
            profile = add_roget(profile, sources["roget"], sources["wordnet-31"], book)
        elif component == "wordnet-lexical":
            profile = add_wordnet_lexical(profile, sources["wordnet-31"], book)
        elif component == "wordnet-affect":
            profile = add_wordnet_affect(
                profile,
                sources["wordnet-affect"],
                sources["wordnet-16"],
                book,
                propagate_hierarchy=options.affect_propagate_hierarchy,
                nouns_only=options.affect_nouns_only,
            )
        elif component == "wordnet-domains":
            profile = add_wordnet_domains(
                profile, sources["wordnet-domains"], sources["wordnet-20"], book
            )
        elif component == "themes":
            profile = add_themes(profile, book, theme_lexicon_from_input(context.themes))
    if (
        options.baseline is None
        and options.components == STANDARD_COMPONENTS
        and not (options.affect_propagate_hierarchy or options.affect_nouns_only)
    ):
        profile["name"] = "general-inquirer-wordnet-themes-vader-gcam-v3"
    if any(
        component.startswith("wordnet-") or component == "roget" for component in options.components
    ):
        profile["wordnet_parsing"] = (
            "Strip documented adjective syntactic flags (a), (p), (ip) before normalizing lemmas"
        )
    annotation_url = read_resource_json("recipes.json")["sources"]["wordnet-annotations"]["url"]
    for component, key in (
        ("wordnet-affect", "wordnet-affect-1.1"),
        ("wordnet-domains", "wordnet-domains-3.2"),
    ):
        if component in options.components:
            profile["sources"][key]["retrieval_url"] = annotation_url
    _load(profile)
    filename = (
        options.filename if context.inputs.gcam_filename is None else context.inputs.gcam_filename
    )
    artifacts = [Artifact("lexicons/" + filename, profile)]
    if book is not None:
        artifacts.append(Artifact("gcam/codebook.v1.json", book))
    return tuple(artifacts)


BUILDERS = {
    "tone": build_tone,
    "themes": build_themes,
    "counts": build_counts,
    "ner": build_names,
    "locations": build_locations,
    "gcam": build_gcam,
}


def compile_profiles(
    inputs: BuildInputs,
    *,
    progress: Progress = ignore_progress,
) -> tuple[tuple[Artifact, ...], dict[str, str]]:
    """Compile the requested profiles and their schemas before publishing."""
    context = BuildContext(inputs, progress)
    recorded_outputs = read_resource_json("recipes.json").get("outputs", {})
    artifacts: list[Artifact] = []
    defaults: dict[str, str] = {}
    for index, target in enumerate(inputs.targets, 1):
        recipe = (
            "baseline"
            if target == "gcam" and inputs.gcam.baseline is not None
            else inputs.recipes[target]
        )
        progress(f"[build {index}/{len(inputs.targets)}] Building {target} ({recipe})")
        started = perf_counter()
        built = BUILDERS[target](context)
        # Every builder returns one selected profile first, followed by support
        # artifacts (such as the codebook). Labels affect only the profile file.
        profile = built[0]
        reference = profile.path.removeprefix("lexicons/")
        if target == "gcam":
            reference = inputs.gcam.filename
        elif target == "locations":
            reference = "locations.v1.json.gz"
        validate_output(reference, profile.payload, recorded_outputs, progress=progress)
        filename = inputs.filename(profile.path.removeprefix("lexicons/"))
        built = (Artifact("lexicons/" + filename, profile.payload), *built[1:])
        defaults[target] = built[0].path.removeprefix("lexicons/")
        artifacts.extend(built)
        progress(
            f"[build {index}/{len(inputs.targets)}] Ready {filename} ({perf_counter() - started:.1f}s)"
        )
    for schema in packaged_resource_path("schemas").iterdir():
        if schema.name.endswith(".schema.json"):
            artifacts.append(
                Artifact("schemas/" + schema.name, json.loads(schema.read_text(encoding="utf-8")))
            )
    paths = [artifact.path for artifact in artifacts]
    if len(paths) != len(set(paths)):
        raise ValueError("Output filenames collide; choose distinct profile filenames")
    return tuple(artifacts), defaults
