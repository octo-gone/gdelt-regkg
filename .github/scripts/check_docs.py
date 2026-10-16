"""Check repository documentation offline using only the Python standard library.

Validates local Markdown links, images, reference links, GitHub file URLs for the
current repository, heading/HTML anchors, Python/JSON example syntax and README
link portability to PyPI. Remote URLs are not fetched and examples are not run.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import tomllib
import unicodedata
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
REFERENCE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s*(.*)$")
INLINE_CODE = re.compile(r"(`+)(?!`)(.*?)\1(?!`)", re.DOTALL)


@dataclass
class Document:
    path: Path
    anchors: set[str] = field(default_factory=set)
    links: list[tuple[int, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def error(self, line: int, message: str) -> None:
        self.errors.append(f"{self.path.as_posix()}:{line}: {message}")


class HTMLLinks(HTMLParser):
    def __init__(self, document: Document):
        super().__init__(convert_charrefs=True)
        self.document = document

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        anchor = attributes.get("id") or (attributes.get("name") if tag == "a" else None)
        if anchor:
            self.document.anchors.add(anchor)
        target = (
            attributes.get("href")
            if tag == "a"
            else attributes.get("src")
            if tag == "img"
            else None
        )
        if target:
            self.document.links.append((self.getpos()[0], target))


def label_key(label: str) -> str:
    return " ".join(html.unescape(label).split()).casefold()


def destination(text: str, start: int) -> tuple[str, int]:
    """Read an angle-bracket or balanced-parenthesis Markdown destination."""
    while start < len(text) and text[start].isspace():
        start += 1
    if start < len(text) and text[start] == "<":
        end = text.find(">", start + 1)
        if end >= 0:
            return html.unescape(text[start + 1 : end]), end + 1
    depth, index = 0, start
    parts: list[str] = []
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            parts.append(text[index + 1])
            index += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            if not depth:
                break
            depth -= 1
        elif char.isspace() and not depth:
            break
        parts.append(char)
        index += 1
    return html.unescape("".join(parts)), index


def markdown_links(text: str, references: dict[str, str], document: Document) -> None:
    """Read inline/image and full, collapsed or shortcut reference links."""
    brackets: list[int] = []
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char == "[":
            brackets.append(index)
        elif char == "]" and brackets:
            start = brackets.pop()
            label = text[start + 1 : index]
            line = text.count("\n", 0, start) + 1
            next_index = index + 1
            if text[next_index : next_index + 1] == "(":
                target, end = destination(text, next_index + 1)
                # An optional quoted title can follow the destination.
                if re.match(r"\s*(?:\"[^\"]*\"|'[^']*'|\([^)]*\))?\s*\)", text[end:]):
                    document.links.append((line, target))
            elif text[next_index : next_index + 1] == "[":
                end = text.find("]", next_index + 1)
                if end >= 0:
                    key = label_key(text[next_index + 1 : end] or label)
                    if key in references:
                        document.links.append((line, references[key]))
                    else:
                        document.error(line, f"undefined link reference [{key}]")
                    index = end
            elif label_key(label) in references:
                document.links.append((line, references[label_key(label)]))
        index += 1


def heading_slug(title: str) -> str:
    """Create GitHub-style slugs for the repository's Markdown headings."""
    title = re.sub(r"!?\[([^\]]+)\]\([^)]*\)", r"\1", title)
    code_spans: list[str] = []

    def protect_code(match: re.Match[str]) -> str:
        code_spans.append(match[2])
        return f"\0{len(code_spans) - 1}\0"

    title = INLINE_CODE.sub(protect_code, title)
    title = re.sub(r"(?<!\w)(_+)(?=\S)(.+?)(?<=\S)\1(?!\w)", r"\2", title)
    for index, code in enumerate(code_spans):
        title = title.replace(f"\0{index}\0", code)
    title = html.unescape(re.sub(r"<[^>]+>", "", title)).lower()
    return "".join(
        char for char in title if char in " -_" or unicodedata.category(char)[0] in "LNM"
    ).replace(" ", "-")


def check_example(document: Document, language: str, code: str, line: int) -> None:
    offset = 0
    try:
        if language == "python":
            compile(code, document.path.as_posix(), "exec")
        elif language == "json":
            json.loads(code)
        elif language == "jsonl":
            for offset, row in enumerate(code.splitlines()):
                if row.strip():
                    json.loads(row)
    except (SyntaxError, json.JSONDecodeError) as error:
        document.error(
            line + offset + (error.lineno or 1), f"invalid {language} example: {error.msg}"
        )


