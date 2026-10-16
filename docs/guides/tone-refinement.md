# Refine a tone dictionary

`gdelt-regkg-cli refine-tone` learns candidate dictionary changes from saved article bodies and original GDELT tone scores. It builds a baseline from a General Inquirer source, fits edits on training dates, selects variants on a validation date, and evaluates the frozen choices on a held-out test date.

```shell
gdelt-regkg-cli refine-tone --results articles.jsonl --train-dates 20260922 20260924 20260926 20260928 --validation-date 20261002 --test-date 20261003 --gi-source inqtabs.txt --output tone-revision --check-language
```

Install the package following [Installation](../installation.md). Obtain the General Inquirer input using the [resource source instructions](../reference/dictionaries.md#resource-source-files). Run `gdelt-regkg-cli refine-tone --help` for the argument list, or consult the [CLI reference](../reference/cli.md#refine-tone).

## Input

`--results` accepts one or more plain JSONL files. Each successful article needs `status`, `batch`, `record_id`, `source`, `url`, `text`, `original` and `word_count_ratio`. For example:

```json
{"status":"ok","batch":"20260922120000","record_id":"20260922120000-1","source":"example.org","url":"https://example.org/article","text":"The project is good.","original":{"tone":25,"positive":25,"negative":0,"polarity":25,"activity_density":0,"self_group_density":0,"word_count":4},"word_count_ratio":1.0}
```

`original` contains the seven native tone components; `word_count_ratio` is the local token count divided by the native word count. Supply real scores from the corresponding GKG record. The example illustrates the schema only. Rows whose status is not `ok` are counted as failures and skipped. The metric tables produced by `benchmark` are not article inputs.

Use separate training, validation and test dates. The command excludes duplicate bodies across splits and reserves a subset of publishers for testing. `--check-language` also screens bodies for English. Once test results guide further changes, use a new test sample.

## Output

The output directory contains `lexicon.json`, `training_edits.json`, `split_audit.jsonl`, `report.json` and `test_comparison.csv`. The candidate does not become the default automatically.

Use [build](resources.md) to reproduce existing recipes; use refinement to experiment with a new dictionary and review its held-out evaluation.
