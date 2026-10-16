"""Stable GCAM dictionary identities shared by scoring, builds and reports.

IDs follow the codebook's Variable column, including the c41 correction.
Language applicability is carried by individual compiled dimensions.
"""

from collections.abc import Iterable
from types import MappingProxyType

DICTIONARIES = MappingProxyType(
    {
        1: "forest-values",
        2: "general-inquirer",
        3: "lexicoder",
        4: "lexicoder-topics",
        5: "liwc",
        6: "loughran-mcdonald",
        7: "opinion-observer",
        8: "rid",
        9: "roget",
        10: "sentiwordnet",
        11: "sentiwords",
        12: "subjectivity",
        13: "body-boundary",
        14: "wordnet-affect-v1",
        15: "wordnet-affect",
        16: "wordnet-domains",
        17: "wordnet-lexical",
        18: "themes",
        19: "anew",
        20: "ml-senticon",
        21: "hedonometer",
        22: "anew-spanish",
        23: "ml-senticon-multilingual",
        24: "hedonometer-multilingual",
        25: "moral-foundations",
        26: "vader",
        27: "portuguese-emotion",
        28: "rid-french",
        29: "rid-russian",
        30: "rid-hungarian",
        31: "rid-swedish",
        32: "rid-portuguese",
        33: "rid-german",
        35: "hogenraad-motive",
        36: "hogenraad-motive-french",
        37: "hogenraad-motive-spanish",
        38: "french-imagery",
        39: "time",
        40: "temperament",
        41: "central-bank",
        42: "emfd",
    }
)
DICTIONARY_IDS = MappingProxyType(
    {
        **{name: code for code, name in DICTIONARIES.items()},
        "general-inquirer-legacy": 2,
        "themes-experimental": 18,
        "themes-authored": 18,
    }
)


def dictionary_id(key: str) -> int:
    return int(key[1:].split(".", 1)[0])


def resolve_dictionaries(
    values: Iterable[int | str], *, custom_ids: Iterable[int] = ()
) -> tuple[int, ...]:
    """Resolve a collection of canonical names or positive numeric IDs.

    Known dictionaries absent from a profile are valid no-ops. Custom dictionary
    IDs must occur in the supplied profile. Bare strings and bools are rejected.
    """
    if isinstance(values, (str, bytes)):
        raise TypeError("disabled_dictionaries must be a collection of names or IDs")
    known = set(DICTIONARIES) | set(custom_ids)
    result = set()
    for value in values:
        code: int | None
        if type(value) is int:
            code = value
        elif isinstance(value, str):
            name = value.strip().casefold()
            code = int(name) if name.isascii() and name.isdecimal() else DICTIONARY_IDS.get(name)
        else:
            raise TypeError("Dictionary selectors must be names or integer IDs")
        if code is None or code not in known:
            raise ValueError(f"Unknown GCAM dictionary: {value!r}")
        result.add(code)
    return tuple(sorted(result))
