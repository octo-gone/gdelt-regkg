"""Read external GCAM source formats without executing or extracting archives."""

from __future__ import annotations

import csv
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

from ..fields.gcam_tokens import tokenize_gcam, valid_native_pattern
from ..fields.tone import _normalize
from .gcam_expansion import _archive_files


def source_files(path):
    path = Path(path)
    if path.is_dir() or zipfile.is_zipfile(path) or path.name.endswith((".tar.gz", ".tgz", ".tar")):
        return _archive_files(path)
    return {path.name: path.read_bytes()}


def decode(raw, encoding=None):
    if encoding is not None:
        return raw.decode(encoding)
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def member(files, filename):
    matches = [
        raw
        for name, raw in files.items()
        if name.rsplit("/", 1)[-1].casefold() == filename.casefold()
    ]
    if len(matches) != 1:
        raise ValueError(f"Source requires exactly one {filename}")
    return decode(matches[0])


def pattern(term, language="eng"):
    """Normalize a source term while retaining explicit glob operators."""
    term = _normalize(term).replace("_", " ")
    if "*" not in term and "?" not in term:
        return " ".join(tokenize_gcam(term, language))
    if language != "eng" and valid_native_pattern(term):
        return " ".join(term.split())
    if re.search(r"[^\w'*?\s-]", term):
        raise ValueError(f"Unsupported dictionary pattern: {term!r}")
    term = " ".join(term.split())
    if not re.search(r"\w", term):
        raise ValueError("A dictionary wildcard requires a literal word or stem")
    return term


def read_cat(path, *, encoding=None, language="eng"):
    files = source_files(path)
    cats = [name for name in files if name.lower().endswith(".cat")]
    if len(cats) != 1:
        raise ValueError("A WordStat source requires exactly one .CAT file")
    groups = defaultdict(set)
    stack: list[str] = []
    skipped: list[str] = []
    lines = decode(files[cats[0]], encoding).splitlines()
    next_depths = [-1] * len(lines)
    next_depth = -1
    for index in range(len(lines) - 1, -1, -1):
        next_depths[index] = next_depth
        if lines[index].strip():
            next_depth = len(lines[index]) - len(lines[index].lstrip("\t"))
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        depth = len(line) - len(line.lstrip("\t"))
        text = line.strip()
        entry = re.fullmatch(r"(.+) \(([-+]?\d+(?:\.\d+)?)\)", text)
        # Some CAT editions put a unit weight on a category heading as well as
        # on terms. Indentation of its children distinguishes the two forms.
        weighted_category = entry is not None and next_depths[number - 1] > depth
        if entry and not weighted_category:
            if not stack or float(entry[2]) != 1:
                raise ValueError(f"WordStat line {number} requires a category and unit weight")
            try:
                term = pattern(entry[1], language)
            except ValueError:
                skipped.append(entry[1])
                continue
            if term:
                groups["/".join(stack)].add(term)
        else:
            if weighted_category:
                assert entry is not None
                if float(entry[2]) != 1:
                    raise ValueError(f"WordStat category at line {number} requires unit weight")
                text = entry[1]
            if "(" in text or ")" in text or depth > len(stack):
                raise ValueError(f"Unsupported WordStat category or operator at line {number}")
            stack = stack[:depth] + [text]
    exclusions: set[str] = set()
    for name, raw in files.items():
        if name.lower().endswith(".exc"):
            exclusions.update(
                pattern(line.strip(), language)
                for line in decode(raw, encoding).splitlines()
                if line.strip()
            )
    return groups, sorted(exclusions), sorted(skipped)


def read_liwc(path):
    files = source_files(path)
    candidates = [raw for name, raw in files.items() if name.lower().endswith(".dic")]
    if len(candidates) != 1:
        raise ValueError("A LIWC-format source requires exactly one .dic file")
    names, groups, section = {}, defaultdict(set), 0
    for number, line in enumerate(decode(candidates[0]).splitlines(), 1):
        parts = line.split()
        if not parts:
            continue
        if parts == ["%"]:
            section += 1
            continue
        if section == 1 and len(parts) == 2 and parts[0].isdigit():
            if parts[0] in names:
                raise ValueError("Duplicate LIWC category ID")
            names[parts[0]] = parts[1]
        elif section == 2 and len(parts) >= 2:
            term = pattern(parts[0])
            for code in parts[1:]:
                if code not in names:
                    raise ValueError(f"Unknown LIWC category at line {number}")
                if term:
                    groups[names[code]].add(term)
        else:
            raise ValueError(f"Unsupported LIWC source line {number}")
    if section != 2 or not groups:
        raise ValueError("Expected LIWC category and vocabulary sections delimited by %")
    return groups


def read_categories(path):
    """Explicit interchange format for acquired historical dictionaries."""
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict) or not isinstance(payload.get("categories"), dict):
        raise ValueError('Count dictionary JSON requires {"categories": {"category": ["term"]}}')
    groups = {}
    for name, terms in payload["categories"].items():
        if (
            not isinstance(name, str)
            or not isinstance(terms, list)
            or any(not isinstance(t, str) for t in terms)
        ):
            raise ValueError("Dictionary categories require names and arrays of terms")
        groups[name] = {value for term in terms if (value := pattern(term))}
    return groups


def table_rows(path):
    """Read a named-column CSV/TSV, retaining original column names."""
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    if not lines:
        raise ValueError("Dictionary table is empty")
    delimiter = "\t" if "\t" in lines[0] else ","
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError("Dictionary table requires unique named columns")
    rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("Dictionary rows must have the same column count as the header")
    return rows


def xlsx_rows(path, sheet_name):
    """Read literal XLSX cells; spreadsheet formulas are never evaluated."""
    main = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    with zipfile.ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            strings = [
                "".join(node.itertext())
                for node in ET.fromstring(archive.read("xl/sharedStrings.xml"))
            ]
        sheets = ET.fromstring(archive.read("xl/workbook.xml")).find(f"{{{main}}}sheets")
        if sheets is None:
            raise ValueError("Workbook is missing sheets")
        matches = [node for node in sheets if node.attrib["name"] == sheet_name]
        if len(matches) != 1:
            raise ValueError(f"Workbook requires sheet {sheet_name!r}")
        relationships = {
            node.attrib["Id"]: node.attrib["Target"]
            for node in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        }
        target = relationships[matches[0].attrib[f"{{{rel}}}id"]]
        target = target.lstrip("/") if target.startswith("/") else "xl/" + target
        rows = []
        for row in ET.fromstring(archive.read(target)).iter(f"{{{main}}}row"):
            values = {}
            for cell in row:
                if cell.find(f"{{{main}}}f") is not None:
                    raise ValueError(
                        "Dictionary workbooks must contain literal values, not formulas"
                    )
                value = cell.find(f"{{{main}}}v")
                text = "" if value is None or value.text is None else value.text
                if cell.attrib.get("t") == "s":
                    text = strings[int(text)]
                elif cell.attrib.get("t") == "inlineStr":
                    text = "".join(cell.itertext())
                values[re.sub(r"\d", "", cell.attrib["r"])] = text
            rows.append(values)
        return rows
