# Sharing image

`V2.1SHARINGIMAGE` stores the image URL selected for sharing an article. `format_sharing_image` formats your prepared metadata.

## Example

```python
from gdelt_regkg.fields import format_sharing_image

print(format_sharing_image("https://example.org/images/workshop.jpg"))
assert format_sharing_image("") == ""
assert format_sharing_image(None) is None
```

```text
https://example.org/images/workshop.jpg
```

## Behavior

Supply one absolute HTTP(S) URL without whitespace. `""` means no image was found; `None` means the metadata is unavailable.

In `generate_gkg`, pass `sharing_image=`. An encoded `field_values["V2.1SHARINGIMAGE"]` override takes precedence. `extract_sharing_image` remains an alias for the same metadata formatter.

## Limits

Select the image and resolve relative URLs before formatting. The library does not parse HTML or check that the URL points to an accessible image.

## Related

[Related images](related-images.md) · [Shared API usage](../usage.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
