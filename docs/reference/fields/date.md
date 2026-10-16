# Batch date

`V2.1DATE` stores the row’s batch timestamp. `format_date` converts a supplied timestamp to the compact UTC representation used by GKG.

## Requirements

Core package and caller-supplied metadata; no article retrieval or NLP model is required.

## Example

```python
from gdelt_regkg.fields.metadata import format_date
from datetime import datetime, timezone

print(format_date(datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)))
print(format_date(None))
```

```text
20250101120000
0
```

## Behavior

Accepts a `datetime`, a fourteen-digit string or integer, or `None`. Calendar dates are validated. Aware datetimes convert to UTC; naive datetimes are treated as UTC. `None` and `0` produce `"0"` for an unknown timestamp.

Set `batch_time=` on `RecordMetadata` to fill this field and the record-ID prefix, then pass the metadata to `generate_gkg(text, metadata, resources)`. Set the article’s publication timestamp separately with `RecordMetadata(..., published_at=...)`; it is written to `PAGE_PRECISEPUBTIMESTAMP` in extra XML. An explicit extras timestamp takes precedence.

## Limitations

The library does not infer GDELT’s ingestion time or round timestamps to a collection schedule. Dates mentioned inside article text belong to `V2.1ENHANCEDDATES`.

## Related

[Record ID](record-id.md) · [Date mentions](enhanced-dates.md) · [Extra XML](extras-xml.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)

[Field index](README.md) · [Python API](../python-api.md)
