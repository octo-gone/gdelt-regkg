"""Static consumer contract; do not execute model/resource loading calls."""

from pathlib import Path
from typing import assert_type

from gdelt_regkg import GKGRecord, RecordMetadata, Resources, generate_gkg
from gdelt_regkg.fields.counts import CountRules
from gdelt_regkg.fields.gcam import GCAMLexicon, GCAMResult, analyze_gcam
from gdelt_regkg.fields.locations import Gazetteer
from gdelt_regkg.fields.ner import NameRules, SpacyNER
from gdelt_regkg.fields.rule_inputs import load_count_rules, load_theme_lexicon
from gdelt_regkg.fields.themes import ThemeLexicon
from gdelt_regkg.fields.translation import M2M100Translator, TranslationResult

path = Path("profile.json")
assert_type(CountRules.from_dict({}), CountRules)
assert_type(CountRules.from_json(path), CountRules)
assert_type(ThemeLexicon.from_mapping({}), ThemeLexicon)
assert_type(ThemeLexicon.from_json(path), ThemeLexicon)
assert_type(GCAMLexicon.from_json(path), GCAMLexicon)
assert_type(GCAMLexicon.from_json(path).without_dictionaries(("roget", 26)), GCAMLexicon)
assert_type(GCAMLexicon.from_json(path).implemented_dimensions, tuple[str, ...])
assert_type(analyze_gcam("body", disabled_dictionaries=("roget", 26)), GCAMResult)
assert_type(analyze_gcam("body", original_text="texte", original_language="fra"), GCAMResult)
assert_type(GCAMLexicon.from_json(path).for_language("fra"), GCAMLexicon)
assert_type(analyze_gcam("body").native_word_count, int | None)
assert_type(Gazetteer.from_json(path), Gazetteer)
assert_type(load_count_rules(path), CountRules)
assert_type(load_theme_lexicon(path), ThemeLexicon)
assert_type(SpacyNER.from_model(), SpacyNER)
assert_type(NameRules.from_json(path), NameRules)
assert_type(M2M100Translator.from_model(), M2M100Translator)
metadata = RecordMetadata("https://example.org", "20250102120000", 1)
assert_type(
    RecordMetadata.from_translation(TranslationResult("x", "x", "eng", None), metadata),
    RecordMetadata,
)
assert_type(generate_gkg("body", metadata, Resources()), GKGRecord)
assert_type(generate_gkg("body", metadata, Resources(), gcam_original_text="texte"), GKGRecord)
assert_type(
    generate_gkg("body", metadata, Resources(), gcam_disabled_dictionaries=("roget", 26)), GKGRecord
)
assert_type(GKGRecord.from_mapping({}), GKGRecord)
assert_type(GKGRecord.from_mapping({}).to_mapping(), dict[str, str | None])
assert_type(GKGRecord.from_mapping({}).to_row(), tuple[str, ...])
