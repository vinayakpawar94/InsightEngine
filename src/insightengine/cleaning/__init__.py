"""The Cleaning Engine: transformations over a :class:`~insightengine.data.base.RawTable`.

Transformers operate on ``RawTable``, not
:class:`~insightengine.data.base.DataHandle` — ``DataHandle`` is
deliberately read-only (Phase 3), and ``RawTable`` is already the
neutral, functional container built for exactly this kind of
transform-then-reload workflow. See
:mod:`insightengine.cleaning.transformer` for the extract/reload helpers
that bridge a live ``DataHandle`` and this package's transformers.
"""

from __future__ import annotations
