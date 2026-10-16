"""Named build recipes and output labels, independent of source discovery."""

from collections.abc import Iterable

from .gcam import PROFILE_ALIASES

RECIPES = {
    "tone": ("v1", "v2", "v3"),
    "themes": ("v1", "v2", "v3", "authored"),
    "counts": ("v1", "v2", "v3"),
    "ner": ("v1",),
    "locations": ("v1",),
    "gcam": ("v1", "v2", "v3", "v4", "v5", "full"),
}
DEFAULT_RECIPES = {
    "tone": "v3",
    "themes": "v3",
    "counts": "v3",
    "ner": "v1",
    "locations": "v1",
    "gcam": "v3",
}


def select_recipes(targets: Iterable[str], use: str = "best") -> dict[str, str]:
    selections = {}
    for target in targets:
        if target not in RECIPES:
            raise ValueError(f"Unknown build target: {target}")
        selected = DEFAULT_RECIPES[target] if use == "best" else use
        if target == "gcam":
            selected = PROFILE_ALIASES.get(selected, selected)
        if selected not in RECIPES[target]:
            raise ValueError(
                f"Recipe {use!r} is unavailable for {target}; choose {', '.join(RECIPES[target])}"
            )
        selections[target] = selected
    return selections


def validate_suffix(suffix: str | None):
    if suffix is not None and (
        not suffix
        or not suffix[0].isalnum()
        or any(not (character.isalnum() or character in "._-") for character in suffix)
    ):
        raise ValueError(
            "--suffix must start with a letter or digit and contain only letters, digits, '.', '_' or '-'"
        )


def label_filename(filename: str, suffix: str | None) -> str:
    """Replace only the profile label, preserving its format and resource stem."""
    if suffix is None:
        return filename
    extension = ".json.gz" if filename.endswith(".json.gz") else ".json"
    return filename.split(".", 1)[0] + "." + suffix + extension
