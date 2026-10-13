# Command-line interface

Run `gdelt-regkg-cli` or `python -m gdelt_regkg` after [installation](../installation.md).
From a source checkout, prefix commands with `uv run`.

| Command | Guide |
| --- | --- |
| `gdelt-regkg-cli build` | [Build resources](build.md): targets, recipes, inputs, GCAM expansion and geographic references |
| `gdelt-regkg-cli benchmark` | [Benchmark](benchmark.md): input files and directories, field selection, metrics and reports |

```shell
gdelt-regkg-cli --help
gdelt-regkg-cli build --help
gdelt-regkg-cli benchmark --help
```

[Tone refinement](refine-tone.md) fits and evaluates candidate tone dictionaries on separate training, validation and test articles.
For extraction from Python, see [API usage](../api-usage.md).
