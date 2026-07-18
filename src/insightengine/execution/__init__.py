"""The Execution Pipeline: orchestrates Data Engine (Phase 3), Cleaning
Engine (Phase 7), and Validation Execution (Phase 6) into one end-to-end
run, with a persisted manifest for resumability.

See :mod:`insightengine.execution.orchestrator` for the stage sequence
and :mod:`insightengine.execution.manifest` for the resumability
contract this package commits to.
"""

from __future__ import annotations
