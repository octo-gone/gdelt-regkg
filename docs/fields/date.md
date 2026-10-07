# Batch date

`V2.1DATE` stores the row’s batch timestamp. `format_date` converts a supplied timestamp to the compact UTC representation used by GKG.

## Example

```python
from datetime import datetime, timezone
from gdelt_regkg.fields import format_date

print(format_date(datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)))
print(format_date(None))
```

```text
20250101120000
0
```

## Behavior

Accepts a `datetime`, a fourteen-digit string or integer, or `None`. Calendar dates are validated. Aware datetimes convert to UTC; naive datetimes are treated as UTC. `None` and `0` produce `"0"` for an unknown timestamp.

In `generate_gkg`, `batch_time=` fills this field and the record-ID prefix. Supply an article’s publication timestamp separately through `published_at=`; it is written to `PAGE_PRECISEPUBTIMESTAMP` in extra XML. An explicit extras timestamp takes precedence.

## Limits

The library does not infer GDELT’s ingestion time or round timestamps to a collection schedule. Dates mentioned inside article text belong to `V2.1ENHANCEDDATES`.

## Related

[Record ID](record-id.md) · [Date mentions](enhanced-dates.md) · [Extra XML](extras-xml.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
