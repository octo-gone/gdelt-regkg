# Social image embeds

`V2.1SOCIALIMAGEEMBEDS` stores supplied social-post URLs containing images. `format_social_image_embeds` formats the collection as one GKG cell.

## Requirements

Core package and caller-supplied metadata; no article retrieval or NLP model is required.

## Example

```python
from gdelt_regkg.fields.metadata import format_social_image_embeds

urls = ["https://example.org/posts/photo"]

print(format_social_image_embeds(urls))
assert format_social_image_embeds([]) == ""
assert format_social_image_embeds(None) is None
```

```text
https://example.org/posts/photo
```

## Behavior

Supply a collection of absolute HTTP(S) URLs without whitespace. Entries are separated by `;`; order and duplicates are preserved. Literal semicolons inside URLs become `%3B`, and existing percent escapes remain unchanged.

An empty collection means no matching media; `None` means metadata is unavailable. A prejoined string is rejected.

In `RecordMetadata`, pass `social_image_embeds=`. An encoded `overrides["V2.1SOCIALIMAGEEMBEDS"]` override takes precedence.

## Limitations

Identify posts containing images before formatting. Resolve relative URLs yourself; the library does not retrieve pages or verify their media content.

## Related

[Sharing image](sharing-image.md) · [API usage](../../guides/records.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)

[Field index](README.md) · [Python API](../python-api.md)
