# Social video embeds

`V2.1SOCIALVIDEOEMBEDS` stores supplied embedded video or social-post URLs. `format_social_video_embeds` formats the collection as one GKG cell.

## Example

```python
from gdelt_regkg.fields import format_social_video_embeds

urls = ['https://example.org/posts/video']
print(format_social_video_embeds(urls))
assert format_social_video_embeds([]) == ""
assert format_social_video_embeds(None) is None
```

```text
https://example.org/posts/video
```

## Behavior

Supply a collection of absolute HTTP(S) URLs without whitespace. Entries are separated by `;`; order and duplicates are preserved. Literal semicolons inside URLs become `%3B`, and existing percent escapes remain unchanged.

An empty collection means no matching media; `None` means metadata is unavailable. A prejoined string is rejected.

In `generate_gkg`, pass `social_video_embeds=`. An encoded `field_values["V2.1SOCIALVIDEOEMBEDS"]` override takes precedence. `extract_social_video_embeds` remains an alias for the same formatter.

## Limits

Identify video embeds and normalize provider URLs before formatting. Resolve relative URLs yourself; the library does not retrieve pages or verify their media content.

## Related

[Sharing image](sharing-image.md) · [Shared API usage](../usage.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
