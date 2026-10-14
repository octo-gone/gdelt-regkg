"""Concise caller-side composition used by the existing extraction scenarios."""

import json
from dataclasses import fields
from pathlib import Path

from gdelt_regkg import RecordMetadata, Resources, generate_gkg
from gdelt_regkg.fields.counts import CountRules
from gdelt_regkg.fields.ner import NERResult
from gdelt_regkg.fields.rule_inputs import (
    count_rules_from_input,
    load_count_rules,
    load_theme_lexicon,
    theme_lexicon_from_input,
)
from gdelt_regkg.fields.themes import ThemeLexicon
from gdelt_regkg.fields.translation import translate_text


def compose_resources(data, theme_path=None):
    if theme_path is not None:
        return Resources(
            count_rules=load_count_rules(data), theme_lexicon=load_theme_lexicon(theme_path)
        )
    counts, themes = data["count_rules"], data["theme_lexicon"]
    return Resources(
        count_rules=count_rules_from_input(counts)
        if "schema" in counts
        else CountRules.from_dict(counts),
        theme_lexicon=theme_lexicon_from_input(themes)
        if "schema" in themes
        else ThemeLexicon.from_mapping(themes["themes"], name=themes["name"]),
    )


def read_resources(path):
    return compose_resources(json.loads(Path(path).read_text(encoding="utf-8")))


def make_record(text, **inputs):
    """Build metadata/resources explicitly and translate before calling the API."""
    metadata_names = {f.name for f in fields(RecordMetadata)}
    metadata = RecordMetadata(
        **{name: inputs.pop(name) for name in tuple(inputs) if name in metadata_names}
    )
    translator = inputs.pop("translator", None)
    translation_options = {
        name: inputs.pop(name)
        for name in ("detect_missing_language", "language_detector", "language_check")
        if name in inputs
    }
    language = inputs.pop("input_language", None)
    if translator is not None:
        result = translate_text(
            text, language=language, translator=translator, **translation_options
        )
        metadata = RecordMetadata.from_translation(result, metadata)
        text = result.text
    ner = inputs.pop("ner", None)
    resources = inputs.pop("config", None) or Resources()
    from dataclasses import replace

    resource_names = {f.name for f in fields(Resources)}
    resources = replace(
        resources, **{name: inputs.pop(name) for name in tuple(inputs) if name in resource_names}
    )
    if ner is not None and not isinstance(ner, NERResult):
        resources = replace(resources, recognizer=ner)
    return generate_gkg(
        text,
        metadata,
        resources,
        ner_result=ner if isinstance(ner, NERResult) else None,
        overrides=inputs.pop("field_values", None),
        **inputs,
    )
