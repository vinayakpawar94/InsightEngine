# InsightEngine

A Python-native survey data processing platform — metadata modeling,
rule-based validation, cleaning, and reporting — designed as an
open-source successor to IBM SPSS Data Collection (Dimensions), without
depending on MDD, DDF, DMS, mrScript, COM automation, or Windows-only
components.

**Project naming (permanent, decided before Phase 2):**
- Project title: **InsightEngine**
- Repository name: **InsightEngine**
- Python package / import name: `insightengine`
- CLI command (reserved for Phase 11, not yet implemented): `insightengine`

## Status

**Phases 1–12 complete** (Foundation, Core Domain Models, Data Engine —
pandas backend only, Metadata Engine — native YAML only, Rule Engine,
Validation Execution, Cleaning Engine, Execution Pipeline, Reporting
Engine, Plugin System hardening, CLI, Legacy migration bridge). See the
project's implementation roadmap for what's built and what's next.

**Known, explicitly deferred (not forgotten):** `RankRule` execution
has been deferred through four phases now (6, 8, 9, 11) without a
decision. Rule types and cleaning transformers are still not
plugin-discoverable (Phase 10). The numeric-type-coercion gap flagged at
the end of Phase 11 (CSV data is always strings; nothing anywhere
coerces it) remains unaddressed.

**Phase 12's verification status — read this before trusting the
migration bridge with anything real:**
- `migration/sav_legacy.py`'s variable/value-label import is genuinely
  tested against real `.sav` files (written and read back with
  `pyreadstat`). This surfaced two real bugs, both fixed: pyreadstat
  returns value-label keys as `float`, not `int`; and pyreadstat sets an
  explicit `None` (not a missing key) for unlabeled variables, which
  broke a naive `dict.get(name, name)` fallback.
- **MRSET (multiple-response set) handling is NOT verified against a
  real Dimensions-produced file, and cannot be in this environment** —
  `pyreadstat.write_sav` has no parameter for writing MRSETs at all, so
  no synthetic round-trip test is possible. It's implemented strictly
  against `pyreadstat`'s own documented `MRSet` TypedDict, tested only
  via a monkeypatched simulation of that shape.
- **A real, unresolved integration gap found while building this:** a
  real `.sav` file's MRSET subvariable names are arbitrary (e.g. `Q8A`,
  `Q8B`), not guaranteed to match the `"{id}_{code}"` convention Phase
  7's `MultiResponseExpansionTransformer` expects. This module builds
  correct *metadata*; wiring the *data* columns through cleaning is not
  solved here.
- `migration/legacy_log.py`'s ErrorLog/QAout2 parser is grounded in real
  evidence — the actual production `_QAedit.dms` template reviewed
  earlier in this project, not a guessed format.
- `migration/shadow_run.py`'s comparator is deliberately scoped to
  aggregate (total/key-overlap) comparison only — there is no shared
  case identifier between legacy (respondent serial) and new-pipeline
  (physical row index) results to support case-level reconciliation.

## Requirements

- Python 3.13+
- This project's automated tests were run and verified against Python
  3.12.3, since 3.13 was not available in the build environment. Nothing
  in the codebase uses a 3.13-only language feature, but re-running the
  test suite on an actual 3.13 interpreter before relying on any phase is
  recommended, not assumed.
- The `[project.scripts]` entry point (`insightengine` console command)
  is wired up and syntactically valid, but has **not** been verified via
  an actual `pip install` + real console-script invocation in this
  environment — that requires Python 3.13, which isn't available here.
  Every command's behavior is instead fully verified via
  `typer.testing.CliRunner` against the CLI's `app` object directly,
  which is what the real console script also calls.
- `tests/unit/test_plugin_discovery_integration.py` does a real
  `pip install`/`uninstall` of a local test-only package as part of the
  test run (Phase 10) — no network access required, but this one test
  file takes noticeably longer (~20s) than the rest of the suite combined.
- A sandbox environment/filesystem reset occurred mid-Phase-11, wiping
  all installed packages and every project file except the one being
  actively written at that moment. Recovered by restoring the full
  Phases 1–10 project from the already-delivered Phase 10 zip rather
  than reconstructing by hand — verified via the full test suite before
  work resumed. Mentioned here in case anything looks slightly
  out-of-sequence in file timestamps.

## Development setup

