# Limitations and intended use

`gdelt-regkg` produces GKG-compatible records from prepared article text and supplied metadata. This is an independent implementation, unaffiliated with and not endorsed by the GDELT Project. The library approximates GDELT's processing without recovering its production dictionaries and models.

## Input affects output

Input content, body extraction, normalization and translation affect agreement. Articles retrieved through archived URLs may have changed since GDELT processed them, and some pages are unavailable or yield incorrect bodies.

For example, the [paper](https://arxiv.org/html/2610.35358v1) retains 33.53% of attempted English URLs from 2020–2025 after all exclusions and the earlier development benchmark retains 29.98% from 2018–2025. And there is a visible raise in agreement in articles subsets with mathcing title and body length (in comparison to GDELT).

However similar titles and lengths do not establish identical bodies, so these comparisons cannot completely separate input differences from extraction differences. As instance, the length filter shares token counts with tone, so it also favors tone agreement mechanically.

## Dictionary and language coverage

Dictionary coverage measures which categories can be represented, but it does not measure whether their occurrences or numeric values are reconstructed correctly.

Main extraction pipeline is driven by English texts. Translated-article agreement combines retrieval, translation and extraction differences and does not independently measure translation quality. See [Translation](../guides/translation.md).

## Field-specific limits

- Counts can miss quantities or attach different objects and locations. Amount-object and quotation agreement is low.
- Theme labels or dictionaries outside a profile's cannot be recovered by that profile.
- The default geographic lookup contains places observed in 20 reference archives from 2015–2019. Recognized names absent from that reference can be unresolved and omitted from geography.
- Metadata formatting and supplied media inputs have no extraction-accuracy score.
- Translation-information accuracy is not evaluated in the study; enhanced-offset results are not summarized here.

Consult the [GKG field reference](../reference/fields/README.md) for each field's behavior and limitations.

## Using reconstructed records

As a recommendation, record the resource profiles, model, policy, language handling and input-text preparation used for an analysis. When combining datasets, it is recommended to label which records came from GDELT and which were reconstructed by this library. Review the [dictionary source terms](../reference/dictionaries.md#third-party-terms) for the intended use. Code, original rules, third-party dictionaries, models and article bodies have distinct licensing terms.
