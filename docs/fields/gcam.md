# GCAM

`V2GCAM` stores word count, category counts and weighted mean scores. `extract_gcam` uses locally prepared English dictionaries. The standard profile supports 809 of 2,888 native dimensions (28.01%); optional Roget and Lexicoder imports raise this to 1,855 of 2,888 (64.23%).

## Example

```python
from gdelt_regkg import analyze_gcam

text = "Good good bad."
result = analyze_gcam(text)
print(result.to_gkg())
assert result.word_count == 3
assert result.counts["c26.1"] == 3
```

```text
wc:3,c2.57:3,c2.76:3,c2.78:2,c2.104:3,c2.107:1,c2.116:1,c2.119:2,c2.125:3,c2.127:2,c2.131:2,c2.157:2,c2.186:2,c2.204:2,c2.213:1,c2.214:2,c15.36:2,c15.175:1,c16.56:1,c16.57:3,c16.68:1,c16.94:3,c16.129:3,c17.1:3,c17.4:3,c17.7:2,c17.8:3,c26.1:3,v26.1:0.433333333333333
```

## Behavior

Cells start with `wc:N`, followed by comma-separated `key:value` entries. `c` keys hold category counts; `v` keys hold mean scores. Counts with no matches are omitted. A weighted mean of zero is written when matches exist; a mean without matches is undefined and omitted.

`result.counts` also exposes supported zero-match categories. `result.values` contains defined means, and `result.implemented_dimensions` identifies supported serialized keys. An absent key can mean no matches or an unsupported category, so interpreting exported rows requires their extraction profile.

Coverage pairs a category’s `c` and `v` keys as one dimension and excludes `wc`. The local codebook contains 2,888 such dimensions, represented by 2,989 count/value keys. Coverage measures support, independently of extraction agreement.

| Dictionary | Supported / native dimensions | Availability |
| --- | --- | --- |
| General Inquirer | 217 / 228 | Standard profile |
| Roget | 1,042 / 1,042 | Optional import |
| WordNet Affect | 280 / 280 | Standard profile |
| WordNet Domains | 168 / 168 | Standard profile |
| WordNet lexical categories | 44 / 44 | Standard profile |
| GKG themes | 99 / 368 | Standard profile |
| VADER | 1 / 1 | Standard profile |
| Lexicoder sentiment | 4 / 4 | Optional import |

General Inquirer uses exact normalized token frequencies with categories allowed to overlap. WordNet and Roget use phrases, exceptions and morphology without POS or sense disambiguation. GCAM theme counts reuse theme rules and retain repeated spans. VADER uses its vocabulary scores and whitespace-token matching, without compound-score normalization, negation inversion or emphasis. GCAM remains independent of the tuned tone profile.

## Options

The [broader GCAM setup](../installation.md#broader-gcam-coverage) creates `gcam-full.json`. `GCAMLexicon.from_json` loads this profile for the standalone analyzer’s `lexicon=` argument or the generator’s `gcam_lexicon=` argument.

```python
from gdelt_regkg import GCAMLexicon, analyze_gcam

lexicon = GCAMLexicon.from_json("local-resources/gcam-full.json")
result = analyze_gcam("Good good bad.", lexicon=lexicon)
assert result.word_count == 3
```

The same loader accepts any compatible JSON/gzip profile. External vocabularies retain their [source terms](../installation.md#third-party-terms).

The [GCAM schema](../../src/gdelt_regkg/resources/schemas/gcam-lexicon.schema.json) supports count vocabularies, phrase/wildcard patterns and weighted score maps. Weighted maps automatically supply companion counts. `GCAMLexicon` also accepts a custom vocabulary directly.

```python
from gdelt_regkg import GCAMLexicon, analyze_gcam

lexicon = GCAMLexicon(
    name="example",
    dimensions={"c2.21": frozenset({"hand"})},
)
print(analyze_gcam("hand hand", lexicon=lexicon).to_gkg())
```

```text
wc:2,c2.21:2
```

This illustrative vocabulary does not establish agreement with native category definitions. Duplicate keys, nonfinite scores and conflicting count vocabularies are rejected. Lexicoder JSON imports use `negative`, `positive`, `neg_negative` and `neg_positive` arrays; `*`, `?` and phrases are supported, with longest nonoverlapping matches within each category.

## Limits

### Missing capabilities

- Eleven General Inquirer categories and 269 GCAM theme categories remain unsupported.
- The library does not support LIWC, RID, Moral Foundations or financial sentiment dictionaries.
- Weighted dictionaries such as SentiWordNet, SentiWords and ANEW are not implemented.
- Lexicoder’s punctuation, proper-name, negation and false-hit preprocessing modules are not implemented.
- Native-language dictionaries and `nwc` are not supported. Translated bodies produce English dimensions.
- The implementation does not reproduce GDELT’s exact dictionary revisions, tokenizer or sense disambiguation.

Dimension coverage does not guarantee matching counts. WordNet Affect has weaker measured agreement than several other supported families; see the metrics overview before selecting dimensions for analysis.

## Related

[Installation and setup](../installation.md) · [GCAM agreement](../README.md#gcam) · [Theme matching](themes.md) · [Tone](tone.md) · [Expansion experiments](../../CHANGELOG.md#0110-general-inquirer-expansion)