```bash
pip install -e ".[dev]"
pytest
mypy src/insightengine --strict
```

## CLI usage

```bash
insightengine init my_project
insightengine validate --data DATA --metadata METADATA --rules RULES --run-dir RUN_DIR
insightengine clean --data DATA --metadata METADATA --run-dir RUN_DIR
insightengine report --run-dir RUN_DIR --format html --output report.html
insightengine export --data DATA --metadata METADATA --rules RULES --run-dir RUN_DIR --report-output report.html
```

See `insightengine <command> --help` for full option details. Note:
`clean` always also produces validation results as a side effect of the
shared Orchestrator (Phase 8); there is no "clean only" mode.

## Project layout

```
src/insightengine/
├── core/               # exceptions, enums, config, logging, Codebook/Question domain model
├── data/               # backend-agnostic Data Engine
│   ├── base.py          # RawTable, DataHandle/DataBackend protocols
│   ├── csv_loader.py     # CSV -> RawTable (no type coercion — see module docstring)
│   ├── loader.py          # format sniffing + top-level load_file()
│   ├── registry.py         # DataBackend plugin registry (pre-populated with pandas)
│   └── backends/
│       └── pandas_backend.py   # the only concrete DataBackend so far
├── metadata/            # Metadata Engine
│   ├── base.py            # MetadataParser protocol
│   ├── validators.py        # authoring-quality checks beyond Codebook's own invariants
│   ├── registry.py            # MetadataParser plugin registry (pre-populated with yaml)
│   └── parsers/
│       └── yaml_native.py     # native YAML <-> Codebook, the only parser so far
├── rules/                # Rule Engine
│   ├── evaluator.py         # restricted expression evaluator — security-critical, see its docstring
│   └── dsl.py                 # Rule dataclasses + YAML rule parser (not plugin-discoverable)
├── validation/            # Validation Execution — wires Rule Engine + Codebook to real data
│   ├── context.py            # ValidationContext (Codebook + DataHandle)
│   ├── results.py              # ValidationResult
│   ├── collector.py             # ErrorCollector
│   └── executor.py                # validate() — see its docstring for RankRule deferral, multi-response convention
├── cleaning/              # Cleaning Engine — transformations over RawTable (not plugin-discoverable)
│   ├── transformer.py       # Transformer ABC, TransformerPipeline, DataHandle bridge
│   ├── grid_expansion.py      # grid row column completion
│   ├── multi_expansion.py       # delimited-string / binary-indicator -> canonical selection collection
│   ├── recode.py                  # single-value category recoding
│   └── derived.py                   # derived-variable computation, dependency-ordered
├── execution/              # Execution Pipeline — end-to-end orchestration with resumability
│   ├── manifest.py           # Stage/Manifest model, atomic JSON writes
│   ├── persistence.py          # RawTable / ValidationResult JSON persistence
│   ├── hooks.py                  # on_start/on_case/on_end — see its docstring for on_case's real scope
│   └── orchestrator.py             # Orchestrator — the top-level run() entry point
├── reporting/              # Reporting Engine — ValidationResult -> files
│   ├── models.py             # ReportData / RuleSummary / build_report_data()
│   ├── base.py                 # ReportGenerator protocol
│   ├── registry.py               # ReportGenerator plugin registry (pre-populated with all 4)
│   ├── json_report.py              # summary + full results
│   ├── csv_report.py                 # raw results only, by design — see its module docstring
│   ├── html_report.py                  # self-contained, escaped, no templating dependency
│   └── excel_report.py                   # two sheets: Summary, Details
├── cli/                     # survey init/validate/clean/export/report
│   └── main.py                 # the typer app — see its module docstring for scope decisions
├── migration/                 # Legacy Dimensions migration bridge — see Status above for verification caveats
│   ├── sav_legacy.py            # .sav -> Codebook via pyreadstat
│   ├── legacy_log.py              # ErrorLog/QAout2 parsing, grounded in real production evidence
│   └── shadow_run.py                # aggregate-only legacy-vs-new comparison
└── plugins/            # generic entry_points-based plugin registry primitive (Phase 1)
tests/
├── unit/                  # unit tests, one file per source module
└── fixtures/
    └── dummy_plugin_package/   # a real, separate, installable package - proves Phase 10's
                                   # acceptance criterion with genuine pip install, not mocking
```
