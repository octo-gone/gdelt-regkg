# Record ID

`GKGRECORDID` identifies a row. `format_record_id` combines a supplied UTC batch timestamp with a positive sequence number and an optional translation marker.

## Example

```python
from gdelt_regkg.fields import format_record_id

print(format_record_id("20250101120000", 1))
print(format_record_id("20250101120000", 2, translated=True))
```

```text
20250101120000-1
20250101120000-T2
```

## Behavior

The timestamp uses `YYYYMMDDHHMMSS`. Sequence numbers must be positive integers; the timestamp must be known. `translated=True` inserts `T` before the sequence number.

In `generate_gkg`, use `batch_time=` and `sequence=`. Translation provenance adds the `T` marker automatically. The batch timestamp also fills `V2.1DATE`.

## Limits

Assign sequence numbers so IDs are unique within your dataset. These are locally generated IDs; article text cannot recover the IDs assigned by GDELT.

## Related

[Batch date](date.md) · [Translation information](translation-info.md) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
