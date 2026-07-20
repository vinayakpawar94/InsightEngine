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

**Phases 1–9 complete** (Foundation, Core Domain Models, Data Engine —
pandas backend only, Metadata Engine — native YAML only, Rule Engine,
Validation Execution, Cleaning Engine, Execution Pipeline, Reporting
Engine). See the project's implementation roadmap for what's built and
what's next.

**Known, explicitly deferred (not forgotten):** `RankRule` execution
has been deferred twice now (Phases 6 and 8) and still isn't built.
Worth a real decision before it drifts further.

## Requirements

- Python 3.13+
- This project's automated tests were run and verified against Python
  3.12.3, since 3.13 was not available in the build environment. Nothing
  in the codebase uses a 3.13-only language feature, but re-running the
  test suite on an actual 3.13 interpreter before relying on any phase is
  recommended, not assumed.

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
│   └── backends/
│       └── pandas_backend.py   # the only concrete DataBackend so far
├── metadata/            # Metadata Engine
│   ├── base.py            # MetadataParser protocol
│   ├── validators.py        # authoring-quality checks beyond Codebook's own invariants
│   └── parsers/
│       └── yaml_native.py     # native YAML <-> Codebook, the only parser so far
├── rules/                # Rule Engine
│   ├── evaluator.py         # restricted expression evaluator — security-critical, see its docstring
│   └── dsl.py                 # Rule dataclasses + YAML rule parser (no execution against data yet)
├── validation/            # Validation Execution — wires Rule Engine + Codebook to real data
│   ├── context.py            # ValidationContext (Codebook + DataHandle)
│   ├── results.py              # ValidationResult
│   ├── collector.py             # ErrorCollector
│   └── executor.py                # validate() — see its docstring for RankRule deferral, multi-response convention
├── cleaning/              # Cleaning Engine — transformations over RawTable
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
│   ├── json_report.py            # summary + full results
│   ├── csv_report.py               # raw results only, by design — see its module docstring
│   ├── html_report.py                # self-contained, escaped, no templating dependency
│   └── excel_report.py                 # two sheets: Summary, Details
└── plugins/            # generic entry_points-based plugin registry
tests/unit/              # unit tests, one file per source module
```
