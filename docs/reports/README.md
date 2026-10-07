# Research reports

Detailed JSON evidence is retained in the repository and excluded from wheel and source distributions. Summary tables and methodology remain in the [documentation overview](../README.md) and [changelog](../../CHANGELOG.md).

| Files | Contents |
| --- | --- |
| `benchmark-results.json` | Seasonal English and Translingual field comparisons, split audits and checksums |
| `benchmark-results-previous.json` | Earlier benchmark retained for historical comparison |
| `extraction-fields-development.json` | Initial locations, dates, amounts, all names and GCAM development check |
| `extraction-fields-benchmark.json` | Reserved English evaluation of locations, dates, amounts, all names and quotations |
| `extraction-fields-benchmark-translated.json` | The same fields on saved translated English bodies |
| `extraction-fields-benchmark-audit.json` | Split checks, frozen extractor/resource hashes and model configuration |
| `resource-migration.json` | Exact profile and output parity after moving external resources out of the package |
| `gcam-{development,benchmark}.json` | Original General Inquirer subset and VADER evaluation |
| `lexicoder-{development,benchmark}.json` | Optional Lexicoder evaluation |
| `gcam-expansion-results.json` | Aggregate expansion results, coverage and correction comparison |
| `gcam-expansion-split-audit.json` | URL and body overlap checks |
| `gcam-expansion-N-{development,benchmark}.json` | Category-level reports for stages 0–7 |
| `gcam-affect-*-development.json` | Development comparisons of Affect matching policies |
| `*-initial-*.json` | Measurements before the WordNet adjective-format correction |

Stages are 0 baseline, 1 General Inquirer, 2 Roget, 3 lexical categories, 4 Affect, 5 Domains, 6 GCAM themes and 7 the packaged default. Initial reports preserve the evidence before benchmark replay; they are historical results, not additional independent samples.

Report contents are unchanged. Historical paths inside JSON identify the files used at evaluation time; the sample plan has since moved to the tools directory.

The reusable [sample plan](../../scripts/benchmark-plan.json) ships with the maintained tools. These reports are evaluation outputs, not extraction resources. External extraction dictionaries are [prepared locally](../installation.md); authored rules and schemas remain in `gdelt_regkg.resources`.
