"""The pairing of a Codebook and a DataHandle — the one place in this
framework allowed to hold both simultaneously, per the layering rule
established in the platform architecture document.
"""

from __future__ import annotations

from dataclasses import dataclass

from insightengine.core.codebook import Codebook
from insightengine.data.base import DataHandle


@dataclass(frozen=True, slots=True)
class ValidationContext:
    """Everything :func:`insightengine.validation.executor.validate`
    needs to run a rule set against real data.

    Deliberately does not validate at construction time that every
    codebook question has a corresponding data column — a
    :class:`~insightengine.core.codebook.DerivedVariable` legitimately
    has no column yet (it hasn't been computed; that's the Cleaning
    Engine's job, Phase 7), and requiring one here would make this class
    unusable before that phase exists. Missing columns are handled at the
    point a check actually needs them — see the executor module.
    """

    codebook: Codebook
    data: DataHandle
