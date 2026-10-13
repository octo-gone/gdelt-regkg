"""Metadata, theme/entity, media and supplied-provenance evaluation."""

import re
from datetime import datetime

from . import parsers
from .common import add_mentions, add_sets

METADATA_LABELS = {
    "recordid": "Record ID",
    "date": "Date",
    "source_collection": "Source collection",
    "source": "Source name",
    "document": "Document identifier",
}


def valid_metadata(name, value):
    if any(c in value for c in "\t\r\n"):
        return False
    try:
        if name == "recordid":
            match = re.fullmatch(r"([0-9]{14})-(?:T)?([1-9][0-9]*)", value)
            if match is None:
                return False
            datetime.strptime(match[1], "%Y%m%d%H%M%S")
        elif name == "date":
            if value != "0":
                if not re.fullmatch(r"[0-9]{14}", value):
                    return False
                datetime.strptime(value, "%Y%m%d%H%M%S")
        elif name == "source_collection":
            return value in {"1", "2", "3", "4", "5", "6"}
        else:
            return bool(value.strip())
    except ValueError:
        return False
    return True


def validity(context, name, label, validator):
    values = [prediction.get(name) for _, prediction in context.pairs]
    available = [value for value in values if value is not None]
    valid = sum(validator(value) for value in available)
    context.add(
        label,
        "validity",
        {
            "validity_rate": valid / len(available) if available else None,
            "valid_values": valid,
            "invalid_values": len(available) - valid,
            "unavailable_values": len(values) - len(available),
        },
        len(available),
    )


def metadata(context, name):
    validity(context, name, METADATA_LABELS[name], lambda value: valid_metadata(name, value))


def categorical(context, name):
    is_theme = name == "themes"
    label = "Themes" if is_theme else name.replace("_", " ").title()
    rows = context.parsed(name, parsers.labels if is_theme else parsers.names)
    if not is_theme:
        add_sets(context, label, "raw identities", rows, agreement=True)
        rows = [
            ({parsers.normalize(v) for v in a}, {parsers.normalize(v) for v in b}) for a, b in rows
        ]
    add_sets(
        context,
        label,
        "all labels" if is_theme else "normalized identities",
        rows,
        agreement=True,
        macro=is_theme,
    )
    if is_theme and context.options.theme_labels is not None:
        supported = context.options.theme_labels
        add_sets(
            context,
            label,
            "supported labels",
            [(a & supported, b & supported) for a, b in rows],
            macro=True,
        )
        reference = sum(len(a) for a, b in rows)
        context.add(
            label,
            "supported-label coverage",
            {
                "reference_coverage": sum(len(a & supported) for a, b in rows) / reference
                if reference
                else None,
                "supported_labels": len(supported),
            },
            len(rows),
        )


def enhanced(context, name):
    themes = name == "enhanced_themes"
    rows = context.parsed(name, lambda value: parsers.mentions(value, themes=themes))
    label = "All names" if name == "all_names" else name.replace("_", " ").title()
    if name == "all_names":
        add_sets(
            context,
            label,
            "identities",
            [({m.identity for m in a}, {m.identity for m in b}) for a, b in rows],
        )
    add_mentions(context, label, "mentions", rows, lambda item: item.identity)


def media(context, name):
    label = name.replace("_", " ").title()
    parser = parsers.media_url if name == "sharing_image" else parsers.media

    def valid(value):
        try:
            parser(value)
            return True
        except ValueError:
            return False

    validity(context, name, label, valid)
    rows = context.parsed(name, parser)
    if name == "sharing_image":
        context.add(
            label,
            "URL agreement",
            {"exact_agreement": sum(a == b for a, b in rows) / len(rows) if rows else None},
            len(rows),
        )
    else:
        add_sets(context, label, "URL sets", rows, agreement=True)


def translation(context, _name):
    def valid(value):
        try:
            parsers.translation(value)
            return True
        except ValueError:
            return False

    validity(context, "translation", "Translation information", valid)
    rows = context.parsed("translation", parsers.translation)
    context.add(
        "Translation information",
        "source language",
        {
            "exact_agreement": sum(a == b for a, b in rows) / len(rows) if rows else None,
            "presence_agreement": sum(bool(a) == bool(b) for a, b in rows) / len(rows)
            if rows
            else None,
        },
        len(rows),
    )


def extras(context, _name):
    def valid(value):
        try:
            parsers.xml(value)
            return True
        except ValueError:
            return False

    validity(context, "extras_xml", "Extra XML", valid)
    rows = context.parsed("extras_xml", parsers.xml)
    context.add(
        "Extra XML",
        "canonical structure",
        {"exact_agreement": sum(a == b for a, b in rows) / len(rows) if rows else None},
        len(rows),
    )
