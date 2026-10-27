# Build gazetteers

A [gazetteer](../get-started/concepts-and-glossary.md#gazetteer) is an offline lookup of place names, country and administrative codes, coordinates and feature identifiers. The library builds this lookup from enhanced location cells in Global Knowledge Graph (GKG) archives. During extraction, a recognizer identifies place mentions and the gazetteer resolves them to geographic entries.

Gazetteer construction reads reference records. It does not retrieve articles or run a NER model. Install the extraction model separately using [Installation and setup](../get-started/installation-and-setup.md#english-models). See [Locations](../reference/fields/locations.md) for resolution behavior and field encoding.

## Build the default reference

The recorded (default) geographic recipe uses 20 GKG archives from 2015–2019 to build the 17,177-entry comparison inventory.

```shell
gdelt-regkg-cli build locations --sources-dir downloads/resources --download-sources --output local-resources
```

This downloads the recorded reference ZIPs into `downloads/resources/`, verifies their hashes, builds `lexicons/locations.v1.json.gz` and selects it in `local-resources/defaults.json`. The exact filenames and HTTP URLs are recorded in [recipes.json](https://github.com/octo-gone/gdelt-regkg/blob/master/src/gdelt_regkg/resources/recipes.json).

For manual acquisition or an offline build, place those same files in `--sources-dir` and omit `--download-sources`. A build with `all` also includes this geographic target.

### Coverage of the reference

The lookup contains only places observed in its input archives. The dates reproduce a particular study configuration. Geographic lookup construction does not require archives of that age.

The default reference can miss newer names, administrative changes and less-covered regions. A recognized place without a lookup match is omitted from the geographic fields. See [Locations](../reference/fields/locations.md#unresolved-mentions) for diagnostics, access to raw recognized spans and the effect on count geography.

Choose newer or more varied reference inputs when appropriate for the intended analysis. More archives can expand the lookup, but do not guarantee coverage of every place or closer extraction agreement. Keep geographic reference inputs separate from held-out benchmark articles. See [Locations](../reference/fields/locations.md#limitations) for field-specific limits.

## Build from selected archives

Pass one or more reference GKG ZIP files explicitly:

```shell
gdelt-regkg-cli build locations --gazetteer-archives reference/first.gkg.csv.zip reference/second.gkg.csv.zip --gazetteer-name my-places --suffix custom --output local-resources
```

Explicit archives replace the recipe's recorded archive list. This command uses the supplied local files without downloading the default references. It writes `lexicons/locations.custom.json.gz` and updates the geographic selection in `defaults.json`. Other resource selections in that directory are preserved.

### Accepted archive contents

Supply ZIP archives containing `.csv` members in the GKG 2.1 layout: 27 tab-separated columns per row. The builder reads the enhanced location entries in column 11, including location type, full name, administrative codes, coordinates and native feature identifiers. The `.csv` suffix does not mean arbitrary comma-separated geographic data is accepted.

Plain CSV inputs and arbitrary geographic ZIP formats are not accepted by `--gazetteer-archives`. To use a lookup prepared through another process, produce a compatible compiled JSON profile and load it using [Select a compiled gazetteer](#select-a-compiled-gazetteer). Its structure is documented in the [gazetteer schema](https://github.com/octo-gone/gdelt-regkg/blob/master/src/gdelt_regkg/resources/schemas/gazetteer.schema.json).

### Names and filenames

`--gazetteer-name` sets the profile's internal name. `--suffix` sets the output filename label. To choose a complete filename instead, use `--gazetteer-filename locations.my-places.json` or a `.json.gz` basename. Use either a complete filename or a suffix in one invocation. Shared naming rules are described in [Build resources](resources.md#label-output-files).

## Select a compiled gazetteer

Record generation selects the directory's geographic profile through `Resources(resources_dir="local-resources")`. Benchmark generation uses `--resources-dir local-resources`. The directory also needs the other resources required by the selected fields.

To load a specific geographic profile explicitly:

```python
from gdelt_regkg import Resources
from gdelt_regkg.fields.locations import Gazetteer

gazetteer = Gazetteer.from_json("local-resources/lexicons/locations.custom.json.gz")
resources = Resources(resources_dir="local-resources", gazetteer=gazetteer)
```

The explicit `gazetteer` overrides the directory selection. The loader accepts compatible `.json` and `.json.gz` profiles. Add the recognizer needed for entity extraction as shown in [Generate records](records.md). Original reference archives are needed for rebuilding, while extraction uses the compiled lookup. See [Build resources](resources.md#resource-selection) for lazy loading, explicit overrides and cached profiles.
