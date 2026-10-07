# Document identifier

`V2DOCUMENTIDENTIFIER` stores a supplied URL, DOI or citation identifier. `document_identifier` preserves that string.

## Example

```python
from gdelt_regkg.fields import document_identifier

print(document_identifier("https://example.org/workshop"))
```

```text
https://example.org/workshop
```

## Behavior

Identifiers must be nonempty strings without tabs or line breaks. The formatter preserves spelling, query parameters and percent escapes.

In `generate_gkg`, pass `identifier=`. A web identifier can also supply the source hostname when `source_name=` is omitted.

## Limits

The formatter does not fetch documents, canonicalize URLs, remove tracking parameters or validate DOI/citation syntax.

## Related

[Source name](source-name.md) · [Shared API usage](../usage.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
