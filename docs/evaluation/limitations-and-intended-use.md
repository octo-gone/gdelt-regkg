# Limitations and intended use

`gdelt-regkg` produces GKG-compatible records from prepared article text and supplied metadata. This is an independent implementation, unaffiliated with and not endorsed by the GDELT Project. Library approximates GDELT's processing and do not recover GDELT's production dictionaries and models.

## Input affects output

Input content, body extraction, normalization and translation also affect the quality of extraction, that is why library approximation of GDELT pipeline could differ. Article's body where retrieved from this output, however text can contain publisher updates/revisions, vary from the body originally processed by GDELT or simply be unavailable.

For example, during development articles from 2018–2025 were analyzed. Yet, only 29.98% of attempted URLs were retained. Using subset of this articles, where title of it matches and body word-count is within 10%, agreement between library and native outputs had risen. This demonstrates sensitivity to article selection.

## Dictionary and language coverage

Library shows high coverage of GCAM counts and values, but it does not measure whether their occurrences or numeric values are reconstructed correctly.

Main extraction pipeline is driven by English texts. Translated-article agreement combines retrieval, translation and extraction differences and does not independently measure translation quality. See [Translation](../guides/translation.md).

## Field-specific limits

- Counts can miss quantities or attach different objects and locations. Amount-object and quotation agreement is low.
- Theme labels or dictionaries outside a profile's cannot be recovered by that profile.
- The default geographic lookup contains places observed in 20 reference archives from 2015–2019. Recognized names absent from that reference can be unresolved and omitted from geography.
- Metadata formatting and supplied media inputs have no extraction-accuracy score.
- Translation details and enhanced offsets quality are also unevaluated there.

Consult the [GKG field reference](../reference/fields/README.md) for each field's behavior and limitations.

## Using reconstructed records

As a recommendation, record the resource profiles, model, policy, language handling and input-text preparation used for an analysis. When combining datasets, it is recommended to label which records came from GDELT and which were reconstructed by this library. Review the [dictionary source terms](../reference/dictionaries.md#third-party-terms) for the intended use. Code, original rules, third-party dictionaries, models and article bodies have distinct licensing terms.
