# Date mentions

`V2.1ENHANCEDDATES` stores explicit calendar references found by `extract_enhanced_dates`. Every mention includes an offset. GKG has no separate standard `V1DATES` column; `V2.1DATE` is the batch timestamp.

## Example

```python
from gdelt_regkg import analyze_dates
from gdelt_regkg.fields import extract_enhanced_dates

text = "In 2025, on June 5 and 2024-02-29."
print(extract_enhanced_dates(text))
result = analyze_dates(text)
assert result.mentions[1].year == 0
```

```text
1#0#0#2025#3;4#6#5#0#12;3#2#29#2024#23
```

## Behavior

Entries use `resolution#month#day#year#offset`, separated by `;`. Missing calendar components remain zero; repeated mentions retain separate zero-based offsets.

| Resolution | Calendar reference |
| --- | --- |
| 1 | Year |
| 2 | Month and year |
| 3 | Month, day and year |
| 4 | Month and day without a year |

Supported forms include ISO dates, English month names/abbreviations, ordinal days, month-year expressions, standalone years from 1500–2199 and slash dates with four-digit years. Invalid dates are excluded without extracting their component years. `result.issues` reports invalid or ambiguous numeric references.

The library emits the `#` separators observed in native GKG archives; the original codebook describes commas. The benchmark accepts both.

## Options

`02/03/2025` is skipped by default. `numeric_order="mdy"` interprets it as February 3, while `"dmy"` interprets it as March 2.

```python
from gdelt_regkg.fields import extract_enhanced_dates

print(extract_enhanced_dates("02/03/2025", numeric_order="dmy"))
```

```text
3#3#2#2025#0
```

The generator’s `numeric_date_order=` applies that convention to date extraction and amount exclusions.

## Limits

Relative dates, weekdays alone, bare months, holidays and two-digit years are not resolved. Publication and batch metadata do not fill missing components. Four-digit quantities can be mistaken for years. Offsets refer to the analyzed English body and have not been benchmarked against identical native text.

## Related

[Batch date](date.md) · [Amounts](amounts.md) · [Current agreement](../README.md#agreement-with-gdelt) · [GKG 2.1 format](http://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf)
