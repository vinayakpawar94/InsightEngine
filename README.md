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

**Phases 1–3 complete** (Foundation, Core Domain Models, Data Engine —
pandas backend only). See the project's implementation roadmap for what's
built and what's next.

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
└── plugins/            # generic entry_points-based plugin registry
tests/unit/              # unit tests, one file per source module
```
