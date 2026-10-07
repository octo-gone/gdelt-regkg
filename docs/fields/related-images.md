# Related images

`V2.1RELATEDIMAGES` stores supplied article-image URLs. `format_related_images` formats the collection as one GKG cell.

## Example

```python
from gdelt_regkg.fields import format_related_images

urls = ['https://example.org/images/one.jpg', 'https://example.org/images/two.jpg']
print(format_related_images(urls))
assert format_related_images([]) == ""
assert format_related_images(None) is None
```

```text
https://example.org/images/one.jpg;https://example.org/images/two.jpg
```

## Behavior

Supply a collection of absolute HTTP(S) URLs without whitespace. Entries are separated by `;`; order and duplicates are preserved. Literal semicolons inside URLs become `%3B`, and existing percent escapes remain unchanged.

An empty collection means no matching media; `None` means metadata is unavailable. A prejoined string is rejected.

In `generate_gkg`, pass `related_images=`. An encoded `field_values["V2.1RELATEDIMAGES"]` override takes precedence. `extract_related_images` remains an alias for the same formatter.

## Limits

Select images relevant to the article before formatting. Resolve relative URLs yourself; the library does not retrieve pages or verify their media content.

## Related

[Sharing image](sharing-image.md) · [Shared API usage](../usage.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
