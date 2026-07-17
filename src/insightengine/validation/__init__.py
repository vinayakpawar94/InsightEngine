"""Validation Execution: wiring the Rule Engine (Phase 5) and Codebook
(Phase 2) to real data (Phase 3).

See :mod:`insightengine.validation.executor` for the scope decisions
this phase makes explicit — most importantly, that ``RankRule``
execution is deliberately deferred, and that "vectorized" here means
"each rule runs once across the whole dataset via columns pulled
through the existing ``DataHandle`` protocol," not numpy-level SIMD
vectorization (Phase 3's frozen ``DataHandle`` protocol has no
columnar-comparison API to do that without breaking backend-agnosticism).
"""

from __future__ import annotations
