# Source collection

`V2SOURCECOLLECTIONIDENTIFIER` records the type of source collection. `format_source_collection` validates the supplied integer code.

## Requirements

Core package and caller-supplied metadata; no article retrieval or NLP model is required.

## Example

```python
from gdelt_regkg.fields.metadata import format_source_collection

print(format_source_collection(1))
```

```text
1
```

## Behavior

| Code | Collection |
| --- | --- |
| 1 | Web |
| 2 | Citation |
| 3 | CORE |
| 4 | DTIC |
| 5 | JSTOR |
| 6 | Nontextual source |

Set `source_collection=` on `RecordMetadata`, then pass the metadata to `generate_gkg(text, metadata, resources)`. The default collection is `1`. Values outside 1–6 and boolean values are rejected.

## Limitations

Select the collection using your source metadata. The formatter does not classify documents or check collection-specific identifier syntax.

## Related

[Source name](source-name.md) · [Document identifier](document-identifier.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)

[Field index](README.md)
