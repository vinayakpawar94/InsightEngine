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

**Phases 1–10 complete** (Foundation, Core Domain Models, Data Engine —
pandas backend only, Metadata Engine — native YAML only, Rule Engine,
Validation Execution, Cleaning Engine, Execution Pipeline, Reporting
Engine, Plugin System hardening). See the project's implementation
roadmap for what's built and what's next.

**Known, explicitly deferred (not forgotten):** `RankRule` execution
has been deferred three times now (Phases 6, 8, 9) without a decision.
Also: rule types (`rules/dsl.py`) and cleaning transformers
(`cleaning/*`) are **not** plugin-discoverable — only
`MetadataParser`/`DataBackend`/`ReportGenerator` are, since those three
were already structural protocols; making rule types or transformers
pluggable would mean reopening frozen Phase 5/7 dispatch logic, which
Phase 10 deliberately did not do. See `execution/hooks.py` for the
`on_case` scope limitation from Phase 8.

## Requirements

- Python 3.13+
- This project's automated tests were run and verified against Python
  3.12.3, since 3.13 was not available in the build environment. Nothing
  in the codebase uses a 3.13-only language feature, but re-running the
  test suite on an actual 3.13 interpreter before relying on any phase is
  recommended, not assumed.
- `tests/unit/test_plugin_discovery_integration.py` does a real
  `pip install`/`uninstall` of a local test-only package
  (`tests/fixtures/dummy_plugin_package`) as part of the test run — no
  network access required (it's a local, dependency-free editable
  install), but this does mean that one test file takes noticeably
  longer (~20s) than the rest of the suite combined, and briefly mutates
  the environment's installed packages (with guaranteed cleanup, even on
  failure, via a `finally` block).

## Development setup

```bash
pip install -e ".[dev]"
pytest
mypy src/insightengine --strict
```

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
│   └── dsl.py                 # Rule dataclasses + YAML rule parser (not plugin-discoverable — see Status above)
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
└── plugins/            # generic entry_points-based plugin registry primitive (Phase 1)
tests/
├── unit/                  # unit tests, one file per source module
└── fixtures/
    └── dummy_plugin_package/   # a real, separate, installable package - proves Phase 10's
                                   # acceptance criterion with genuine pip install, not mocking
```