def parse_document(path: Path, text: str) -> Document:
    document = Document(path)
    visible: list[str] = []
    code: list[str] = []
    fence, language, opened = "", "", 0
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        if fence:
            if re.fullmatch(
                r" {0,3}" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line
            ):
                check_example(document, language, "".join(code), opened)
                fence = ""
                code = []
            else:
                code.append(line)
            visible.append("\n")
            continue
        match = FENCE.match(line)
        if match:
            fence, opened = match[1], number
            language = match[2].strip().split()[0] if match[2].strip() else ""
            visible.append("\n")
        else:
            visible.append("\n" if line.startswith(("    ", "\t")) else line)
    if fence:
        document.error(opened, "unclosed code fence")

    visible = re.sub(
        r"<!--.*?-->",
        lambda match: re.sub(r"[^\n]", " ", match[0]),
        "".join(visible),
        flags=re.DOTALL,
    ).splitlines(keepends=True)

    references: dict[str, str] = {}
    for index, line in enumerate(visible):
        match = REFERENCE.match(line)
        if match:
            target, _ = destination(match[2], 0)
            references[label_key(match[1])] = target
            document.links.append((index + 1, target))
            visible[index] = "\n"

    used: set[str] = set()
    for index, line in enumerate(visible):
        atx = re.match(r"^ {0,3}#{1,6}(?:[ \t]+(.*)|\s*$)", line)
        title = re.sub(r"\s+#+\s*$", "", atx[1] or "").strip() if atx else None
        if title is None and index and re.fullmatch(r" {0,3}(?:=+|-+)\s*", line):
            title = visible[index - 1].strip() or None
        if title is not None:
            base = heading_slug(title)
            anchor, suffix = base, 0
            while anchor in used:
                suffix += 1
                anchor = f"{base}-{suffix}"
            used.add(anchor)
            document.anchors.add(anchor)

    masked = INLINE_CODE.sub(lambda match: re.sub(r"[^\n]", " ", match[0]), "".join(visible))
    HTMLLinks(document).feed(masked)
    markdown_links(masked, references, document)
    return document


def markdown_files(root: Path) -> list[Path]:
    files = list(root.glob("*.md"))
    for directory in ("docs", "src", ".github"):
        files.extend((root / directory).rglob("*.md"))
    return sorted(path.relative_to(root) for path in files if path.is_file())


def local_target(root: Path, source: Path, href: str, repository: str) -> tuple[Path, str] | None:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc:
        # Branch file URLs refer to the checkout; historical tags and remote URLs are left alone.
        prefix = f"/{repository}/"
        parts = parsed.path.removeprefix(prefix).split("/", 2)
        if (
            parsed.netloc.lower() != "github.com"
            or not parsed.path.startswith(prefix)
            or len(parts) != 3
            or parts[0] not in ("blob", "tree")
            or parts[1] not in ("main", "master")
        ):
            return None
        path = root / unquote(parts[2])
    else:
        path = root / source.parent / unquote(parsed.path) if parsed.path else root / source
    return path.resolve(), unquote(parsed.fragment).removeprefix("user-content-")


def check_link(
    root: Path,
    document: Document,
    line: int,
    href: str,
    repository: str,
    documents: dict[Path, Document],
) -> None:
    try:
        parsed = urlsplit(href)
        if (
            document.path == Path("README.md")
            and parsed.path
            and not (parsed.scheme or parsed.netloc)
        ):
            document.error(line, f"README link must use an absolute URL for PyPI: {href}")
        target = local_target(root, document.path, href, repository)
        if target is None:
            return
        path, fragment = target
        if not path.is_relative_to(root):
            document.error(line, f"link leaves the repository: {href}")
        elif not path.exists():
            document.error(line, f"missing link target: {href}")
        elif fragment:
            if path.is_dir():
                path /= "README.md"
            relative = path.relative_to(root)
            if path.suffix.lower() == ".md":
                target_document = documents.get(relative)
                if target_document is None:
                    target_document = parse_document(relative, path.read_text(encoding="utf-8"))
                if fragment not in target_document.anchors:
                    document.error(line, f"missing section anchor: {href}")
    except (OSError, UnicodeError, ValueError) as error:
        document.error(line, f"invalid link {href!r}: {error}")


def check_repository(root: Path) -> list[str]:
    root = root.resolve()
    project_file = root / "pyproject.toml"
    try:
        project = tomllib.loads(project_file.read_text(encoding="utf-8"))["project"]
        urls = project["urls"]
        repository = urlsplit(urls["Repository"]).path.strip("/").removesuffix(".git")
    except (OSError, UnicodeError, ValueError, KeyError) as error:
        return [f"pyproject.toml: cannot read project documentation URLs: {error}"]

    documents: dict[Path, Document] = {}
    errors: list[str] = []
    for relative in markdown_files(root):
        try:
            documents[relative] = parse_document(
                relative, (root / relative).read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            errors.append(f"{relative.as_posix()}: cannot read UTF-8 Markdown: {error}")
    for document in documents.values():
        for line, href in document.links:
            check_link(root, document, line, href, repository, documents)
        errors.extend(document.errors)
    metadata = Document(Path("pyproject.toml"))
    for name in ("Documentation", "Changelog"):
        if name not in urls:
            metadata.error(1, f"missing project URL: {name}")
        else:
            check_link(root, metadata, 1, urls[name], repository, documents)
    return errors + metadata.errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    errors = check_repository(args.root)
    if errors:
        print("\n".join(errors))
        return 1
    print("Documentation links, anchors, example syntax and PyPI links passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
