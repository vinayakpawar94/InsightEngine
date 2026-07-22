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

**Phases 1–11 complete** (Foundation, Core Domain Models, Data Engine —
pandas backend only, Metadata Engine — native YAML only, Rule Engine,
Validation Execution, Cleaning Engine, Execution Pipeline, Reporting
Engine, Plugin System hardening, CLI). See the project's implementation
roadmap for what's built and what's next.

**Known, explicitly deferred (not forgotten):** `RankRule` execution
has been deferred three times now (Phases 6, 8, 9) without a decision.
Rule types and cleaning transformers are not plugin-discoverable (Phase
10). **A real architectural gap surfaced by Phase 11's integration
testing:** there is no type-coercion step anywhere in the pipeline — CSV
values are always strings (a deliberate Phase 3 decision), so a
`NumericQuestion`/numeric-comparison rule against CSV-sourced data will
always produce either a domain-check error or a `RuleEvaluationError`.
This isn't a bug in any one phase; it's a real, currently-unaddressed
gap between the Data Engine and the Metadata/Rule Engines worth a
deliberate decision (likely a Cleaning Engine transformer) rather than
continuing to work around it project-by-project.

**A note on this phase's own history:** a sandbox environment/filesystem
reset occurred mid-Phase-11, wiping all installed packages and every
project file except the one being actively written at that moment.
Recovered by restoring the full Phases 1–10 project from the
Phase 10 delivery zip (already handed off) rather than reconstructing
by hand — verified byte-for-byte equivalent to the pre-reset state via
the full test suite before Phase 11 work resumed.

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
└── plugins/            # generic entry_points-based plugin registry primitive (Phase 1)
tests/
├── unit/                  # unit tests, one file per source module
└── fixtures/
    └── dummy_plugin_package/   # a real, separate, installable package - proves Phase 10's
                                   # acceptance criterion with genuine pip install, not mocking
```
