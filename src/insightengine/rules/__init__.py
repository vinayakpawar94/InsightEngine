"""The Rule Engine: a restricted expression language and rule representation.

This phase defines what a rule *is* (the dataclasses in
:mod:`insightengine.rules.dsl`) and what a ``when:`` expression can
safely do (:mod:`insightengine.rules.evaluator`). It deliberately does
**not** execute rules against a real dataset — wiring rules to actual
survey data (per-case or vectorized) is Phase 6's job (Validation
Execution), which needs a real ``DataHandle`` and ``Codebook`` to be
meaningful. Everything here operates against a plain variable-name-to-
value mapping, decoupled from both.
"""

from __future__ import annotations
