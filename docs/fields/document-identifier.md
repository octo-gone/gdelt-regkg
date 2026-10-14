# Document identifier

`V2DOCUMENTIDENTIFIER` stores a supplied URL, DOI or citation identifier. `document_identifier` preserves that string.

## Example

```python
from gdelt_regkg.fields.metadata import document_identifier

print(document_identifier("https://example.org/workshop"))
```

```text
https://example.org/workshop
```

## Behavior

Identifiers must be nonempty strings without tabs or line breaks. The formatter preserves spelling, query parameters and percent escapes.

Set `identifier=` on `RecordMetadata`, then pass the metadata to `generate_gkg(text, metadata, resources)`. A web identifier also supplies the source hostname when the metadata’s `source_name=` is omitted.

## Limits

The formatter does not fetch documents, canonicalize URLs, remove tracking parameters or validate DOI/citation syntax.

## Related

[Source name](source-name.md) · [API usage](../api-usage.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
