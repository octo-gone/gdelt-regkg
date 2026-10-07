# Extra XML

`V2EXTRASXML` stores additional data that has no dedicated GKG column. You can define custom element names and nested structures for your own metadata, annotations or processing results. Common examples include article titles, authors, publication times, links and citations. `format_extras_xml` serializes the supplied data as an XML fragment.

## Example

```python
from gdelt_regkg import format_extras_xml

elements = {
    "PAGE_TITLE": "Music & science workshop",
    "PAGE_AUTHORS": "Alice Smith",
    "PAGE_PRECISEPUBTIMESTAMP": "20250101113000",
    "CUSTOM_DATA": {
        "CATEGORY": "workshop",
        "REVIEW_STATUS": "checked",
    },
}
print(format_extras_xml(elements))
```

```text
<PAGE_TITLE>Music &amp; science workshop</PAGE_TITLE><PAGE_AUTHORS>Alice Smith</PAGE_AUTHORS><PAGE_PRECISEPUBTIMESTAMP>20250101113000</PAGE_PRECISEPUBTIMESTAMP><CUSTOM_DATA><CATEGORY>workshop</CATEGORY><REVIEW_STATUS>checked</REVIEW_STATUS></CUSTOM_DATA>
```

## Behavior

Dictionary keys become element names. The `PAGE_*` names are common conventions; they are not a required or exhaustive set. In the example, `CUSTOM_DATA` and its child elements are defined by the application.

Strings become escaped text, dictionaries create nested blocks, lists/tuples repeat an element and `None` omits it. Scalar values must be strings, so numbers and booleans need conversion to text. Empty strings create empty elements. Insertion order is preserved, with no added root element.

Tabs and line breaks become XML character references so the fragment fits one TSV cell. String values containing markup are escaped; use nested dictionaries for child elements. XML names and characters are validated.

For semicolon-delimited metadata such as `PAGE_LINKS`, supply a joined string; a list would create repeated XML elements. Normalize authors and timestamps before formatting.

In `generate_gkg`, pass `extras=elements`. `extras={}` explicitly produces an empty cell; `extras=None` leaves the field unavailable. `extract_extras_xml` in `gdelt_regkg.fields` preserves `None` and otherwise uses the same formatter.

## Options

### Citations

`citation_elements` builds a citation block from `Citation` objects. The same structure can also be supplied as nested dictionaries.

```python
from gdelt_regkg import Citation, citation_elements, format_extras_xml

elements = citation_elements([
    Citation(authors=("Smith, Alice",), title="Workshop notes", date="2024")
])
print(format_extras_xml(elements))
```

```text
<CITEDREFERENCESLIST><CITATION><AUTHORS><AUTHOR>Alice Smith</AUTHOR></AUTHORS><TITLE>Workshop notes</TITLE><DATE>2024</DATE></CITATION></CITEDREFERENCESLIST>
```

`Citation` accepts authors, title, book title, date, journal, volume, issue, pages, institution, publisher, location and marker. Blank optional values are omitted; simple `Surname, Given` authors are reordered. Reference order and duplicates are retained.

## Limits

No HTML or citation extraction runs. Attributes, namespaces and mixed text/child content are unsupported. The formatter validates XML structure, not the meaning of custom elements.

## Related

[Batch date](date.md) · [Shared API usage](../usage.md) · [Article metadata format](https://blog.gdeltproject.org/new-gkg-2-0-article-metadata-fields/) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
