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

**Phase 1 (Foundation) complete,** under the `insightengine` name. See the
project's implementation roadmap for what's built and what's next.
Nothing in this repository processes survey data yet — this phase is the
project skeleton, configuration system, logging, exception hierarchy,
and plugin registry that every later phase depends on.

## Requirements

- Python 3.13+
- This phase's automated tests were run and verified against Python
  3.12.3, since 3.13 was not available in the build environment. Nothing
  in this phase uses a 3.13-only language feature, but re-running the
  test suite on an actual 3.13 interpreter before relying on this phase
  is recommended, not assumed.

## Development setup

```bash
pip install -e ".[dev]"
pytest
mypy src/insightengine --strict
```

## Project layout

```
src/insightengine/
├── core/               # exceptions, enums, config, logging — the dependency floor
└── plugins/            # generic entry_points-based plugin registry
tests/unit/              # unit tests, one file per source module
```
