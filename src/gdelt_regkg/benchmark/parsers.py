"""Strict field parsers; empty cells are valid empty results, not missing data."""

import calendar
import math
import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from xml.etree import ElementTree


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC", value).casefold().replace("\u2019", "'").split())


def blocks(value, separator=";"):
    return [part for part in value.split(separator) if part]


def integer(value):
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError("Expected a nonnegative integer")
    return int(value)


def finite(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Expected a finite number")
    return number


def decimal(value):
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Invalid numeric quantity") from error
    if not result.is_finite():
        raise ValueError("Expected a finite numeric quantity")
    return result


def labels(cell):
    result = set(blocks(cell))
    if any(not re.fullmatch(r"[A-Z][A-Z0-9_-]*", value) for value in result):
        raise ValueError("Invalid theme label")
    return result


def names(cell):
    return set(blocks(cell))


@dataclass(frozen=True)
class Mention:
    identity: object
    offset: int


def mentions(cell, *, themes=False):
    result = []
    for part in blocks(cell):
        name, offset = part.rsplit(",", 1)
        if not name.strip():
            raise ValueError("Mention name is empty")
        if themes and not re.fullmatch(r"[A-Z][A-Z0-9_-]*", name):
            raise ValueError("Invalid theme label")
        result.append(Mention(name if themes else normalize(name), integer(offset)))
    return result


@dataclass(frozen=True)
class Count:
    label: str
    quantity: Decimal
    object: str
    geography: tuple[str, ...]
    offset: int | None = None


def counts(cell, *, enhanced=False):
    result = []
    for part in blocks(cell):
        values = part.split("#")
        if len(values) != (11 if enhanced else 10):
            raise ValueError("Invalid count tuple width")
        if not re.fullmatch(r"[A-Z][A-Z0-9_-]*", values[0]):
            raise ValueError("Invalid count label")
        quantity = decimal(values[1])
        if quantity < 0 or quantity != quantity.to_integral_value():
            raise ValueError("Count quantities must be nonnegative integers")
        if values[3] not in {"", "0", "1", "2", "3", "4", "5"}:
            raise ValueError("Invalid count location type")
        result.append(
            Count(
                values[0],
                quantity,
                normalize(values[2]),
                tuple(values[3:10]),
                integer(values[10]) if enhanced else None,
            )
        )
    return result


@dataclass(frozen=True)
class Location:
    kind: str
    name: str
    country: str
    adm1: str
    adm2: str
    latitude: float | None
    longitude: float | None
    feature: str
    offset: int | None = None

    @property
    def identity(self):
        return self.kind, self.country, self.adm1, self.feature


def locations(cell, *, enhanced=False):
    result = []
    for part in blocks(cell):
        values = part.split("#")
        if len(values) != (9 if enhanced else 7):
            raise ValueError("Invalid location tuple width")
        if enhanced:
            kind, name, country, adm1, adm2, lat, lon, feature, offset = values
        else:
            kind, name, country, adm1, lat, lon, feature = values
            adm2, offset = "", None
        if kind not in {"1", "2", "3", "4", "5"}:
            raise ValueError("Invalid resolved location type")
        latitude, longitude = finite(lat) if lat else None, finite(lon) if lon else None
        if latitude is not None and not -90 <= latitude <= 90:
            raise ValueError("Latitude is outside its valid range")
        if longitude is not None and not -180 <= longitude <= 180:
            raise ValueError("Longitude is outside its valid range")
        result.append(
            Location(
                kind,
                normalize(name),
                country,
                adm1,
                adm2,
                latitude,
                longitude,
                feature,
                integer(offset) if offset is not None else None,
            )
        )
    return result


def dates(cell):
    result = []
    for part in blocks(cell):
        values = re.split("[#,]", part)
        if len(values) != 5:
            raise ValueError("Date requires resolution, month, day, year and offset")
        resolution, month, day, year, offset = map(integer, values)
        if resolution not in {1, 2, 3, 4} or year > 9999:
            raise ValueError("Invalid date resolution or year")
        if resolution == 1:
            valid = month == day == 0 and year > 0
        elif resolution == 2:
            valid = 1 <= month <= 12 and day == 0 and year > 0
        else:
            valid = (
                1 <= month <= 12
                and 1 <= day <= calendar.monthrange(year or 2000, month)[1]
                and ((year == 0) == (resolution == 4))
            )
        if not valid:
            raise ValueError("Invalid calendar date components")
        result.append(Mention((resolution, month, day, year), offset))
    return result


@dataclass(frozen=True)
class Amount:
    quantity: Decimal
    object: str
    offset: int


def amounts(cell):
    result = []
    for part in blocks(cell):
        values = part.split(",")
        if len(values) != 3:
            raise ValueError("Amount requires value, object and offset")
        result.append(Amount(decimal(values[0]), normalize(values[1]), integer(values[2])))
    return result


@dataclass(frozen=True)
class Quote:
    text: str
    verb: str
    length: int
    offset: int


def quotations(cell):
    result = []
    for part in blocks(cell, "#"):
        offset, length, verb, text = part.split("|", 3)
        if not text.strip() or integer(length) == 0:
            raise ValueError("Quotation requires content and positive length")
        result.append(Quote(normalize(text), normalize(verb), integer(length), integer(offset)))
    return result


def tone(cell):
    if not cell:
        return None
    values = tuple(map(finite, cell.split(",")))
    if len(values) != 7 or values[6] < 0 or values[6] != int(values[6]):
        raise ValueError("Tone requires six finite scores and a nonnegative integer word count")
    return values


def gcam(cell):
    result = {}
    for part in blocks(cell, ","):
        key, value = part.split(":", 1)
        if key not in {"wc", "nwc"} and not re.fullmatch(r"[cv][1-9][0-9]*\.[1-9][0-9]*", key):
            raise ValueError("Invalid GCAM key")
        if key in result:
            raise ValueError("Duplicate GCAM key")
        number = finite(value)
        if (key.startswith("c") or key in {"wc", "nwc"}) and number < 0:
            raise ValueError("GCAM counts cannot be negative")
        result[key] = number
    return result


def media_url(value):
    if not value:
        return ""
    parsed = urlsplit(value)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or any(c.isspace() for c in value)
    ):
        raise ValueError("Invalid absolute media URL")
    return parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower()).geturl()


def media(cell):
    return {media_url(value) for value in blocks(cell)}


def translation(cell):
    if not cell:
        return None
    values = dict(part.split(":", 1) for part in blocks(cell))
    if (
        set(values) != {"srclc", "eng"}
        or not re.fullmatch(r"[a-z]{3}", values["srclc"])
        or not values["eng"].strip()
    ):
        raise ValueError("Translation requires source-language (srclc) and engine (eng) values")
    return values["srclc"]


def xml(cell):
    if "<!DOCTYPE" in cell.upper() or "<!ENTITY" in cell.upper():
        raise ValueError("XML entity declarations are unsupported")
    try:
        return ElementTree.canonicalize("<GKG>" + cell + "</GKG>")
    except ElementTree.ParseError as error:
        raise ValueError("Invalid extra XML") from error
