# Source name

`V2SOURCECOMMONNAME` records the source label. `source_common_name` uses a supplied label or extracts the hostname from a web URL.

## Requirements

Core package and caller-supplied metadata; no article retrieval or NLP model is required.

## Example

```python
from gdelt_regkg.fields.metadata import source_common_name

print(source_common_name("https://news.example.org/workshop"))
print(source_common_name("citation:123", name="Example Journal"))
```

```text
news.example.org
Example Journal
```

## Behavior

Automatic naming accepts absolute HTTP(S) URLs, lowercases the hostname and retains subdomains. An explicit `name=` is used as supplied.

Set `source_name=` on `RecordMetadata` to override hostname extraction, then pass the metadata to `generate_gkg(text, metadata, resources)`. Supply a label for non-web identifiers. Tabs and line breaks are rejected.

## Limitations

Hostname extraction does not collapse subdomains into a registrable domain. Supply the original source label when reproducing an existing GKG row.

## Related

[Source collection](source-collection.md) · [Document identifier](document-identifier.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)

[Field index](README.md) · [Python API](../python-api.md)
