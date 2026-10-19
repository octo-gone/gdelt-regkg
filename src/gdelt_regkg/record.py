"""The single declaration of GKG record fields and their wire order."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, fields
from typing import Any


def cell(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Expected a string; normalize missing values before extraction")
    if any(c in value for c in "\t\r\n"):
        raise ValueError("GKG cells cannot contain tabs or newlines")
    return value


@dataclass(frozen=True)
class GKGRecord(Mapping[str, str | None]):
    """Typed record; mapping access uses native wire column names."""

    recordid: str = field(metadata={"column": "GKGRECORDID"})
    date: str = field(metadata={"column": "V2.1DATE"})
    source_collection: str = field(metadata={"column": "V2SOURCECOLLECTIONIDENTIFIER"})
    source: str = field(metadata={"column": "V2SOURCECOMMONNAME"})
    document: str = field(metadata={"column": "V2DOCUMENTIDENTIFIER"})
    counts: str | None = field(metadata={"column": "V1COUNTS"})
    enhanced_counts: str | None = field(metadata={"column": "V2.1COUNTS"})
    themes: str | None = field(metadata={"column": "V1THEMES"})
    enhanced_themes: str | None = field(metadata={"column": "V2ENHANCEDTHEMES"})
    locations: str | None = field(metadata={"column": "V1LOCATIONS"})
    enhanced_locations: str | None = field(metadata={"column": "V2ENHANCEDLOCATIONS"})
    persons: str | None = field(metadata={"column": "V1PERSONS"})
    enhanced_persons: str | None = field(metadata={"column": "V2ENHANCEDPERSONS"})
    organizations: str | None = field(metadata={"column": "V1ORGANIZATIONS"})
    enhanced_organizations: str | None = field(metadata={"column": "V2ENHANCEDORGANIZATIONS"})
    tone: str | None = field(metadata={"column": "V1.5TONE"})
    enhanced_dates: str | None = field(metadata={"column": "V2.1ENHANCEDDATES"})
    gcam: str | None = field(metadata={"column": "V2GCAM"})
    sharing_image: str | None = field(metadata={"column": "V2.1SHARINGIMAGE"})
    related_images: str | None = field(metadata={"column": "V2.1RELATEDIMAGES"})
    social_image_embeds: str | None = field(metadata={"column": "V2.1SOCIALIMAGEEMBEDS"})
    social_video_embeds: str | None = field(metadata={"column": "V2.1SOCIALVIDEOEMBEDS"})
    quotations: str | None = field(metadata={"column": "V2.1QUOTATIONS"})
    all_names: str | None = field(metadata={"column": "V2.1ALLNAMES"})
    amounts: str | None = field(metadata={"column": "V2.1AMOUNTS"})
    translation: str = field(metadata={"column": "V2.1TRANSLATIONINFO"})
    extras_xml: str | None = field(metadata={"column": "V2EXTRASXML"})

    def __post_init__(self) -> None:
        for definition in fields(self):
            value = getattr(self, definition.name)
            if value is None:
                if definition.name in _REQUIRED_FIELDS:
                    raise TypeError(f"{definition.name} must be str")
            else:
                cell(value)

    @classmethod
    def from_mapping(cls, values: Mapping[str, str | None]) -> GKGRecord:
        if set(values) != set(GKG_COLUMNS):
            raise ValueError("Record keys must exactly match GKG_COLUMNS")
        arguments: dict[str, Any] = {
            name: values[column] for column, name in _COLUMN_FIELDS.items()
        }
        return cls(**arguments)

    def to_mapping(self) -> dict[str, str | None]:
        return {column: getattr(self, name) for column, name in _COLUMN_FIELDS.items()}

    def to_row(self, *, allow_incomplete: bool = False) -> tuple[str, ...]:
        return mapping_row(self, allow_incomplete=allow_incomplete)

    def __getitem__(self, key: str) -> str | None:
        return getattr(self, _COLUMN_FIELDS[key])

    def __iter__(self) -> Iterator[str]:
        return iter(GKG_COLUMNS)

    def __len__(self) -> int:
        return len(GKG_COLUMNS)


_COLUMN_FIELDS = {f.metadata["column"]: f.name for f in fields(GKGRecord)}
GKG_COLUMNS: list[str] = list(_COLUMN_FIELDS)
"""GKG column names in serialization order, also exported by `gdelt_regkg.utils`."""

FIELD_NAMES: tuple[str, ...] = tuple(_COLUMN_FIELDS.values())
_REQUIRED_FIELDS = frozenset(
    ("recordid", "date", "source_collection", "source", "document", "translation")
)


def mapping_row(
    record: Mapping[str, str | None], *, allow_incomplete: bool = False
) -> tuple[str, ...]:
    if set(record) != set(GKG_COLUMNS):
        raise ValueError("Record keys must exactly match GKG_COLUMNS")
    cells = []
    for column in GKG_COLUMNS:
        value = record[column]
        if value is None:
            if not allow_incomplete:
                raise ValueError(
                    f"{column} is unavailable; use allow_incomplete=True for a scaffold export"
                )
            value = ""
        cells.append(cell(value))
    return tuple(cells)
